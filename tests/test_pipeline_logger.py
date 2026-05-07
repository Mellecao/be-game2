import json
from pathlib import Path

import pytest


def test_log_event_writes_jsonl(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from server import pipeline_logger

    pipeline_logger.log_event("my-slug", "step_start", {"step": 1, "agent_id": "planner"})
    pipeline_logger.log_event("my-slug", "step_end", {"step": 1, "duration_s": 4.2})

    log_path = tmp_path / "output" / "my-slug" / ".pipeline.log"
    assert log_path.exists()
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    e1 = json.loads(lines[0])
    e2 = json.loads(lines[1])
    assert e1["event"] == "step_start"
    assert e1["step"] == 1
    assert e2["event"] == "step_end"
    assert "ts" in e1 and "ts" in e2


def test_read_log_returns_parsed_entries(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from server import pipeline_logger

    pipeline_logger.log_event("slug-x", "vault_write", {"path": "Atlas/Maps/X MOC.md"})
    pipeline_logger.log_event("slug-x", "asset_generated", {"asset_id": "hero", "kind": "png"})

    events = pipeline_logger.read_log("slug-x")
    assert len(events) == 2
    assert events[0]["event"] == "vault_write"
    assert events[1]["asset_id"] == "hero"


def test_active_slug_thread_local(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from server import pipeline_logger

    assert pipeline_logger.get_active_slug() is None
    pipeline_logger.set_active_slug("project-a")
    assert pipeline_logger.get_active_slug() == "project-a"
    pipeline_logger.set_active_slug(None)
    assert pipeline_logger.get_active_slug() is None


def test_log_event_no_active_slug_silent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from server import pipeline_logger

    pipeline_logger.set_active_slug(None)
    # Quando slug é None e não passa explícito, é no-op silencioso
    pipeline_logger.log_event(None, "vault_write", {"path": "x"})
    # Nenhum arquivo criado
    assert not (tmp_path / "output").exists()


def test_read_log_missing_returns_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from server import pipeline_logger

    events = pipeline_logger.read_log("never-existed")
    assert events == []
