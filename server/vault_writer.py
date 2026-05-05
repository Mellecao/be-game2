# server/vault_writer.py
"""
Escrita direta de arquivos .md no vault Obsidian.
Usado pelo pipeline — bypassa o HTTP /api/vault/knowledge.
"""
from __future__ import annotations

import os
import re
import unicodedata
from datetime import date
from pathlib import Path

import yaml

VAULT_PATH = Path(os.getenv("OBSIDIAN_VAULT_PATH", r"C:\Users\v27me\OneDrive\Desktop\Ideaverse"))

_ACE_UP = {
    "atlas":     "[[Black Elephant MOC]]",
    "calendar":  "[[Calendar]]",
    "cards":     "[[Cards MOC]]",
    "efforts":   "[[Efforts]]",
    "resources": "[[Utilities]]",
    "sources":   "[[Sources]]",
}


def make_slug(text: str) -> str:
    """Converte texto arbitrário em kebab-case ASCII."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text


def build_frontmatter(
    agent_id: str,
    ace_type: str,
    tags: list[str] | None = None,
    extra: dict | None = None,
) -> str:
    """Gera string YAML de frontmatter padrão."""
    fm: dict = {
        "up":      [_ACE_UP.get(ace_type, "[[Black Elephant MOC]]")],
        "agent":   agent_id,
        "tags":    ["agente", agent_id] + (tags or []),
        "created": str(date.today()),
    }
    if extra:
        fm.update(extra)
    return yaml.dump(fm, allow_unicode=True, default_flow_style=False)


def write_note(
    *,
    relative_path: str,
    title: str,
    content: str,
    agent_id: str,
    ace_type: str,
    tags: list[str] | None = None,
    extra_frontmatter: dict | None = None,
    index: bool = True,
) -> Path:
    """
    Escreve arquivo .md no vault com frontmatter padrão.
    Cria diretórios automaticamente.
    Se o arquivo já existir, adiciona sufixo timestamp para não sobrescrever.
    Se index=True, chama index_single_file (requer Qdrant online).
    Retorna o Path absoluto do arquivo escrito.
    """
    full = VAULT_PATH / relative_path
    full.parent.mkdir(parents=True, exist_ok=True)

    if full.exists():
        stem   = full.stem
        suffix = full.suffix
        import time
        ts     = str(int(time.time()))[-6:]
        full   = full.parent / f"{stem}-{ts}{suffix}"

    fm    = build_frontmatter(agent_id, ace_type, tags, extra_frontmatter)
    body  = f"---\n{fm}---\n\n# {title}\n\n{content}"
    full.write_text(body, encoding="utf-8")

    if index:
        from server.obsidian_indexer import index_single_file
        try:
            index_single_file(full)
        except Exception:
            pass  # Qdrant offline não bloqueia escrita

    return full
