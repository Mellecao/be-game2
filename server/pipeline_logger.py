"""Append-only JSONL log per pipeline task."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

_tls = threading.local()
_write_lock = threading.Lock()


def _log_path(slug: str) -> Path:
    return Path("output") / slug / ".pipeline.log"


def set_active_slug(slug: str | None) -> None:
    _tls.slug = slug


def get_active_slug() -> str | None:
    return getattr(_tls, "slug", None)


def log_event(slug: str | None, event: str, payload: dict | None = None) -> None:
    """Append one JSONL entry to output/{slug}/.pipeline.log.
    If slug is None, falls back to thread-local active slug.
    If still None, silently no-op (e.g. chat call outside pipeline).
    """
    slug = slug or get_active_slug()
    if not slug:
        return

    entry: dict = {"ts": time.time(), "event": event}
    if payload:
        entry.update(payload)

    path = _log_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with _write_lock:
        with path.open("a", encoding="utf-8") as f:
            f.write(line)


def read_log(slug: str) -> list[dict]:
    path = _log_path(slug)
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # skip corrupted lines
    return out
