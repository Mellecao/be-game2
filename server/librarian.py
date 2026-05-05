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

    full_moc = VAULT_PATH / moc_path
    if full_moc.exists():
        text = full_moc.read_text(encoding="utf-8")
        link = f"[[{learnings_path.replace('.md', '')}]]"
        if "## Dev" in text and link not in text:
            text = text.replace("## Dev\n", f"## Dev\n- {link}\n")
            full_moc.write_text(text, encoding="utf-8")

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
    index: bool = True,
) -> None:
    """Intervencao pos-deploy: atualiza MOC com URL, arquiva Effort."""
    full_moc = VAULT_PATH / moc_path
    if full_moc.exists():
        text = full_moc.read_text(encoding="utf-8")
        if "## Deploy" in text and github_url not in text:
            text = text.replace("## Deploy\n", f"## Deploy\n- URL: {github_url}\n")
            full_moc.write_text(text, encoding="utf-8")

    full_effort = VAULT_PATH / effort_path
    if full_effort.exists():
        archive_dir = VAULT_PATH / "Efforts" / "Archives"
        archive_dir.mkdir(parents=True, exist_ok=True)
        full_effort.rename(archive_dir / full_effort.name)
    else:
        for status_dir in ["On", "Ongoing", "Simmering"]:
            candidate_dir = VAULT_PATH / "Efforts" / status_dir
            if candidate_dir.exists():
                for md in candidate_dir.glob("*.md"):
                    if slug.lower() in md.stem.lower():
                        archive_dir = VAULT_PATH / "Efforts" / "Archives"
                        archive_dir.mkdir(parents=True, exist_ok=True)
                        md.rename(archive_dir / md.name)
                        break

    if index:
        try:
            from server.obsidian_indexer import index_single_file
            if full_moc.exists():
                index_single_file(full_moc)
        except Exception as exc:
            logging.getLogger(__name__).debug("bibliotecario: indexing skipped — %s", exc)


def context_query(question: str) -> str:
    """Busca semantica no vault para perguntas de contexto sobre projetos anteriores."""
    from server.vault_tool import get_vault_tool
    tool = get_vault_tool()
    return tool._run(question)
