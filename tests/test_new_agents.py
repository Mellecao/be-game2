def test_create_image_artist():
    from server.agents import create_image_artist
    agent = create_image_artist()
    assert agent.role
    tool_names = [t.name for t in agent.tools]
    assert "flux_image" in tool_names


def test_create_3d_artist():
    from server.agents import create_3d_artist
    agent = create_3d_artist()
    tool_names = [t.name for t in agent.tools]
    assert "hunyuan3d_generate" in tool_names


def test_create_designer_reviewer_uses_vision_llm(monkeypatch):
    monkeypatch.setenv("VISION_MODEL", "openai/gpt-4o-mini")
    from server.agents import create_designer_reviewer, vision_llm
    agent = create_designer_reviewer()
    assert agent.llm.model == vision_llm.model


def test_create_bibliotecario_has_organize_and_log_tools():
    from server.agents import create_bibliotecario
    agent = create_bibliotecario()
    names = [t.name for t in agent.tools]
    assert "vault_organize" in names
    assert "pipeline_log" in names


def test_create_researcher_returns_agent_with_tools():
    from server.agents import create_researcher
    from crewai import Agent
    agent = create_researcher()
    assert isinstance(agent, Agent)
    tool_names = {t.name for t in agent.tools}
    assert "web_search" in tool_names
    assert "awwwards_search" in tool_names
    assert "browser_capture" in tool_names
    assert "vision_analyze" in tool_names
    assert agent.role.lower().startswith("pesquisador") or "researcher" in agent.role.lower()


def test_create_qa_code_alias_exists():
    from server.agents import create_qa_code
    from crewai import Agent
    assert isinstance(create_qa_code(), Agent)


def test_create_qa_visual_returns_agent_with_browser_tools():
    from server.agents import create_qa_visual
    from crewai import Agent
    agent = create_qa_visual()
    assert isinstance(agent, Agent)
    tool_names = {t.name for t in agent.tools}
    assert "server_runner" in tool_names
    assert "browser_qa" in tool_names
    assert "visual_diff" in tool_names
