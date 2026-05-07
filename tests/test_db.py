import os
from pathlib import Path

import pytest


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB_PATH", str(tmp_path / "test.db"))
    import importlib
    from server import db
    importlib.reload(db)
    db.init_schema()
    yield db


def test_init_schema_creates_table(temp_db):
    with temp_db.get_conn() as c:
        cur = c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='agent_messages'")
        assert cur.fetchone() is not None


def test_init_schema_creates_indexes(temp_db):
    with temp_db.get_conn() as c:
        cur = c.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='agent_messages'")
        names = {row[0] for row in cur.fetchall()}
        assert "idx_am_agent" in names
        assert "idx_am_slug" in names


def test_get_conn_returns_row_factory(temp_db):
    with temp_db.get_conn() as c:
        c.execute("INSERT INTO agent_messages (slug, agent_id, type, text, ts) VALUES (?, ?, ?, ?, ?)",
                  ("x", "researcher", "say", "hello", 1.0))
        row = c.execute("SELECT * FROM agent_messages").fetchone()
        assert row["agent_id"] == "researcher"
