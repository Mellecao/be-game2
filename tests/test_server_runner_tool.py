from pathlib import Path

import requests


def test_runs_python_http_server_for_static_project(tmp_path):
    (tmp_path / "index.html").write_text("<h1>OK</h1>", encoding="utf-8")

    from server.server_runner_tool import ServerRunnerTool

    tool = ServerRunnerTool()
    info = tool._run(project_dir=str(tmp_path))
    try:
        url = info["url"]
        r = requests.get(url, timeout=5)
        assert r.status_code == 200
        assert "OK" in r.text
    finally:
        tool.teardown(info)


def test_teardown_closes_port(tmp_path):
    (tmp_path / "index.html").write_text("ok", encoding="utf-8")
    from server.server_runner_tool import ServerRunnerTool
    tool = ServerRunnerTool()
    info = tool._run(project_dir=str(tmp_path))
    port = info["port"]
    tool.teardown(info)

    import socket, time
    time.sleep(0.5)
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", port))  # deve conseguir bindar de novo
    finally:
        s.close()
