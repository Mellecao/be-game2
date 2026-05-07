"""Smoke test: verifica que pipeline + handoff + chat coexistem sem crashar imports."""
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


def test_full_chat_message_flow(temp_db, monkeypatch):
    """Player envia mensagem, Secretario responde, ambas ficam no DB."""
    from server import api, agent_messages
    from fastapi.testclient import TestClient

    class FakeCrew:
        def __init__(self, *a, **kw): pass
        def kickoff(self): return "Pipeline ok, 1 card em desenvolvimento."
    monkeypatch.setattr(api, "Crew", FakeCrew)
    monkeypatch.setattr("server.event_bus.emit", lambda *a, **kw: None)

    client = TestClient(api.app)
    r = client.post("/api/chat/secretario", json={"message": "como ta?"})
    assert r.status_code == 200

    history_player = agent_messages.history("player")
    history_secretario = agent_messages.history("secretario")
    assert len(history_player) >= 1
    assert len(history_secretario) >= 1
    assert history_secretario[-1]["text"] == "Pipeline ok, 1 card em desenvolvimento."


def test_handoff_records_say_message(temp_db, monkeypatch):
    """Quando _emit_agent_step roda, gera mensagem 'say' do agente."""
    from server import planner_loop, handoff
    monkeypatch.setattr("server.event_bus.emit", lambda *a, **kw: None)
    monkeypatch.setattr(handoff, "_call_llm", lambda p: "Refs prontas, indo pro Copy.")
    handoff._generate_cached.cache_clear()

    planner_loop._emit_agent_step("researcher", "Researcher", "5 refs", "copywriter", "rose-beauty")

    msgs = temp_db.history("researcher")
    assert any(m["type"] == "say" and "Copy" in m["text"] for m in msgs)


def test_history_endpoint_after_pipeline_run(temp_db):
    """GET /api/agents/{id}/messages retorna o historico do agent_messages."""
    from server import api, agent_messages
    from fastapi.testclient import TestClient

    agent_messages.record("rose-beauty", "designer", "say", "Manifest pronto.")
    client = TestClient(api.app)
    r = client.get("/api/agents/designer/messages?limit=10")
    assert r.status_code == 200
    body = r.json()
    assert any("Manifest pronto" in m["text"] for m in body["messages"])
