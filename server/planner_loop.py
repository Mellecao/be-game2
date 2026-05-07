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
    """Pipeline completo de 10 etapas + curadoria pos-pipeline."""
    _tls.task_id = task.id  # route LLM streaming tokens to this task

    from .agents import (
        create_copywriter, create_planner, create_designer,
        create_image_artist, create_designer_reviewer, create_3d_artist,
        create_developer, create_qa, create_devops, create_bibliotecario,
    )
    from .tasks import (
        create_planner_moc_task, create_copywriter_pipeline_task,
        create_designer_task,
        create_image_pipeline_task, create_designer_review_task, create_3d_pipeline_task,
        create_dev_task,
        create_qa_task, create_dev_revision_task, create_devops_task, create_planner_close_task,
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

        manifest = _am.parse_manifest(design_result)
        import json as _json
        librarian.after_design(slug, guide_path, _json.dumps(manifest), moc_path)

        # ── 4. IMAGENS ───────────────────────────────────────────────────────
        if manifest.get("images"):
            if not _set(4, "imagining", "Image Artist gerando PNGs do manifest..."):
                return

            # Iteracao deterministica: chama FluxImageTool diretamente para cada item
            # do manifest, evitando correlacao fragil por zip (que falha se a geracao
            # de qualquer imagem silencia sem emitir evento).
            # TODO: se necessario, re-adicionar Crew de Image Artist apenas para
            # traducao/enriquecimento do prompt_en antes da geracao.
            flux = FluxImageTool()
            manifest_resolved = {"images": []}
            for spec in manifest["images"]:
                item = dict(spec)
                prompt_en = spec.get("prompt_en") or (
                    f"{spec.get('prompt_pt', spec.get('prompt', ''))}, "
                    "cinematic, sharp focus, 8k, detailed"
                )
                result = flux._run(prompt_en)
                if not result.startswith("Erro"):
                    item["png_path"] = result
                manifest_resolved["images"].append(item)
            _am.write_resolved(slug, manifest_resolved)

            # Catastrofe: nenhuma imagem gerada
            if not any(i.get("png_path") for i in manifest_resolved["images"]):
                with _tasks_lock:
                    task.status = "error"
                    task.log    = "Nenhuma imagem do manifest foi gerada — Forge offline?"
                event_bus.emit("error", f"❌ Imagens falharam para '{card_name}'")
                final_status = "error"
                return

            # ── 5. DESIGNER REVIEW ───────────────────────────────────────────
            if not _set(5, "reviewing_assets", "Designer revisando os PNGs..."):
                return

            reviewer    = create_designer_reviewer()
            review_task = create_designer_review_task(reviewer, {
                "slug":             slug,
                "manifest_resolved": manifest_resolved,
                "guide_excerpt":    design_result[:3000],
            })
            review_raw = str(Crew(agents=[reviewer], tasks=[review_task], verbose=False).kickoff())

            try:
                review_data = _json.loads(review_raw.strip())
                reviews     = review_data.get("reviews", [])
            except _json.JSONDecodeError:
                reviews = []

            for r in reviews:
                pipeline_logger.log_event(None, "asset_review", {
                    "asset_id": r.get("id"),
                    "verdict":  r.get("verdict"),
                    "reason":   r.get("reason", "")[:200],
                })

            reproved = [r for r in reviews if r.get("verdict") == "REPROVADO"]
            if reproved:
                if not _set(5, "regen_assets", f"Regenerando {len(reproved)} imagens reprovadas..."):
                    return

                flux = FluxImageTool()
                for r in reproved:
                    item = next((i for i in manifest_resolved["images"] if i["id"] == r["id"]), None)
                    if not item or not r.get("regen_prompt"):
                        continue
                    new_path = flux._run(r["regen_prompt"])
                    if not new_path.startswith("Erro"):
                        item["png_path"] = new_path
                _am.write_resolved(slug, manifest_resolved)

            # ── 6. 3D ────────────────────────────────────────────────────────
            threed_items = [i for i in manifest_resolved.get("images", [])
                            if i.get("convert_to_3d") and i.get("png_path")]
            if threed_items:
                if not _set(6, "modeling_3d", f"3D Artist gerando {len(threed_items)} GLBs..."):
                    return

                artist3d = create_3d_artist()
                t3d      = create_3d_pipeline_task(artist3d, {"slug": slug})
                Crew(agents=[artist3d], tasks=[t3d], verbose=False).kickoff()

                glb_events   = [e for e in pipeline_logger.read_log(slug)
                                if e["event"] == "asset_generated" and e.get("kind") == "glb"]
                glb_by_source = {ev.get("source_image"): ev["path"] for ev in glb_events}
                for item in manifest_resolved["images"]:
                    if item.get("png_path") in glb_by_source:
                        item["glb_path"] = glb_by_source[item["png_path"]]
                _am.write_resolved(slug, manifest_resolved)

            librarian.after_assets(slug, manifest_resolved, project_dir, moc_path)

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

        # ── 8. QA (era 5) — preserva loop de revisao existente ──────────────
        if not _set(8, "reviewing", "QA revisando codigo..."):
            return

        file_summary = _read_project_files(project_dir)
        qa_agent     = create_qa()
        qa_result    = str(Crew(agents=[qa_agent], tasks=[create_qa_task(qa_agent, {"slug": slug, "project_dir": project_dir, "file_summary": file_summary})], verbose=False).kickoff())

        if "STATUS: REPROVADO" in qa_result:
            if not _set(8, "revision", f"QA reprovou — Dev corrigindo os problemas..."):
                return

            print(f"[planner:{task.id[:8]}] QA REPROVOU — iniciando revisao com Dev")
            event_bus.emit("qa_failed", f"⚠️ QA reprovou '{card_name}' — Dev revisando...")

            dev_rev = create_developer()
            Crew(agents=[dev_rev], tasks=[create_dev_revision_task(dev_rev, {
                "slug":        slug,
                "project_dir": project_dir,
                "qa_feedback": qa_result,
            })], verbose=False).kickoff()

            if not _set(8, "reviewing", "QA revisando codigo corrigido..."):
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
                final_status = "error"
                return

            print(f"[planner:{task.id[:8]}] QA APROVADO na segunda passagem apos revisao")

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
