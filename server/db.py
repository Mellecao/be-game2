"""SQLite connection + schema init para agent_messages."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def _db_path() -> Path:
    return Path(os.environ.get("AGENT_DB_PATH", "agent_messages.db"))


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path()))
    conn.row_factory = sqlite3.Row
    return conn


def init_schema() -> None:
    with get_conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS agent_messages (
              id          INTEGER PRIMARY KEY AUTOINCREMENT,
              slug        TEXT NOT NULL,
              agent_id    TEXT NOT NULL,
              type        TEXT NOT NULL,
              text        TEXT NOT NULL,
              ts          REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_am_agent ON agent_messages(agent_id, ts DESC);
            CREATE INDEX IF NOT EXISTS idx_am_slug  ON agent_messages(slug, ts DESC);
        """)
