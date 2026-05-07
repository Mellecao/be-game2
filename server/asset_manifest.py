# server/asset_manifest.py
"""Parse + persist do asset_manifest emitido pelo Designer."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

_FENCE_RE = re.compile(r"```asset_manifest\s*\n(.*?)\n```", re.DOTALL)
_log = logging.getLogger(__name__)


def parse_manifest(designer_output: str) -> dict:
    """Extrai bloco asset_manifest do markdown do Designer.
    Retorna {"images": []} em qualquer falha (parse, ausencia, JSON invalido)."""
    if not designer_output:
        return {"images": []}
    m = _FENCE_RE.search(designer_output)
    if not m:
        _log.warning("asset_manifest: bloco nao encontrado no output do Designer")
        return {"images": []}
    raw = m.group(1).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        _log.warning("asset_manifest: JSON invalido: %s", e)
        return {"images": []}
    if not isinstance(data, dict) or "images" not in data:
        _log.warning("asset_manifest: estrutura invalida (esperado dict com 'images')")
        return {"images": []}
    return data


def _resolved_path(slug: str) -> Path:
    return Path("output") / slug / "assets" / "manifest_resolved.json"


def write_resolved(slug: str, manifest: dict) -> Path:
    path = _resolved_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def read_resolved(slug: str) -> dict:
    path = _resolved_path(slug)
    if not path.exists():
        return {"images": []}
    return json.loads(path.read_text(encoding="utf-8"))
