import json


def test_pipeline_log_tool_returns_events(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from server import pipeline_logger
    pipeline_logger.log_event("slug-z", "vault_write", {"path": "Atlas/x.md"})
    pipeline_logger.log_event("slug-z", "asset_generated", {"asset_id": "hero", "kind": "png"})

    from server.pipeline_log_tool import PipelineLogTool
    tool = PipelineLogTool()
    out = tool._run(slug="slug-z")
    parsed = json.loads(out)
    assert isinstance(parsed, list)
    assert len(parsed) == 2
    assert parsed[0]["event"] == "vault_write"


def test_pipeline_log_tool_missing_slug(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from server.pipeline_log_tool import PipelineLogTool
    tool = PipelineLogTool()
    out = tool._run(slug="never-existed")
    parsed = json.loads(out)
    assert parsed == []
