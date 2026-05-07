import time

import pytest


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB_PATH", str(tmp_path / "test.db"))
    import importlib
    from server import db, agent_messages
    importlib.reload(db)
    importlib.reload(agent_messages)
    db.init_schema()
    yield agent_messages


def test_record_inserts_and_returns_id(temp_db, monkeypatch):
    emitted = []
    monkeypatch.setattr("server.event_bus.emit",
                        lambda kind, payload: emitted.append((kind, payload)))

    msg_id = temp_db.record("rose-beauty", "researcher", "say", "Pesquisa pronta.")
    assert msg_id > 0
    assert len(emitted) == 1
    assert emitted[0][0] == "agent_message"
    payload = emitted[0][1]
    import json
    p = json.loads(payload) if isinstance(payload, str) else payload
    assert p["agent_id"] == "researcher"
    assert p["type"] == "say"


def test_history_returns_chronological_asc(temp_db):
    base = time.time()
    temp_db.record("x", "researcher", "whisper", "msg1")
    time.sleep(0.01)
    temp_db.record("x", "researcher", "say", "msg2")
    time.sleep(0.01)
    temp_db.record("x", "designer", "say", "msg3")

    hist = temp_db.history("researcher")
    assert len(hist) == 2
    assert hist[0]["text"] == "msg1"
    assert hist[1]["text"] == "msg2"


def test_history_respects_limit(temp_db):
    for i in range(10):
        temp_db.record("x", "a", "say", f"msg{i}")
    hist = temp_db.history("a", limit=5)
    assert len(hist) == 5
    assert hist[0]["text"] == "msg5"
    assert hist[-1]["text"] == "msg9"


def test_recent_filters_by_slug_and_since(temp_db):
    temp_db.record("a", "x", "say", "old")
    cutoff = time.time()
    time.sleep(0.01)
    temp_db.record("a", "x", "say", "new1")
    temp_db.record("b", "x", "say", "other-slug")

    out = temp_db.recent("a", since_ts=cutoff)
    assert len(out) == 1
    assert out[0]["text"] == "new1"
