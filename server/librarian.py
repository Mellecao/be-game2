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
