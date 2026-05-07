from __future__ import annotations
import datetime
import json
import os
import re as _re
import threading
import time
import unicodedata
from dataclasses import dataclass, asdict
from pathlib import Path

import requests
from crewai import Crew, Process

from . import event_bus

DELAY_SECONDS = 180

# ── Thread-local task context for LLM streaming ───────────────────────────────
_tls = threading.local()

try:
    from crewai.utilities.streaming import crewai_event_bus, LLMStreamChunkEvent

    @crewai_event_bus.on(LLMStreamChunkEvent)
    def _on_llm_chunk(source, event: LLMStreamChunkEvent) -> None:
        task_id = getattr(_tls, "task_id", None)
        if task_id and event.chunk:
            event_bus.emit("llm_chunk", json.dumps({"task_id": task_id, "text": event.chunk}))

except Exception:
    pass


@dataclass
class PlannerTask:
    id: str
    card_name: str
    status: str      # waiting|delegating|planning|copywriting|designing|developing|reviewing|revision|deploying|closing|done|error|cancelled
    log: str
    created_at: float
    start_at: float
    step: int = 0    # 0 = aguardando; 1-7 = etapa atual do pipeline


_tasks: dict[str, PlannerTask] = {}
_tasks_lock = threading.Lock()
_seen_ids: set[str] = set()
_seen_lock = threading.Lock()


# ── Public API ────────────────────────────────────────────────────────────────

def start() -> None:
    api_key = os.environ["TRELLO_API_KEY"]
    token   = os.environ["TRELLO_TOKEN"]
    list_id = os.environ["TRELLO_LIST_ID"]

    print("[planner] inicializando — buscando cards existentes para ignorar...")
    try:
        cards = _fetch_cards(api_key, token, list_id)
        with _seen_lock:
            for c in cards:
                _seen_ids.add(c["id"])
        print(f"[planner] {len(cards)} card(s) existente(s) marcados como ignorados (nao serao executados)")
    except Exception as e:
        print(f"[planner] AVISO ao inicializar: {e}")

    t = threading.Thread(
        target=_loop, args=(api_key, token, list_id),
        daemon=True, name="planner-loop",
    )
    t.start()
    print(f"[planner] loop iniciado — poll a cada 5s, delay de execucao: {DELAY_SECONDS}s")


def get_tasks() -> list[dict]:
    now = time.time()
    with _tasks_lock:
        result = []
        for t in _tasks.values():
            d = asdict(t)
            d["remaining_seconds"] = int(max(0, t.start_at - now)) if t.status == "waiting" else 0
            result.append(d)
    return sorted(result, key=lambda x: x["created_at"], reverse=True)


def cancel_task(task_id: str) -> bool:
    with _tasks_lock:
        task = _tasks.get(task_id)
        if not task:
            return False
        if task.status in ("done", "error", "cancelled"):
            return False
        old_status = task.status
        task.status = "cancelled"
        task.log = "Cancelado pelo usuario"
        name = task.card_name

    print(f"[planner:{task_id[:8]}] CANCELADO (era '{old_status}'): \"{name}\"")
    event_bus.emit("task_cancelled", f"🚫 Task cancelada: \"{name}\"")
    return True


# ── Loop ──────────────────────────────────────────────────────────────────────

def _loop(api_key: str, token: str, list_id: str) -> None:
    while True:
        try:
            _poll(api_key, token, list_id)
        except Exception as e:
            print(f"[planner] erro no loop principal: {e}")
        time.sleep(5)


def _poll(api_key: str, token: str, list_id: str) -> None:
    cards = _fetch_cards(api_key, token, list_id)
    now   = time.time()

    # ── 1. Detecta cards novos ─────────────────────────────────────────────
    for card in cards:
        cid = card["id"]
        with _seen_lock:
            if cid in _seen_ids:
                continue
            _seen_ids.add(cid)

        start_at = now + DELAY_SECONDS
        task = PlannerTask(
            id=cid,
            card_name=card["name"],
            status="waiting",
            log=f"Aguardando {DELAY_SECONDS}s antes de executar (capturando possiveis edicoes)...",
            created_at=now,
            start_at=start_at,
        )
        with _tasks_lock:
            _tasks[cid] = task

        print(f"[planner] NOVO CARD detectado: \"{card['name']}\"")
        print(f"[planner:{cid[:8]}] aguardando {DELAY_SECONDS}s antes de iniciar execucao")
        event_bus.emit("task_new", f"🆕 Novo card: \"{card['name']}\" — iniciando em {DELAY_SECONDS}s")

    # ── 2. Inicia tasks que atingiram o delay ──────────────────────────────
    ready: list[PlannerTask] = []
    with _tasks_lock:
        for task in _tasks.values():
            if task.status == "waiting" and time.time() >= task.start_at:
                ready.append(task)

    for task in ready:
        _start_task(task, api_key, token)


def _start_task(task: PlannerTask, api_key: str, token: str) -> None:
    # Re-verifica o card para capturar edições feitas no período de espera
    print(f"[planner:{task.id[:8]}] 30s esgotados — re-verificando card antes de delegar...")
    try:
        url    = f"https://api.trello.com/1/cards/{task.id}"
        params = {"key": api_key, "token": token, "fields": "name,desc"}
        resp   = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        fresh  = resp.json()
        final_name = fresh["name"]
        final_desc = fresh.get("desc", "")

        if final_name != task.card_name:
            print(f"[planner:{task.id[:8]}] card EDITADO durante espera: '{task.card_name}' → '{final_name}'")
        else:
            print(f"[planner:{task.id[:8]}] card sem alteracoes — prosseguindo")
    except Exception as e:
        print(f"[planner:{task.id[:8]}] erro ao re-verificar card: {e} — usando dados originais")
        final_name = task.card_name
        final_desc = ""

    with _tasks_lock:
        if task.status == "cancelled":
            print(f"[planner:{task.id[:8]}] task foi cancelada, abortando")
            return
        task.card_name = final_name
        task.status = "delegating"
        task.log = "Planner analisou — delegando para o agente Dev"

    print(f"[planner:{task.id[:8]}] INICIANDO PIPELINE para: \"{final_name}\"")
    event_bus.emit("planner_delegating", f"📋 Pipeline iniciado para: \"{final_name}\"")

    threading.Thread(
        target=_run_pipeline,
        args=(task, final_name, final_desc),
        daemon=True,
        name=f"pipeline-{task.id[:8]}",
    ).start()


def _run_dev(task: PlannerTask, card_name: str, card_desc: str) -> None:
    try:
        with _tasks_lock:
            task.status = "running"
            task.log = "Dev agent executando no terminal..."

        print(f"[planner:{task.id[:8]}] Dev agent INICIADO para: \"{card_name}\"")

        message = card_name
        if card_desc:
            message = f"{card_name}\n\nDescricao: {card_desc}"

        from crewai import Crew
        from .agents import create_developer
        from .tasks import create_dev_task

        dev  = create_developer()
        tobj = create_dev_task(dev, message)
        crew = Crew(agents=[dev], tasks=[tobj], verbose=False)
        result = crew.kickoff()
        result_str = str(result)[:300]

        with _tasks_lock:
            if task.status != "cancelled":
                task.status = "done"
                task.log = f"Concluido. {result_str}"

        print(f"[planner:{task.id[:8]}] Dev CONCLUIU: \"{card_name}\"")
        print(f"[planner:{task.id[:8]}] resultado resumido: {result_str[:100]}")
        event_bus.emit("dev_done", f"✅ Dev concluiu: \"{card_name}\"")

    except Exception as e:
        with _tasks_lock:
            task.status = "error"
            task.log = f"Erro: {e}"
        print(f"[planner:{task.id[:8]}] ERRO ao executar \"{card_name}\": {e}")
        event_bus.emit("error", f"❌ Erro: \"{card_name}\" — {e}")


# ── Pipeline helpers ─────────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = _re.sub(r"[^\w\s-]", "", text)
    text = _re.sub(r"[\s_]+", "-", text)
    return _re.sub(r"-{2,}", "-", text).strip("-")


def _parse_qa_verdict(qa_result: str) -> str:
    """Parsea output do Crew QA — espera JSON com 'verdict' ou string contendo APROVADO."""
    import json as _json
    try:
        for line in qa_result.split("\n"):
            line = line.strip()
            if line.startswith("{") and "verdict" in line:
                obj = _json.loads(line)
                v = obj.get("verdict", "").upper()
                if v in ("APROVADO", "REPROVADO"):
                    return v
    except Exception:
        pass
    upper = qa_result.upper()
    if "STATUS: APROVADO" in upper or '"VERDICT": "APROVADO"' in upper:
        return "APROVADO"
    return "REPROVADO"


def _read_project_files(project_dir: str) -> str:
    p = Path(project_dir)
    if not p.exists():
        return f"Pasta {project_dir} nao encontrada."
    files = [f.name for f in p.rglob("*") if f.is_file() and not f.name.startswith(".")]
    summary = f"Arquivos ({len(files)} total): {', '.join(files[:20])}\n"
    index = p / "index.html"
    if index.exists():
        content = index.read_text(encoding="utf-8", errors="ignore")
        summary += f"\nindex.html (primeiros 300 chars):\n{content[:300]}"
    return summary


def _run_pipeline(task: PlannerTask, card_name: str, card_desc: str) -> None:
    """Pipeline completo de 10 etapas + curadoria pos-pipeline."""
    _tls.task_id = task.id  # route LLM streaming tokens to this task

    from .agents import (
        create_copywriter, create_planner, create_designer,
        create_image_artist, create_designer_reviewer, create_3d_artist,
        create_researcher,
        create_developer, create_qa, create_qa_code, create_qa_visual,
        create_devops, create_bibliotecario,
        llm,
    )
    from .tasks import (
        create_planner_moc_task, create_copywriter_pipeline_task,
        create_designer_task,
        create_image_pipeline_task, create_designer_review_task, create_3d_pipeline_task,
        create_creative_brief_task,
        create_dev_task,
        create_qa_task, create_qa_brief_task, create_dev_revision_task,
        create_devops_task, create_planner_close_task,
        create_curator_finalize_task,
    )
    from . import vault_writer
    from . import trello_tool
    from . import librarian
    from . import asset_manifest as _am
    from . import pipeline_logger
    from .flux_tool import FluxImageTool

    slug        = _slugify(card_name)
    pipeline_logger.set_active_slug(slug)
    today       = datetime.date.today().isoformat()
    project_dir = rf"C:\Users\v27me\Videos\{slug}"
    moc_path    = f"Atlas/Maps/{slug} MOC.md"
    effort_path = f"Efforts/On/{slug} (E).md"

    def _set(step_num: int, status: str, log_msg: str) -> bool:
        with _tasks_lock:
            if task.status == "cancelled":
                return False
            task.status = status
            task.step   = step_num
            task.log    = log_msg
        event_bus.emit("pipeline_step", f"[{step_num}/10] {log_msg}")
        pipeline_logger.log_event(None, "step_start", {"step": step_num, "status": status})
        return True

    final_status = "error"
    design_result = ""
    manifest_resolved = {"images": []}

    try:
        # ── 1. PLANEJAMENTO ──────────────────────────────────────────────────
        if not _set(1, "planning", f"Planner criando MOC para '{slug}'..."):
            return

        moc_content = (
            f"## Briefing\n{card_desc}\n\n"
            f"## Copywriting\n\n## Design\n\n## Imagens\n\n## Modelos 3D\n\n"
            f"## Dev\n\n## Deploy\n\n## Curadoria\n\n## Aprendizados"
        )
        effort_content = f"## Objetivo\n{card_name}\n\n## Progresso\n- [ ] Pipeline iniciado"
        vault_writer.write_note(relative_path=moc_path,    title=f"{slug} MOC",  content=moc_content,    agent_id="planner", ace_type="atlas")
        vault_writer.write_note(relative_path=effort_path, title=slug,           content=effort_content,  agent_id="planner", ace_type="efforts")

        planner = create_planner()
        Crew(agents=[planner], tasks=[create_planner_moc_task(planner, {"card_name": card_name, "card_desc": card_desc, "slug": slug, "moc_path": moc_path, "effort_path": effort_path})], verbose=False).kickoff()

        # ── 2. CREW CRIATIVO (substitui copy/design/imgs/review/3D) ─────────
        # Statuses cobertos pelo Crew Criativo: copywriting, designing,
        # imagining, reviewing_assets, regen_assets, modeling_3d.
        if not _set(2, "creative_crew", "Crew Criativo trabalhando..."):
            return

        researcher        = create_researcher()
        copy_agent        = create_copywriter()
        designer          = create_designer()
        image_artist      = create_image_artist()
        artist_3d         = create_3d_artist()
        designer_reviewer = create_designer_reviewer()

        creative_crew = Crew(
            agents=[researcher, copy_agent, designer, image_artist, artist_3d, designer_reviewer],
            tasks=[create_creative_brief_task({
                "slug":      slug,
                "card_name": card_name,
                "card_desc": card_desc,
            })],
            process=Process.hierarchical,
            manager_llm=llm,
            verbose=False,
        )
        creative_result = str(creative_crew.kickoff())

        # Hooks do bibliotecario apos crew terminar.
        # Os hooks after_copy/after_design/after_assets serao disparados pelos
        # proprios agentes/tools no futuro; por ora rodamos after_research +
        # after_assets aqui (ambos baseados em arquivos gravados em disco).
        references_path = f"output/{slug}/research/references.json"
        if Path(references_path).exists():
            librarian.after_research(slug, references_path, moc_path)

        manifest_resolved_path = Path(f"output/{slug}/assets/manifest_resolved.json")
        if manifest_resolved_path.exists():
            try:
                manifest_resolved = json.loads(manifest_resolved_path.read_text(encoding="utf-8"))
            except Exception:
                manifest_resolved = {"images": []}
            librarian.after_assets(slug, manifest_resolved, project_dir, moc_path)

        # Recuperar paths de copy/guia para compor mensagem do Dev (best-effort).
        copy_path  = f"Atlas/Notes/Sources/Copywriter/{today}-{slug}-copy.md"
        guide_path = f"Atlas/Utilities/Designer/{today}-{slug}-visual-guide.md"

        # ── 7. DESENVOLVIMENTO (era 4) ───────────────────────────────────────
        if not _set(7, "developing", f"Dev construindo '{slug}' via Claude CLI..."):
            return

        dev_message = (
            f"Projeto: {card_name}\nSlug: {slug}\nBriefing: {card_desc}\n\n"
            f"Copy salva em vault: {copy_path}\n"
            f"Guia visual salvo em vault: {guide_path}\n"
            f"Manifest resolvido: output/{slug}/assets/manifest_resolved.json\n\n"
            f"Use obsidian_vault_search para consultar o guia visual antes de montar o prompt para o Claude CLI. "
            f"Os PNGs e GLBs estao disponiveis em output/{slug}/assets/."
        )
        dev_agent = create_developer()
        Crew(agents=[dev_agent], tasks=[create_dev_task(dev_agent, dev_message)], verbose=False).kickoff()
        librarian.after_dev(slug, project_dir, moc_path)

        # ── 8-9. CREW QA com loop de iteracao ────────────────────────────
        MAX_QA_RETRIES = 2
        verdict = "REPROVADO"
        for attempt in range(MAX_QA_RETRIES + 1):
            if not _set(9, "qa_crew", f"Crew QA revisando (tentativa {attempt+1}/{MAX_QA_RETRIES+1})..."):
                return

            qa_code_agent   = create_qa_code()
            qa_visual_agent = create_qa_visual()

            qa_crew = Crew(
                agents=[qa_code_agent, qa_visual_agent],
                tasks=[create_qa_brief_task({
                    "slug":            slug,
                    "project_dir":     project_dir,
                    "references_path": f"output/{slug}/research/references.json",
                })],
                process=Process.hierarchical,
                manager_llm=llm,
                verbose=False,
            )
            qa_result = str(qa_crew.kickoff())
            verdict = _parse_qa_verdict(qa_result)

            qa_report = Path(f"output/{slug}/qa_visual/report.json")
            qa_screens = Path(f"output/{slug}/qa_visual/current")
            if qa_report.exists():
                librarian.after_qa_visual(slug, str(qa_report), str(qa_screens), moc_path)

            if verdict == "APROVADO":
                break

            if attempt < MAX_QA_RETRIES:
                fix_prompt_path = Path(f"output/{slug}/qa_visual/fix_prompt.md")
                if not fix_prompt_path.exists():
                    event_bus.emit("warn", "QA reprovou mas fix_prompt nao foi gerado; abortando.")
                    break
                fix_prompt = fix_prompt_path.read_text(encoding="utf-8")
                if not _set(8, "revision", f"Dev corrigindo (tentativa {attempt+2})..."):
                    return
                dev_rev = create_developer()
                Crew(agents=[dev_rev],
                     tasks=[create_dev_revision_task(dev_rev, {
                         "slug": slug, "project_dir": project_dir, "qa_feedback": fix_prompt,
                     })],
                     verbose=False).kickoff()

        if verdict != "APROVADO":
            with _tasks_lock:
                task.status = "qa_blocked"
                task.log    = f"QA bloqueou apos {MAX_QA_RETRIES+1} tentativas"
            event_bus.emit("qa_blocked", f"❌ '{card_name}' bloqueado pelo QA")
            final_status = "qa_blocked"
            return

        # ── 9. DEPLOY (era 6) ────────────────────────────────────────────────
        if not _set(9, "deploying", "DevOps fazendo push para GitHub + Netlify..."):
            return

        devops_agent = create_devops()
        devops_raw   = str(Crew(agents=[devops_agent], tasks=[create_devops_task(devops_agent, {"slug": slug})], verbose=False).kickoff())

        gh_match    = _re.search(r"https://github\.com/[\w.-]+/[\w.-]+", devops_raw)
        nl_match    = _re.search(r"https://[\w-]+\.netlify\.app", devops_raw)
        github_url  = gh_match.group(0) if gh_match else devops_raw.strip()
        netlify_url = nl_match.group(0) if nl_match else ""

        # ── 10. FECHAMENTO (era 7) ───────────────────────────────────────────
        if not _set(10, "closing", "Planner atualizando Trello e arquivando vault..."):
            return

        deploy_summary = github_url
        if netlify_url:
            deploy_summary += f"\nNetlify: {netlify_url}"

        done_list_id = os.environ.get("TRELLO_DONE_LIST_ID", "")
        if done_list_id:
            try:
                trello_tool.update_card_description(task.id, f"{card_desc}\n\n---\n Entregue:\n- GitHub: {github_url}{chr(10) + '- Netlify: ' + netlify_url if netlify_url else ''}")
                trello_tool.move_card_to_list(task.id, done_list_id)
            except Exception as e:
                print(f"[planner:{task.id[:8]}] AVISO Trello: {e}")

        librarian.after_deploy(slug, github_url, moc_path, effort_path, netlify_url=netlify_url)

        planner2 = create_planner()
        Crew(agents=[planner2], tasks=[create_planner_close_task(planner2, {"card_name": card_name, "github_url": github_url, "netlify_url": netlify_url})], verbose=False).kickoff()

        # ── DONE ─────────────────────────────────────────────────────────────
        with _tasks_lock:
            task.status = "done"
            task.step   = 10
            task.log    = f"Pipeline concluido — {deploy_summary}"

        print(f"[planner:{task.id[:8]}] PIPELINE CONCLUIDO: \"{card_name}\" → {deploy_summary}")
        event_bus.emit("pipeline_done", f"'{card_name}' entregue: {deploy_summary}")
        final_status = "done"

    except Exception as e:
        with _tasks_lock:
            task.status = "error"
            task.log    = f"Erro na etapa {task.step}: {e}"
        print(f"[planner:{task.id[:8]}] ERRO na etapa {task.step}: {e}")
        event_bus.emit("error", f"Erro no pipeline '{card_name}': {e}")
        final_status = "error"

    finally:
        # Curadoria pos-pipeline — sempre roda
        # Se a task foi cancelada durante o pipeline, respeita esse status final
        with _tasks_lock:
            if task.status == "cancelled":
                final_status = "cancelled"
        try:
            _run_curation(task, slug, moc_path, effort_path, final_status)
        except Exception as e:
            print(f"[planner:{task.id[:8]}] ERRO na curadoria: {e}")
        pipeline_logger.set_active_slug(None)


def _run_curation(task: PlannerTask, slug: str, moc_path: str, effort_path: str, final_status: str) -> None:
    """Fase pos-pipeline: bibliotecario faz curadoria final. Sempre roda."""
    from .agents import create_bibliotecario
    from .tasks import create_curator_finalize_task
    from . import pipeline_logger as _pl

    with _tasks_lock:
        previous_log = task.log
        task.status  = "curating"
        task.log     = f"Bibliotecario fazendo curadoria final de '{slug}'..."
    event_bus.emit("pipeline_step", f"[C] Bibliotecario curando {slug}...")

    _pl.log_event(None, "step_start", {"step": "curating", "status": "curating"})

    biblio     = create_bibliotecario()
    crew_task  = create_curator_finalize_task(biblio, {
        "slug":         slug,
        "moc_path":     moc_path,
        "effort_path":  effort_path,
        "final_status": final_status,
        "log_path":     f"output/{slug}/.pipeline.log",
    })
    try:
        Crew(agents=[biblio], tasks=[crew_task], verbose=False).kickoff()
    except Exception as e:
        print(f"[planner:{task.id[:8]}] curadoria abortou: {e}")

    with _tasks_lock:
        task.status = final_status
        task.log    = f"{previous_log} | curadoria concluida"

    _pl.log_event(None, "step_end", {"step": "curating"})
    event_bus.emit("pipeline_step", f"[C] Curadoria de '{slug}' concluida")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fetch_cards(api_key: str, token: str, list_id: str) -> list[dict]:
    url    = f"https://api.trello.com/1/lists/{list_id}/cards"
    params = {"key": api_key, "token": token, "fields": "name,desc,id"}
    resp   = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


# ── Whisper buffer ────────────────────────────────────────────────────────────
import threading as _threading_wb

# Buffer de whisper por agente (acumula chunks pra flushar como 1 mensagem)
_whisper_buffer: dict[str, dict] = {}
_whisper_buffer_lock = _threading_wb.Lock()


def _whisper_buffer_append(agent_id: str, slug: str, chunk: str) -> None:
    with _whisper_buffer_lock:
        entry = _whisper_buffer.setdefault(agent_id, {"slug": slug, "text": ""})
        entry["slug"] = slug
        entry["text"] += chunk


def _whisper_buffer_flush(agent_id: str, slug: str) -> None:
    """Flush do buffer pro DB (whisper)."""
    from . import agent_messages
    with _whisper_buffer_lock:
        entry = _whisper_buffer.pop(agent_id, None)
    if not entry or not entry["text"].strip():
        return
    text = entry["text"].strip()[-600:]
    agent_messages.record(slug, agent_id, "whisper", text)


def _whisper_buffer_clear() -> None:
    """Util pra testes."""
    with _whisper_buffer_lock:
        _whisper_buffer.clear()


def _emit_agent_step(agent_id: str, agent_name: str, what_was_done: str,
                     next_agent: str | None, slug: str) -> None:
    """Chamado ao fim do step de um agente: flusha whisper, gera handoff, grava say."""
    from . import agent_messages
    from .handoff import generate_handoff

    _whisper_buffer_flush(agent_id, slug)
    text = generate_handoff(agent_id, agent_name, what_was_done, next_agent)
    agent_messages.record(slug, agent_id, "say", text)
