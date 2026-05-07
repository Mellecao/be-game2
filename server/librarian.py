# server/librarian.py
"""
Bibliotecario transversal — intervem no pipeline em 3 momentos.
Implementado em Task C1; este arquivo e um stub para permitir import durante Task B2.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import date
from pathlib import Path

from . import pipeline_logger

VAULT_PATH = Path(os.getenv("OBSIDIAN_VAULT_PATH", r"C:\Users\v27me\OneDrive\Desktop\Ideaverse"))


def enforce_asset_name(filename: str, pattern: str) -> bool:
    """Retorna True se o nome do arquivo bate com o padrao regex esperado."""
    return bool(re.match(pattern, Path(filename).name))


def after_copy(slug: str, copy_path: str, moc_path: str, index: bool = True) -> None:
    """Intervencao pos-copy: valida nome, atualiza MOC, re-indexa."""
    expected_pattern = rf"^\d{{4}}-\d{{2}}-\d{{2}}-{re.escape(slug)}-copy\.md$"
    filename = Path(copy_path).name
    if not enforce_asset_name(filename, expected_pattern):
        logging.getLogger(__name__).warning(
            "bibliotecario: nome da copy fora do padrao: '%s' (esperado: %s)", filename, expected_pattern
        )

    full_moc = VAULT_PATH / moc_path
    if not full_moc.exists():
        return

    text = full_moc.read_text(encoding="utf-8")
    copy_stem = copy_path.replace(".md", "")
    link = f"[[{copy_stem}]]"

    if "## Copywriting" in text and link not in text:
        text = text.replace("## Copywriting\n", f"## Copywriting\n- {link}\n")
        full_moc.write_text(text, encoding="utf-8")
        pipeline_logger.log_event(None, "vault_write", {
            "path": str(full_moc.relative_to(VAULT_PATH)) if full_moc.is_relative_to(VAULT_PATH) else str(full_moc),
            "agent_id": "bibliotecario",
            "ace_type": "atlas",
        })

    if index:
        try:
            from server.obsidian_indexer import index_single_file
            index_single_file(full_moc)
        except Exception as exc:
            logging.getLogger(__name__).debug("bibliotecario: indexing MOC skipped — %s", exc)


def after_dev(slug: str, project_dir: str, moc_path: str, index: bool = True) -> None:
    """Intervencao pos-dev: captura stack, cria nota de aprendizados, atualiza MOC."""
    p = Path(project_dir)
    if not p.exists():
        return

    all_files = [f.name for f in p.rglob("*") if f.is_file() and not f.name.startswith(".")]
    has_three  = any("three" in f.lower() for f in all_files)
    has_gsap   = any("gsap" in f.lower() for f in all_files)
    has_ts     = any(f.endswith(".ts") for f in all_files)
    stack_tags = []
    if has_three: stack_tags.append("Three.js")
    if has_gsap:  stack_tags.append("GSAP")
    if has_ts:    stack_tags.append("TypeScript")
    stack_tags.append("HTML/CSS/JS")

    today   = date.today().isoformat()
    title   = f"Aprendizados: {slug}"
    content = (
        f"## Contexto\nProjeto gerado automaticamente pelo pipeline BE-Game.\n\n"
        f"## Stack Detectada\n" + "\n".join(f"- {t}" for t in stack_tags) + "\n\n"
        f"## Arquivos Gerados\n- Total: {len(all_files)} arquivos\n"
        f"- Lista: {', '.join(all_files[:15])}\n"
    )

    learnings_path = f"Atlas/Notes/Agentes/Bibliotecario/{today}-{slug}-learnings.md"
    full_learnings = VAULT_PATH / learnings_path
    full_learnings.parent.mkdir(parents=True, exist_ok=True)

    import yaml
    from server.vault_writer import build_frontmatter
    fm   = build_frontmatter("bibliotecario", "atlas", tags=["aprendizado", slug] + stack_tags)
    body = f"---\n{fm}---\n\n# {title}\n\n{content}"
    full_learnings.write_text(body, encoding="utf-8")
    pipeline_logger.log_event(None, "vault_write", {
        "path": str(full_learnings.relative_to(VAULT_PATH)) if full_learnings.is_relative_to(VAULT_PATH) else str(full_learnings),
        "agent_id": "bibliotecario",
        "ace_type": "atlas",
    })

    full_moc = VAULT_PATH / moc_path
    if full_moc.exists():
        text = full_moc.read_text(encoding="utf-8")
        link = f"[[{learnings_path.replace('.md', '')}]]"
        if "## Dev" in text and link not in text:
            text = text.replace("## Dev\n", f"## Dev\n- {link}\n")
            full_moc.write_text(text, encoding="utf-8")
            pipeline_logger.log_event(None, "vault_write", {
                "path": str(full_moc.relative_to(VAULT_PATH)) if full_moc.is_relative_to(VAULT_PATH) else str(full_moc),
                "agent_id": "bibliotecario",
                "ace_type": "atlas",
            })

    if index:
        try:
            from server.obsidian_indexer import index_single_file
            index_single_file(full_learnings)
            if full_moc.exists():
                index_single_file(full_moc)
        except Exception as exc:
            logging.getLogger(__name__).debug("bibliotecario: indexing skipped — %s", exc)


def after_deploy(
    slug: str,
    github_url: str,
    moc_path: str,
    effort_path: str,
    netlify_url: str = "",
    index: bool = True,
) -> None:
    """Intervencao pos-deploy: atualiza MOC com URLs (GitHub + Netlify), arquiva Effort."""
    full_moc = VAULT_PATH / moc_path
    if full_moc.exists():
        text = full_moc.read_text(encoding="utf-8")
        if "## Deploy" in text and github_url not in text:
            url_lines = f"- GitHub: {github_url}\n"
            if netlify_url:
                url_lines += f"- Netlify: {netlify_url}\n"
            text = text.replace("## Deploy\n", f"## Deploy\n{url_lines}")
            full_moc.write_text(text, encoding="utf-8")
            pipeline_logger.log_event(None, "vault_write", {
                "path": str(full_moc.relative_to(VAULT_PATH)) if full_moc.is_relative_to(VAULT_PATH) else str(full_moc),
                "agent_id": "bibliotecario",
                "ace_type": "atlas",
            })

    full_effort = VAULT_PATH / effort_path
    if full_effort.exists():
        archive_dir = VAULT_PATH / "Efforts" / "Archives"
        archive_dir.mkdir(parents=True, exist_ok=True)
        dst = archive_dir / full_effort.name
        full_effort.rename(dst)
        pipeline_logger.log_event(None, "vault_move", {
            "src": str(full_effort.relative_to(VAULT_PATH)) if full_effort.is_relative_to(VAULT_PATH) else str(full_effort),
            "dst": str(dst.relative_to(VAULT_PATH)) if dst.is_relative_to(VAULT_PATH) else str(dst),
            "actor": "librarian.after_deploy",
        })
    else:
        for status_dir in ["On", "Ongoing", "Simmering"]:
            candidate_dir = VAULT_PATH / "Efforts" / status_dir
            if candidate_dir.exists():
                for md in candidate_dir.glob("*.md"):
                    if slug.lower() in md.stem.lower():
                        archive_dir = VAULT_PATH / "Efforts" / "Archives"
                        archive_dir.mkdir(parents=True, exist_ok=True)
                        dst = archive_dir / md.name
                        md.rename(dst)
                        pipeline_logger.log_event(None, "vault_move", {
                            "src": str(md.relative_to(VAULT_PATH)) if md.is_relative_to(VAULT_PATH) else str(md),
                            "dst": str(dst.relative_to(VAULT_PATH)) if dst.is_relative_to(VAULT_PATH) else str(dst),
                            "actor": "librarian.after_deploy",
                        })
                        break

    if index:
        try:
            from server.obsidian_indexer import index_single_file
            if full_moc.exists():
                index_single_file(full_moc)
        except Exception as exc:
            logging.getLogger(__name__).debug("bibliotecario: indexing skipped — %s", exc)


def after_design(slug: str, guide_path: str, manifest_str: str, moc_path: str, index: bool = True) -> None:
    """Pos-design: salva manifest JSON, atualiza MOC com link pro guia."""
    today = date.today().isoformat()
    manifest_relpath = f"Atlas/Utilities/Designer/{today}-{slug}-manifest.json"
    full_manifest = VAULT_PATH / manifest_relpath
    full_manifest.parent.mkdir(parents=True, exist_ok=True)
    full_manifest.write_text(manifest_str, encoding="utf-8")
    pipeline_logger.log_event(None, "vault_write", {
        "path": str(full_manifest.relative_to(VAULT_PATH)) if full_manifest.is_relative_to(VAULT_PATH) else str(full_manifest),
        "agent_id": "bibliotecario",
        "ace_type": "atlas",
    })

    full_moc = VAULT_PATH / moc_path
    if full_moc.exists():
        text = full_moc.read_text(encoding="utf-8")
        guide_link = f"[[{guide_path.replace('.md', '')}]]"
        manifest_link = f"[[{manifest_relpath.replace('.json', '')}|asset_manifest]]"
        if "## Design" in text and guide_link not in text:
            insert = f"## Design\n- {guide_link}\n- Manifest: {manifest_link}\n"
            text = text.replace("## Design\n", insert)
            full_moc.write_text(text, encoding="utf-8")
            pipeline_logger.log_event(None, "vault_write", {
                "path": str(full_moc.relative_to(VAULT_PATH)) if full_moc.is_relative_to(VAULT_PATH) else str(full_moc),
                "agent_id": "bibliotecario",
                "ace_type": "atlas",
            })

    if index:
        try:
            from server.obsidian_indexer import index_single_file
            index_single_file(full_manifest)
        except Exception as exc:
            logging.getLogger(__name__).debug("after_design indexing skipped — %s", exc)


def after_assets(slug: str, resolved_manifest: dict, project_dir: str, moc_path: str, index: bool = True) -> None:
    """Pos-assets: cria notas listando PNGs e GLBs, atualiza MOC."""
    today = date.today().isoformat()
    images = resolved_manifest.get("images", [])

    # ImageArtist note
    img_lines = ["| id | png_path | purpose |", "|---|---|---|"]
    for it in images:
        img_lines.append(f"| {it.get('id', '')} | `{it.get('png_path', '')}` | {it.get('purpose', '')} |")
    img_content = "\n".join(img_lines)

    img_relpath = f"Atlas/Utilities/ImageArtist/{today}-{slug}-assets.md"
    img_full = VAULT_PATH / img_relpath
    img_full.parent.mkdir(parents=True, exist_ok=True)
    from server.vault_writer import build_frontmatter
    fm_img = build_frontmatter("image_artist", "resources", tags=["assets", slug])
    img_full.write_text(f"---\n{fm_img}---\n\n# Assets PNG: {slug}\n\n{img_content}", encoding="utf-8")
    pipeline_logger.log_event(None, "vault_write", {
        "path": str(img_full.relative_to(VAULT_PATH)) if img_full.is_relative_to(VAULT_PATH) else str(img_full),
        "agent_id": "image_artist",
        "ace_type": "resources",
    })

    # 3D Artist note
    glb_items = [it for it in images if it.get("glb_path")]
    glb_lines = ["| id | glb_path | source_png |", "|---|---|---|"]
    for it in glb_items:
        glb_lines.append(f"| {it.get('id', '')} | `{it.get('glb_path', '')}` | `{it.get('png_path', '')}` |")
    glb_content = "\n".join(glb_lines) if glb_items else "_(nenhum modelo 3D gerado)_"

    glb_relpath = f"Atlas/Utilities/3DArtist/{today}-{slug}-models.md"
    glb_full = VAULT_PATH / glb_relpath
    glb_full.parent.mkdir(parents=True, exist_ok=True)
    fm_glb = build_frontmatter("agente_3d", "resources", tags=["assets-3d", slug])
    glb_full.write_text(f"---\n{fm_glb}---\n\n# Modelos 3D: {slug}\n\n{glb_content}", encoding="utf-8")
    pipeline_logger.log_event(None, "vault_write", {
        "path": str(glb_full.relative_to(VAULT_PATH)) if glb_full.is_relative_to(VAULT_PATH) else str(glb_full),
        "agent_id": "agente_3d",
        "ace_type": "resources",
    })

    # MOC update
    full_moc = VAULT_PATH / moc_path
    if full_moc.exists():
        text = full_moc.read_text(encoding="utf-8")
        img_link = f"[[{img_relpath.replace('.md', '')}|Lista de PNGs]]"
        glb_link = f"[[{glb_relpath.replace('.md', '')}|Lista de GLBs]]"
        if "## Imagens" in text and img_link not in text:
            text = text.replace("## Imagens\n", f"## Imagens\n- {img_link}\n")
        if "## Modelos 3D" in text and glb_link not in text:
            text = text.replace("## Modelos 3D\n", f"## Modelos 3D\n- {glb_link}\n")
        full_moc.write_text(text, encoding="utf-8")
        pipeline_logger.log_event(None, "vault_write", {
            "path": str(full_moc.relative_to(VAULT_PATH)) if full_moc.is_relative_to(VAULT_PATH) else str(full_moc),
            "agent_id": "bibliotecario",
            "ace_type": "atlas",
        })

    if index:
        try:
            from server.obsidian_indexer import index_single_file
            index_single_file(img_full)
            index_single_file(glb_full)
        except Exception as exc:
            logging.getLogger(__name__).debug("after_assets indexing skipped — %s", exc)


def context_query(question: str) -> str:
    """Busca semantica no vault para perguntas de contexto sobre projetos anteriores."""
    from server.vault_tool import get_vault_tool
    tool = get_vault_tool()
    return tool._run(question)


def _judge_call(prompt: str) -> str:
    """Chama LLM julgador. Use o llm rapido (mesmo do crew) — gemma local seria ideal."""
    from .agents import llm
    return llm.call(messages=[{"role": "user", "content": prompt}])


JUDGE_PROMPT_TEMPLATE = """Voce e o bibliotecario do vault Ideaverse. Decida se a nota
abaixo deve ser indexada no Qdrant pra busca semantica em projetos futuros.

Criterios SAVE (qualquer um):
- Padrao novo do segmento
- Stack inedita usada
- Problema nao-trivial resolvido
- Insight de mercado especifico
- Referencia visual rara/SOTW

Criterios SKIP (qualquer um):
- Padrao generico ja comum no vault
- Aprendizado obvio
- Dossie fraco sem Frankenstein claro
- Asset list generico sem proposito narrativo

Tipo do artifact: {artifact_type}
Contexto: {context}
Resumo do conteudo:
{content_summary}

Devolva APENAS JSON estrito (sem markdown, sem hedge):
{{"save": bool, "ace_type": "atlas"|"resources", "tags": [str], "priority": "high"|"medium"|"low", "reason": "...", "summary": "..."}}
"""


def judge_artifact(artifact_type: str, content_summary: str, context: dict) -> dict:
    """Decide se um artifact deve ser indexado no Qdrant. Retorna dict com decisao."""
    import json as _json

    prompt = JUDGE_PROMPT_TEMPLATE.format(
        artifact_type=artifact_type,
        context=_json.dumps(context, ensure_ascii=False),
        content_summary=content_summary[:2000],
    )
    raw = _judge_call(prompt)
    try:
        decision = _json.loads(raw.strip())
        decision.setdefault("save", True)
        decision.setdefault("ace_type", "atlas")
        decision.setdefault("tags", [])
        decision.setdefault("priority", "medium")
        decision.setdefault("reason", "")
        decision.setdefault("summary", "")
        return decision
    except _json.JSONDecodeError:
        return {
            "save": True,
            "ace_type": "atlas",
            "tags": [],
            "priority": "medium",
            "reason": "fallback: judge LLM malformed JSON; default save=True",
            "summary": content_summary[:500],
        }


def _summarize_research(refs: dict) -> str:
    """Resumo curto pro judge: segmento + Frankenstein highlights."""
    seg = refs.get("segment", "?")
    n_insp = len(refs.get("inspirational", []))
    n_comp = len(refs.get("competitors", []))
    frank = refs.get("frankenstein", {})
    frank_str = ", ".join(f"{k}={v.get('from_ref','?')}" for k, v in frank.items())
    return f"segmento={seg}, inspiracionais={n_insp}, competidores={n_comp}, frankenstein=[{frank_str}]"


def after_research(slug: str, references_path: str, moc_path: str, index: bool = True) -> None:
    """Pos-research: MOC sempre, nota Atlas gated por judge_artifact."""
    import json as _json

    refs = _json.loads(Path(references_path).read_text(encoding="utf-8"))

    full_moc = VAULT_PATH / moc_path
    if full_moc.exists():
        text = full_moc.read_text(encoding="utf-8")
        link = f"- [Refs JSON]({references_path})"
        if "## Pesquisa" in text and link not in text:
            text = text.replace("## Pesquisa\n", f"## Pesquisa\n{link}\n")
            full_moc.write_text(text, encoding="utf-8")
            pipeline_logger.log_event(None, "vault_write", {
                "path": str(full_moc.relative_to(VAULT_PATH)) if full_moc.is_relative_to(VAULT_PATH) else str(full_moc),
                "agent_id": "bibliotecario",
                "ace_type": "atlas",
            })

    summary = _summarize_research(refs)
    decision = judge_artifact("research", summary, {"slug": slug, "segment": refs.get("segment", "")})

    if not decision["save"]:
        pipeline_logger.log_event(None, "librarian_skipped", {
            "artifact": "research", "slug": slug, "reason": decision["reason"]
        })
        return

    today = date.today().isoformat()
    note_relpath = f"Atlas/Utilities/Researcher/{today}-{slug}-references.md"
    full_note = VAULT_PATH / note_relpath
    full_note.parent.mkdir(parents=True, exist_ok=True)

    from server.vault_writer import build_frontmatter
    fm = build_frontmatter("researcher", decision["ace_type"], tags=["pesquisa", slug] + decision["tags"])

    lines = [f"---\n{fm}---\n", f"# Pesquisa: {slug}\n",
             f"**Segmento:** {refs.get('segment','?')}\n",
             f"**Prioridade:** {decision['priority']}\n",
             f"**Resumo:** {decision['summary']}\n",
             "## Inspiracionais"]
    for r in refs.get("inspirational", []):
        lines.append(f"- [{r.get('title','?')}]({r.get('url','')}) — `{r.get('ref_id','?')}`")
    lines.append("\n## Competidores")
    for r in refs.get("competitors", []):
        lines.append(f"- [{r.get('title','?')}]({r.get('url','')}) — `{r.get('ref_id','?')}`")
    lines.append("\n## Frankenstein")
    for k, v in refs.get("frankenstein", {}).items():
        lines.append(f"- **{k}**: `{v.get('from_ref','?')}` — {v.get('why','')}")

    full_note.write_text("\n".join(lines), encoding="utf-8")

    pipeline_logger.log_event(None, "librarian_kept", {
        "artifact": "research", "slug": slug,
        "priority": decision["priority"], "reason": decision["reason"],
        "path": note_relpath,
    })

    if index:
        try:
            from server.obsidian_indexer import index_single_file
            index_single_file(full_note)
        except Exception as exc:
            logging.getLogger(__name__).debug("after_research indexing skipped — %s", exc)


def _summarize_qa_visual(report: list) -> str:
    if not report:
        return "report vazio"
    n = len(report)
    n_repr = sum(1 for r in report if r.get("verdict") == "REPROVADO")
    issues_top = []
    for r in report:
        for i in r.get("issues", [])[:1]:
            issues_top.append(f"[{r.get('section','?')}] {i}")
        if len(issues_top) >= 3:
            break
    return f"secoes={n}, reprovadas={n_repr}, top_issues={'; '.join(issues_top)}"


def after_qa_visual(slug: str, report_path: str, screenshots_dir: str,
                    moc_path: str, index: bool = True) -> None:
    """Pos-QA-visual: MOC sempre, nota Atlas gated por judge_artifact."""
    import json as _json

    report = _json.loads(Path(report_path).read_text(encoding="utf-8"))

    full_moc = VAULT_PATH / moc_path
    if full_moc.exists():
        text = full_moc.read_text(encoding="utf-8")
        link = f"- [Report QA visual]({report_path})"
        if "## QA Visual" in text and link not in text:
            text = text.replace("## QA Visual\n", f"## QA Visual\n{link}\n")
            full_moc.write_text(text, encoding="utf-8")
            pipeline_logger.log_event(None, "vault_write", {
                "path": str(full_moc.relative_to(VAULT_PATH)) if full_moc.is_relative_to(VAULT_PATH) else str(full_moc),
                "agent_id": "bibliotecario",
                "ace_type": "atlas",
            })

    summary = _summarize_qa_visual(report)
    decision = judge_artifact("qa_visual", summary, {"slug": slug})

    if not decision["save"]:
        pipeline_logger.log_event(None, "librarian_skipped", {
            "artifact": "qa_visual", "slug": slug, "reason": decision["reason"]
        })
        return

    today = date.today().isoformat()
    note_relpath = f"Atlas/Utilities/QA-Visual/{today}-{slug}-review.md"
    full_note = VAULT_PATH / note_relpath
    full_note.parent.mkdir(parents=True, exist_ok=True)

    from server.vault_writer import build_frontmatter
    fm = build_frontmatter("qa_visual", decision["ace_type"], tags=["qa-visual", slug] + decision["tags"])

    lines = [f"---\n{fm}---\n", f"# QA Visual: {slug}\n",
             f"**Prioridade:** {decision['priority']}\n",
             f"**Resumo:** {decision['summary']}\n",
             f"**Screenshots:** {screenshots_dir}\n",
             "## Veredicto por secao",
             "| Secao | Veredicto | Issues |", "|---|---|---|"]
    for r in report:
        issues = "<br>".join(r.get("issues", []))
        lines.append(f"| {r.get('section','?')} | {r.get('verdict','?')} | {issues} |")

    full_note.write_text("\n".join(lines), encoding="utf-8")

    pipeline_logger.log_event(None, "librarian_kept", {
        "artifact": "qa_visual", "slug": slug,
        "priority": decision["priority"], "reason": decision["reason"],
        "path": note_relpath,
    })

    if index:
        try:
            from server.obsidian_indexer import index_single_file
            index_single_file(full_note)
        except Exception as exc:
            logging.getLogger(__name__).debug("after_qa_visual indexing skipped — %s", exc)
