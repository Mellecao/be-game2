# tests/test_github_tool.py
import pytest
from unittest.mock import patch, MagicMock


def test_missing_env_returns_error(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_USERNAME", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    from server.github_tool import GitHubPushTool
    tool = GitHubPushTool()
    result = tool._run(project_slug="meu-projeto")
    assert result.startswith("error:")
    assert "GITHUB_USERNAME" in result or "GITHUB_TOKEN" in result


def test_missing_project_folder_returns_error(monkeypatch):
    monkeypatch.setenv("GITHUB_USERNAME", "testuser")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_fake")
    from server.github_tool import GitHubPushTool
    tool = GitHubPushTool()
    result = tool._run(project_slug="projeto-que-nao-existe-zzz")
    assert result.startswith("error:")
    assert "nao encontrada" in result.lower() or "not found" in result.lower()


def test_successful_push_returns_url(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_USERNAME", "testuser")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_fake")

    import server.github_tool as gt
    monkeypatch.setattr(gt, "VIDEOS_DIR", tmp_path)
    (tmp_path / "meu-projeto").mkdir()

    mock_completed = MagicMock()
    mock_completed.returncode = 0
    mock_completed.stderr = ""
    mock_completed.stdout = ""

    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {}

    with patch("subprocess.run", return_value=mock_completed), \
         patch("requests.post", return_value=mock_resp):
        from server.github_tool import GitHubPushTool
        tool = GitHubPushTool()
        result = tool._run(project_slug="meu-projeto")

    assert result == "https://github.com/testuser/meu-projeto"


def test_git_failure_returns_error(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_USERNAME", "testuser")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_fake")

    import server.github_tool as gt
    monkeypatch.setattr(gt, "VIDEOS_DIR", tmp_path)
    (tmp_path / "projeto-err").mkdir()

    mock_fail = MagicMock()
    mock_fail.returncode = 128
    mock_fail.stderr = "fatal: not a git repository"
    mock_fail.stdout = ""

    with patch("subprocess.run", return_value=mock_fail):
        from server.github_tool import GitHubPushTool
        tool = GitHubPushTool()
        result = tool._run(project_slug="projeto-err")

    assert result.startswith("error:")
