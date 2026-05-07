import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB_PATH", str(tmp_path / "test.db"))
    import importlib
    from server import db, agent_messages
    importlib.reload(db)
    importlib.reload(agent_messages)
    db.init_schema()
    from server import api
    importlib.reload(api)
    return TestClient(api.app)


def test_chat_secretario_returns_reply(client, monkeypatch):
    from server import api
    class FakeCrew:
        def __init__(self, *a, **kw): pass
        def kickoff(self):
            return "Pipeline ok, 1 card em design."
    monkeypatch.setattr(api, "Crew", FakeCrew)

    r = client.post("/api/chat/secretario", json={"message": "como ta o pipeline?"})
    assert r.status_code == 200
    body = r.json()
    assert "reply" in body
    assert "Pipeline" in body["reply"]


def test_chat_secretario_records_player_and_reply(client, monkeypatch):
    from server import api, agent_messages
    class FakeCrew:
        def __init__(self, *a, **kw): pass
        def kickoff(self): return "Resposta X"
    monkeypatch.setattr(api, "Crew", FakeCrew)

    client.post("/api/chat/secretario", json={"message": "hello"})

    from server import db
    with db.get_conn() as c:
        rows = c.execute("SELECT type, text FROM agent_messages ORDER BY ts").fetchall()
    types = [r["type"] for r in rows]
    assert "player" in types
    assert "reply" in types


def test_chat_bibliotecario_returns_reply(client, monkeypatch):
    from server import api
    class FakeCrew:
        def __init__(self, *a, **kw): pass
        def kickoff(self): return "Encontrei no vault."
    monkeypatch.setattr(api, "Crew", FakeCrew)

    r = client.post("/api/chat/bibliotecario", json={"message": "ja fizemos pricing saas?"})
    assert r.status_code == 200
    assert "reply" in r.json()


def test_get_agent_messages_returns_history(client, monkeypatch):
    from server import agent_messages
    monkeypatch.setattr("server.event_bus.emit", lambda *a, **kw: None)
    agent_messages.record("x", "researcher", "say", "msg1")
    agent_messages.record("x", "researcher", "say", "msg2")

    r = client.get("/api/agents/researcher/messages?limit=10")
    assert r.status_code == 200
    body = r.json()
    assert "messages" in body
    assert len(body["messages"]) == 2
    assert body["messages"][0]["text"] == "msg1"


def test_chat_secretario_rejects_empty_message(client):
    r = client.post("/api/chat/secretario", json={"message": ""})
    assert r.status_code == 400
