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


def test_emit_agent_step_records_say_with_handoff(temp_db, monkeypatch):
    from server import planner_loop, handoff
    monkeypatch.setattr("server.event_bus.emit", lambda *a, **kw: None)
    monkeypatch.setattr(handoff, "_call_llm", lambda p: "Pesquisa pronta, passando pro Copy.")
    handoff._generate_cached.cache_clear()

    planner_loop._emit_agent_step("researcher", "Researcher", "5 refs no Frankenstein", "copywriter", "rose-beauty")

    msgs = temp_db.history("researcher")
    assert len(msgs) == 1
    assert msgs[0]["type"] == "say"
    assert "Copy" in msgs[0]["text"]


def test_emit_agent_step_flushes_whisper_first(temp_db, monkeypatch):
    from server import planner_loop, handoff
    monkeypatch.setattr("server.event_bus.emit", lambda *a, **kw: None)
    monkeypatch.setattr(handoff, "_call_llm", lambda p: "fim")
    handoff._generate_cached.cache_clear()
    planner_loop._whisper_buffer_clear()

    planner_loop._whisper_buffer_append("designer", "x", "Pensando no manifest...")
    planner_loop._emit_agent_step("designer", "Designer", "manifest pronto", "image_artist", "x")

    msgs = temp_db.history("designer")
    types = [m["type"] for m in msgs]
    assert "whisper" in types
    assert "say" in types
    assert types.index("whisper") < types.index("say")
