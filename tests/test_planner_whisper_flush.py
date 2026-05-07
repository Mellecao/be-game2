import pytest


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB_PATH", str(tmp_path / "test.db"))
    import importlib
    from server import db, agent_messages
    importlib.reload(db)
    importlib.reload(agent_messages)
    db.init_schema()
    return agent_messages


def test_whisper_buffer_accumulates_and_flushes(temp_db, monkeypatch):
    from server import planner_loop
    monkeypatch.setattr("server.event_bus.emit", lambda *a, **kw: None)

    planner_loop._whisper_buffer_clear()
    planner_loop._whisper_buffer_append("researcher", "rose-beauty", "Buscando ")
    planner_loop._whisper_buffer_append("researcher", "rose-beauty", "refs no awwwards...")

    assert len(temp_db.history("researcher")) == 0

    planner_loop._whisper_buffer_flush("researcher", "rose-beauty")
    msgs = temp_db.history("researcher")
    assert len(msgs) == 1
    assert msgs[0]["type"] == "whisper"
    assert "Buscando refs no awwwards" in msgs[0]["text"]


def test_whisper_buffer_independent_per_agent(temp_db, monkeypatch):
    from server import planner_loop
    monkeypatch.setattr("server.event_bus.emit", lambda *a, **kw: None)

    planner_loop._whisper_buffer_clear()
    planner_loop._whisper_buffer_append("researcher", "x", "abc")
    planner_loop._whisper_buffer_append("designer", "x", "xyz")

    planner_loop._whisper_buffer_flush("researcher", "x")
    planner_loop._whisper_buffer_flush("designer", "x")

    r = temp_db.history("researcher")
    d = temp_db.history("designer")
    assert r[0]["text"] == "abc"
    assert d[0]["text"] == "xyz"


def test_whisper_buffer_flush_empty_is_noop(temp_db, monkeypatch):
    from server import planner_loop
    monkeypatch.setattr("server.event_bus.emit", lambda *a, **kw: None)
    planner_loop._whisper_buffer_clear()
    planner_loop._whisper_buffer_flush("nobody", "x")
    assert temp_db.history("nobody") == []
