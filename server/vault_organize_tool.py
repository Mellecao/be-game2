"""Tool CrewAI para listar/ler/mover/apagar arquivos no vault e em output/.

Restringe operações a roots permitidos. Bloqueia path traversal, .git e
paths absolutos fora dos roots.
"""
from __future__ import annotations

import os
from pathlib import Path

from crewai.tools import BaseTool
from pydantic import Field

from . import pipeline_logger

_DEFAULT_VAULT = r"C:\Users\v27me\OneDrive\Desktop\Ideaverse"


def _vault_path() -> Path:
    """Lê OBSIDIAN_VAULT_PATH do ambiente em tempo de execução (não em import)."""
    return Path(os.getenv("OBSIDIAN_VAULT_PATH", _DEFAULT_VAULT))


def _allowed_roots() -> list[Path]:
    roots = [_vault_path().resolve()]
    slug = pipeline_logger.get_active_slug()
    if slug:
        roots.append((Path("output") / slug).resolve())
    return roots


def _contains_git_component(path_str: str) -> bool:
    """Retorna True se qualquer componente do path for '.git'."""
    normalized = path_str.replace("\\", "/")
    parts = normalized.split("/")
    return ".git" in parts


def _resolve_safe(path_str: str) -> Path | None:
    """Resolve path relativo a um dos roots; retorna None se inválido."""
    if not path_str:
        return None

    # Bloqueia qualquer path que contenha .git como componente
    if _contains_git_component(path_str):
        return None

    roots = _allowed_roots()
    p = Path(path_str)

    candidates: list[Path] = []
    if p.is_absolute():
        # Para path absoluto, resolve diretamente
        candidates.append(p.resolve())
    else:
        # Para path relativo, tenta contra cada root
        for root in roots:
            candidates.append((root / path_str).resolve())

    for cand in candidates:
        for root in roots:
            try:
                cand.relative_to(root)
                return cand
            except ValueError:
                continue
    return None


class VaultOrganizeTool(BaseTool):
    name: str = "vault_organize"
    description: str = (
        "Lista, le, move ou apaga arquivos no vault Obsidian ou na pasta output do projeto ativo. "
        "Argumentos: op (list|read|move|delete), path, src, dst, reason. "
        "Bloqueia paths fora dos roots permitidos e diretorios .git. "
        "Operacoes destrutivas exigem reason."
    )

    def _run(
        self,
        op: str,
        path: str | None = None,
        src: str | None = None,
        dst: str | None = None,
        reason: str | None = None,
    ) -> str:
        if op == "list":
            return self._list(path or "")
        if op == "read":
            return self._read(path or "")
        if op == "move":
            return self._move(src or "", dst or "")
        if op == "delete":
            return self._delete(path or "", reason or "")
        return f"Erro: op desconhecida '{op}'. Use list|read|move|delete."

    def _list(self, path: str) -> str:
        if path:
            target = _resolve_safe(path)
        else:
            target = _allowed_roots()[0]
        if target is None:
            return f"Erro: path bloqueado: '{path}'"
        if not target.exists():
            return f"Erro: path nao existe: '{path}'"
        if not target.is_dir():
            return f"Erro: path nao e diretorio: '{path}'"
        items = [f.name + ("/" if f.is_dir() else "") for f in sorted(target.iterdir())]
        return "\n".join(items) if items else "(diretorio vazio)"

    def _read(self, path: str) -> str:
        target = _resolve_safe(path)
        if target is None:
            return f"Erro: path bloqueado: '{path}'"
        if not target.exists():
            return f"Erro: arquivo nao existe: '{path}'"
        if not target.is_file():
            return f"Erro: path nao e arquivo: '{path}'"
        try:
            return target.read_text(encoding="utf-8")[:8000]
        except Exception as e:
            return f"Erro ao ler: {e}"

    def _move(self, src: str, dst: str) -> str:
        src_p = _resolve_safe(src)
        dst_p = _resolve_safe(dst)
        if src_p is None:
            return f"Erro: src bloqueado: '{src}'"
        if dst_p is None:
            return f"Erro: dst bloqueado: '{dst}'"
        if not src_p.exists():
            return f"Erro: src nao existe: '{src}'"
        if dst_p.exists():
            return f"Erro: dst ja existe: '{dst}' (use delete antes ou outro nome)"
        dst_p.parent.mkdir(parents=True, exist_ok=True)
        src_p.rename(dst_p)
        pipeline_logger.log_event(None, "vault_move", {"src": src, "dst": dst, "actor": "bibliotecario"})
        return f"OK: movido '{src}' -> '{dst}'"

    def _delete(self, path: str, reason: str) -> str:
        if not reason:
            return "Erro: delete requer reason"
        target = _resolve_safe(path)
        if target is None:
            return f"Erro: path bloqueado: '{path}'"
        if not target.exists():
            return f"OK: arquivo ja nao existe: '{path}'"
        if not target.is_file():
            return f"Erro: nao deleta diretorios: '{path}'"
        target.unlink()
        pipeline_logger.log_event(None, "vault_delete", {"path": path, "reason": reason, "actor": "bibliotecario"})
        return f"OK: deletado '{path}' (motivo: {reason})"
