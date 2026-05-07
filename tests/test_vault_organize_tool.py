from pathlib import Path
import pytest


@pytest.fixture
def vault_setup(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "Atlas").mkdir()
    (vault / "Atlas" / "x.md").write_text("# X", encoding="utf-8")
    (vault / "Atlas" / "y.md").write_text("# Y", encoding="utf-8")
    output = tmp_path / "output" / "slug-a"
    output.mkdir(parents=True)
    (output / "asset.png").write_bytes(b"PNG-fake")

    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault))
    monkeypatch.chdir(tmp_path)
    from server import pipeline_logger
    pipeline_logger.set_active_slug("slug-a")
    yield {"vault": vault, "output": output, "tmp": tmp_path}
    pipeline_logger.set_active_slug(None)


def test_list_vault(vault_setup):
    from server.vault_organize_tool import VaultOrganizeTool
    tool = VaultOrganizeTool()
    out = tool._run(op="list", path="Atlas")
    assert "x.md" in out and "y.md" in out


def test_read_vault_file(vault_setup):
    from server.vault_organize_tool import VaultOrganizeTool
    tool = VaultOrganizeTool()
    out = tool._run(op="read", path="Atlas/x.md")
    assert "# X" in out


def test_move_within_vault(vault_setup):
    from server.vault_organize_tool import VaultOrganizeTool
    tool = VaultOrganizeTool()
    tool._run(op="move", src="Atlas/x.md", dst="Atlas/Archives/x.md")
    assert (vault_setup["vault"] / "Atlas" / "Archives" / "x.md").exists()
    assert not (vault_setup["vault"] / "Atlas" / "x.md").exists()


def test_delete_within_vault(vault_setup):
    from server.vault_organize_tool import VaultOrganizeTool
    tool = VaultOrganizeTool()
    tool._run(op="delete", path="Atlas/y.md", reason="duplicata")
    assert not (vault_setup["vault"] / "Atlas" / "y.md").exists()


def test_blocks_path_traversal(vault_setup):
    from server.vault_organize_tool import VaultOrganizeTool
    tool = VaultOrganizeTool()
    out = tool._run(op="read", path="../../etc/passwd")
    assert "Erro" in out or "bloqueado" in out.lower()


def test_blocks_absolute_path_outside_root(vault_setup):
    from server.vault_organize_tool import VaultOrganizeTool
    tool = VaultOrganizeTool()
    out = tool._run(op="read", path="C:\\Windows\\System32\\drivers\\etc\\hosts")
    assert "Erro" in out or "bloqueado" in out.lower()


def test_blocks_git_dir(vault_setup):
    (vault_setup["vault"] / ".git").mkdir()
    (vault_setup["vault"] / ".git" / "config").write_text("[core]", encoding="utf-8")
    from server.vault_organize_tool import VaultOrganizeTool
    tool = VaultOrganizeTool()
    out = tool._run(op="delete", path=".git/config", reason="x")
    assert "Erro" in out or "bloqueado" in out.lower()
    assert (vault_setup["vault"] / ".git" / "config").exists()


def test_delete_logs_event(vault_setup, tmp_path):
    from server.vault_organize_tool import VaultOrganizeTool
    from server import pipeline_logger
    tool = VaultOrganizeTool()
    tool._run(op="delete", path="Atlas/x.md", reason="teste")
    events = pipeline_logger.read_log("slug-a")
    assert any(e["event"] == "vault_delete" for e in events)


def test_move_logs_event(vault_setup, tmp_path):
    from server.vault_organize_tool import VaultOrganizeTool
    from server import pipeline_logger
    tool = VaultOrganizeTool()
    tool._run(op="move", src="Atlas/y.md", dst="Atlas/Archives/y.md")
    events = pipeline_logger.read_log("slug-a")
    assert any(e["event"] == "vault_move" for e in events)
