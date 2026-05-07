"""Sobe servidor do projeto Dev pra QA Visual rodar Playwright contra ele."""
from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict
from urllib.request import urlopen
from urllib.error import URLError

from crewai.tools import BaseTool


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_until_ready(url: str, timeout: int = 60) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urlopen(url, timeout=2)
            return True
        except (URLError, ConnectionError):
            time.sleep(1)
    return False


class ServerRunnerTool(BaseTool):
    name: str = "server_runner"
    description: str = (
        "Sobe o servidor de um projeto Dev. Detecta package.json (npm run dev) "
        "ou serve estatico via python -m http.server. Retorna {url, port, pid}. "
        "Sempre chame teardown(info) no finally."
    )

    def _run(self, project_dir: str) -> Dict:
        pdir = Path(project_dir)
        if not pdir.exists():
            return {"error": f"project_dir nao existe: {project_dir}"}

        port = _free_port()

        if (pdir / "package.json").exists():
            cmd = ["npm", "run", "dev", "--", "--port", str(port)]
            shell = sys.platform == "win32"
        else:
            cmd = [sys.executable, "-m", "http.server", str(port), "--directory", str(pdir)]
            shell = False

        proc = subprocess.Popen(
            cmd,
            cwd=str(pdir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=shell,
        )

        url = f"http://127.0.0.1:{port}"
        if not _wait_until_ready(url, timeout=60):
            proc.kill()
            return {"error": f"servidor nao subiu em 60s: {url}"}

        return {"url": url, "port": port, "pid": proc.pid, "_proc": proc}

    def teardown(self, info: Dict) -> None:
        proc = info.get("_proc")
        if proc is None:
            return
        try:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        except Exception:
            pass
