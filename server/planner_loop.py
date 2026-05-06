from __future__ import annotations
import datetime
import json
import os
import re as _re
import threading
import time
import unicodedata
from dataclasses import dataclass, asdict

import requests
from crewai import Crew

from . import event_bus

DELAY_SECONDS = 180

# ── Thread-local task context for LLM streaming ───────────────────────────────
_tls = threading.local()

try:
    import litellm

    class _ChunkLogger(litellm.CustomLogger):
        def log_stream_event(self, kwargs, response_obj, start_time, end_time):
            try:
                task_id = getattr(_tls, "task_id", None)
                if not task_id:
                    return
                choices = getattr(response_obj, "choices", None)
                if not choices:
                    return
                delta = getattr(choices[0], "delta", None)
                text = (getattr(delta, "content", None) or "") if delta else ""
                if text:
                    event_bus.emit("llm_chunk", json.dumps({"task_id": task_id, "text": text}))
            except Exception:
                pass

    litellm.callbacks = [_ChunkLogger()]
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


def _read_project_files(project_dir: str) -> str:
    from pathlib import Path
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
    """Pipeline completo de 7 etapas para um card do Trello."""
    _tls.task_id = task.id  # route LLM streaming tokens to this task

    from .agents import (
        create_copywriter, create_planner, create_designer,
        create_developer, create_qa, create_devops,
    )
    from .tasks import (
        create_planner_moc_task, create_copywriter_pipeline_task,
        create_designer_task, create_dev_task,
        create_qa_task, create_dev_revision_task, create_devops_task, create_planner_close_task,
    )
    from . import vault_writer
    from . import trello_tool
    from . import librarian

    slug        = _slugify(card_name)
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
        event_bus.emit("pipeline_step", f"[{step_num}/7] {log_msg}")
        return True

    try:
        # ── 1. PLANEJAMENTO ──────────────────────────────────────────────────
        if not _set(1, "planning", f"Planner criando MOC para '{slug}'..."):
            return

        moc_content = (
            f"## Briefing\n{card_desc}\n\n"
            f"## Copywriting\n\n## Design\n\n## Dev\n\n## Deploy\n\n## Aprendizados"
        )
        effort_content = f"## Objetivo\n{card_name}\n\n## Progresso\n- [ ] Pipeline iniciado"
        vault_writer.write_note(relative_path=moc_path,    title=f"{slug} MOC",  content=moc_content,    agent_id="planner", ace_type="atlas")
        vault_writer.write_note(relative_path=effort_path, title=slug,           content=effort_content,  agent_id="planner", ace_type="efforts")

        planner = create_planner()
        Crew(agents=[planner], tasks=[create_planner_moc_task(planner, {"card_name": card_name, "card_desc": card_desc, "slug": slug, "moc_path": moc_path, "effort_path": effort_path})], verbose=False).kickoff()

        # ── 2. COPYWRITING ───────────────────────────────────────────────────
        if not _set(2, "copywriting", "Copywriter escrevendo copy..."):
            return

        copy_agent  = create_copywriter()
        copy_result = str(Crew(agents=[copy_agent], tasks=[create_copywriter_pipeline_task(copy_agent, {"card_name": card_name, "card_desc": card_desc, "slug": slug})], verbose=False).kickoff())
        copy_path   = f"Atlas/Notes/Sources/Copywriter/{today}-{slug}-copy.md"
        vault_writer.write_note(relative_path=copy_path, title=f"{slug} — Copy", content=copy_result, agent_id="copywriter", ace_type="sources", tags=["copy", slug])

        librarian.after_copy(slug, copy_path, moc_path)

        # ── 3. DESIGN ────────────────────────────────────────────────────────
        if not _set(3, "designing", "Designer criando guia visual..."):
            return

        designer      = create_designer()
        design_result = str(Crew(agents=[designer], tasks=[create_designer_task(designer, {"slug": slug, "copy_path": copy_path})], verbose=False).kickoff())
        guide_path    = f"Atlas/Utilities/Designer/{today}-{slug}-visual-guide.md"
        vault_writer.write_note(relative_path=guide_path, title=f"Guia Visual: {slug}", content=design_result, agent_id="designer", ace_type="resources", tags=["design", "guia-visual", slug])

        # ── 4. DESENVOLVIMENTO ───────────────────────────────────────────────
        if not _set(4, "developing", f"Dev construindo '{slug}' via Claude CLI..."):
            return

        dev_message = (
            f"Projeto: {card_name}\n"
            f"Slug: {slug}\n"
            f"Briefing: {card_desc}\n\n"
            f"Copy salva em vault: {copy_path}\n"
            f"Guia visual salvo em vault: {guide_path}\n\n"
            f"Use obsidian_vault_search para consultar o guia visual antes de montar o prompt para o Claude CLI."
        )
        dev_agent = create_developer()
        Crew(agents=[dev_agent], tasks=[create_dev_task(dev_agent, dev_message)], verbose=False).kickoff()

        librarian.after_dev(slug, project_dir, moc_path)

        # ── 5. QA (primeira revisão) ─────────────────────────────────────────
        if not _set(5, "reviewing", "QA revisando codigo..."):
            return

        file_summary = _read_project_files(project_dir)
        qa_agent     = create_qa()
        qa_result    = str(Crew(agents=[qa_agent], tasks=[create_qa_task(qa_agent, {"slug": slug, "project_dir": project_dir, "file_summary": file_summary})], verbose=False).kickoff())

        if "STATUS: REPROVADO" in qa_result:
            # ── Envia de volta ao Dev para corrigir ──────────────────────────
            if not _set(5, "revision", f"QA reprovou — Dev corrigindo os problemas..."):
                return

            print(f"[planner:{task.id[:8]}] QA REPROVOU — iniciando revisao com Dev")
            event_bus.emit("qa_failed", f"⚠️ QA reprovou '{card_name}' — Dev revisando...")

            dev_rev      = create_developer()
            Crew(agents=[dev_rev], tasks=[create_dev_revision_task(dev_rev, {
                "slug":         slug,
                "project_dir":  project_dir,
                "qa_feedback":  qa_result,
            })], verbose=False).kickoff()

            # ── QA segunda passagem ───────────────────────────────────────────
            if not _set(5, "reviewing", "QA revisando codigo corrigido..."):
                return

            file_summary2 = _read_project_files(project_dir)
            qa_agent2     = create_qa()
            qa_result2    = str(Crew(agents=[qa_agent2], tasks=[create_qa_task(qa_agent2, {"slug": slug, "project_dir": project_dir, "file_summary": file_summary2})], verbose=False).kickoff())

            if "STATUS: REPROVADO" in qa_result2:
                with _tasks_lock:
                    task.status = "error"
                    task.log    = f"QA reprovou apos revisao: {qa_result2[:300]}"
                print(f"[planner:{task.id[:8]}] QA REPROVOU apos revisao — abortando pipeline")
                event_bus.emit("error", f"❌ QA reprovou '{card_name}' após revisão")
                return

            print(f"[planner:{task.id[:8]}] QA APROVADO na segunda passagem apos revisao")

        # ── 6. DEPLOY ────────────────────────────────────────────────────────
        if not _set(6, "deploying", "DevOps fazendo push para GitHub + Netlify..."):
            return

        devops_agent = create_devops()
        devops_raw   = str(Crew(agents=[devops_agent], tasks=[create_devops_task(devops_agent, {"slug": slug})], verbose=False).kickoff())

        gh_match    = _re.search(r"https://github\.com/[\w.-]+/[\w.-]+", devops_raw)
        nl_match    = _re.search(r"https://[\w-]+\.netlify\.app", devops_raw)
        github_url  = gh_match.group(0) if gh_match else devops_raw.strip()
        netlify_url = nl_match.group(0) if nl_match else ""

        # ── 7. FECHAMENTO ────────────────────────────────────────────────────
        if not _set(7, "closing", "Planner atualizando Trello e arquivando vault..."):
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
            task.step   = 7
            task.log    = f"Pipeline concluido — {deploy_summary}"

        print(f"[planner:{task.id[:8]}] PIPELINE CONCLUIDO: \"{card_name}\" → {deploy_summary}")
        event_bus.emit("pipeline_done", f"'{card_name}' entregue: {deploy_summary}")

    except Exception as e:
        with _tasks_lock:
            task.status = "error"
            task.log    = f"Erro na etapa {task.step}: {e}"
        print(f"[planner:{task.id[:8]}] ERRO na etapa {task.step}: {e}")
        event_bus.emit("error", f"Erro no pipeline '{card_name}': {e}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fetch_cards(api_key: str, token: str, list_id: str) -> list[dict]:
    url    = f"https://api.trello.com/1/lists/{list_id}/cards"
    params = {"key": api_key, "token": token, "fields": "name,desc,id"}
    resp   = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()
