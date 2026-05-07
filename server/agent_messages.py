"""Helpers de leitura/escrita de agent_messages + emite SSE."""
from __future__ import annotations

import json
import time
from typing import Any

from . import db
from . import event_bus


def record(slug: str, agent_id: str, type: str, text: str) -> int:
    """Insere msg + emite SSE 'agent_message'. Retorna id da row."""
    ts = time.time()
    with db.get_conn() as c:
        cur = c.execute(
            "INSERT INTO agent_messages (slug, agent_id, type, text, ts) VALUES (?, ?, ?, ?, ?)",
            (slug, agent_id, type, text, ts),
        )
        msg_id = cur.lastrowid

    payload = json.dumps({
        "id": msg_id,
        "slug": slug,
        "agent_id": agent_id,
        "type": type,
        "text": text,
        "ts": ts,
    }, ensure_ascii=False)
    event_bus.emit("agent_message", payload)
    return msg_id


def history(agent_id: str, limit: int = 200) -> list[dict[str, Any]]:
    """Ultimas N msgs do agente, ordem cronologica asc."""
    with db.get_conn() as c:
        rows = c.execute(
            "SELECT * FROM (SELECT * FROM agent_messages WHERE agent_id = ? ORDER BY ts DESC LIMIT ?) "
            "ORDER BY ts ASC",
            (agent_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def recent(slug: str, since_ts: float, limit: int = 100) -> list[dict[str, Any]]:
    """Msgs do projeto desde timestamp."""
    with db.get_conn() as c:
        rows = c.execute(
            "SELECT * FROM agent_messages WHERE slug = ? AND ts >= ? ORDER BY ts ASC LIMIT ?",
            (slug, since_ts, limit),
        ).fetchall()
    return [dict(r) for r in rows]
