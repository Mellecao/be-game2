# server/github_tool.py
"""
GitHubPushTool — git init/add/commit/push via subprocess.
Cria o repositório no GitHub via API se ainda não existir.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

VIDEOS_DIR = Path(r"C:\Users\v27me\Videos")


class _GitHubPushInput(BaseModel):
    project_slug: str = Field(
        ...,
        description="Nome do projeto em kebab-case. "
                    "A pasta deve existir em C:/Users/v27me/Videos/{project_slug}",
    )


class GitHubPushTool(BaseTool):
    name: str = "github_push"
    description: str = (
        "Inicializa repositório git na pasta do projeto, faz add+commit de todos "
        "os arquivos e push para GitHub. Cria o repositório remoto automaticamente "
        "se ainda não existir. Retorna a URL HTTPS do repositório."
    )
    args_schema: type[BaseModel] = _GitHubPushInput

    def _run(self, project_slug: str) -> str:
        username = os.environ.get("GITHUB_USERNAME", "")
        token    = os.environ.get("GITHUB_TOKEN", "")
        if not username or not token:
            return "error: GITHUB_USERNAME e GITHUB_TOKEN devem estar definidos no .env"

        project_dir = VIDEOS_DIR / project_slug
        if not project_dir.exists():
            return f"error: pasta do projeto nao encontrada: {project_dir}"

        def run_git(*args: str) -> subprocess.CompletedProcess:
            return subprocess.run(
                ["git"] + list(args),
                cwd=str(project_dir),
                capture_output=True,
                text=True,
            )

        # 1. Init (idempotente)
        r = run_git("init")
        if r.returncode != 0 and "already" not in r.stderr.lower():
            return f"error: git init falhou — {r.stderr.strip()}"

        # 2. Stage + commit
        r = run_git("add", ".")
        if r.returncode != 0:
            return f"error: git add falhou — {r.stderr.strip()}"

        r = run_git("commit", "-m", f"init: {project_slug} — gerado por Black Elephant AI")
        if r.returncode != 0 and "nothing to commit" not in r.stdout.lower():
            return f"error: git commit falhou — {r.stderr.strip()}"

        # 3. Criar repo no GitHub via API (ignora 422 = já existe)
        gh_resp = requests.post(
            "https://api.github.com/user/repos",
            json={"name": project_slug, "private": False},
            headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"},
            timeout=15,
        )
        if gh_resp.status_code not in (201, 422):
            return f"error: GitHub API retornou {gh_resp.status_code} — {gh_resp.text[:200]}"

        # 4. Remote + push
        remote_url = f"https://{token}@github.com/{username}/{project_slug}.git"
        run_git("remote", "add", "origin", remote_url)   # ignora se já existe
        run_git("branch", "-M", "main")

        r = run_git("push", "-u", "origin", "main")
        if r.returncode != 0:
            return f"error: git push falhou — {r.stderr.strip()}"

        return f"https://github.com/{username}/{project_slug}"


def get_github_tool() -> GitHubPushTool:
    return GitHubPushTool()
