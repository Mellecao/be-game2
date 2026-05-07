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
    return agent_messages


def test_pipeline_status_returns_active_tasks(monkeypatch):
    from server import agent_messages_tools

    fake_tasks = [
        {"id": "t1", "card_name": "Rose Beauty", "status": "designing", "step": 4, "log": "Designer working..."},
    ]
    monkeypatch.setattr(agent_messages_tools, "_get_tasks_fn", lambda: fake_tasks)

    tool = agent_messages_tools.GetPipelineStatusTool()
    out = tool._run()
    assert "Rose Beauty" in out
    assert "designing" in out


def test_active_tasks_returns_summary(monkeypatch):
    from server import agent_messages_tools

    fake_tasks = [
        {"id": "t1", "card_name": "A", "status": "developing", "step": 7, "log": "Dev"},
        {"id": "t2", "card_name": "B", "status": "qa_crew", "step": 9, "log": "QA"},
    ]
    monkeypatch.setattr(agent_messages_tools, "_get_tasks_fn", lambda: fake_tasks)

    tool = agent_messages_tools.GetActiveTasksTool()
    out = tool._run()
    assert "2" in out
    assert "A" in out and "B" in out


def test_agent_history_returns_text_block(temp_db, monkeypatch):
    monkeypatch.setattr("server.event_bus.emit", lambda *a, **kw: None)
    temp_db.record("x", "researcher", "say", "Pesquisa pronta.")
    temp_db.record("x", "researcher", "whisper", "Buscando refs...")

    from server import agent_messages_tools
    tool = agent_messages_tools.GetAgentHistoryTool()
    out = tool._run(agent_id="researcher", limit=10)
    assert "Pesquisa pronta" in out
    assert "Buscando refs" in out


def test_agent_history_handles_unknown_agent(temp_db):
    from server import agent_messages_tools
    tool = agent_messages_tools.GetAgentHistoryTool()
    out = tool._run(agent_id="ghost")
    assert "(sem mensagens)" in out or out.strip() == ""
