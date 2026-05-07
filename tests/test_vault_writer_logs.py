# tests/test_vault_writer_logs.py
def test_vault_writer_emits_log_event(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()

    import server.vault_writer as vw
    monkeypatch.setattr(vw, "VAULT_PATH", vault)

    # Point pipeline_logger output dir to tmp_path so it doesn't write to cwd
    monkeypatch.chdir(tmp_path)

    from server import pipeline_logger
    pipeline_logger.set_active_slug("p1")

    vw.write_note(
        relative_path="Atlas/Notes/test.md",
        title="Test",
        content="hello",
        agent_id="copywriter",
        ace_type="atlas",
        index=False,
    )

    events = pipeline_logger.read_log("p1")
    assert any(
        e["event"] == "vault_write" and e.get("path", "").endswith("test.md")
        for e in events
    )
    pipeline_logger.set_active_slug(None)
