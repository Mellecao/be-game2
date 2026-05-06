# server/github_tool.py
"""
GitHubPushTool — git init/add/commit/push via subprocess + Netlify zip deploy.
Retorna as URLs do GitHub e do Netlify separadas por newline.
"""
from __future__ import annotations

import io
import os
import subprocess
import zipfile
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
        "Inicializa repositório git na pasta do projeto, faz add+commit+push para GitHub "
        "e deploy automático para Netlify. "
        "Retorna a URL do GitHub e a URL do Netlify."
    )
    args_schema: type[BaseModel] = _GitHubPushInput

    def _run(self, project_slug: str) -> str:
        username = os.environ.get("GITHUB_USERNAME", "")
        gh_token = os.environ.get("GITHUB_TOKEN", "")
        nl_token  = os.environ.get("NETLIFY_ACCESS_TOKEN", "")

        if not username or not gh_token:
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

        # ── 1. Git init (idempotente) ─────────────────────────────────────────
        r = run_git("init")
        if r.returncode != 0 and "already" not in r.stderr.lower():
            return f"error: git init falhou — {r.stderr.strip()}"

        # ── 2. Stage + commit ─────────────────────────────────────────────────
        r = run_git("add", ".")
        if r.returncode != 0:
            return f"error: git add falhou — {r.stderr.strip()}"

        r = run_git("commit", "-m", f"init: {project_slug} — gerado por Black Elephant AI")
        if r.returncode != 0 and "nothing to commit" not in r.stdout.lower():
            return f"error: git commit falhou — {r.stderr.strip()}"

        # ── 3. Criar repo no GitHub via API (ignora 422 = já existe) ─────────
        gh_resp = requests.post(
            "https://api.github.com/user/repos",
            json={"name": project_slug, "private": False},
            headers={"Authorization": f"token {gh_token}", "Accept": "application/vnd.github+json"},
            timeout=15,
        )
        if gh_resp.status_code not in (201, 422):
            return f"error: GitHub API retornou {gh_resp.status_code} — {gh_resp.text[:200]}"

        # ── 4. Remote + push ──────────────────────────────────────────────────
        remote_url = f"https://{gh_token}@github.com/{username}/{project_slug}.git"
        run_git("remote", "add", "origin", remote_url)
        run_git("branch", "-M", "main")

        r = run_git("push", "-u", "origin", "main")
        if r.returncode != 0:
            return f"error: git push falhou — {r.stderr.strip()}"

        github_url = f"https://github.com/{username}/{project_slug}"

        # ── 5. Netlify deploy ─────────────────────────────────────────────────
        if not nl_token:
            return f"github: {github_url}\nnetlify: (NETLIFY_ACCESS_TOKEN nao configurado)"

        netlify_url = _deploy_to_netlify(project_dir, project_slug, nl_token)
        return f"github: {github_url}\nnetlify: {netlify_url}"


def _zip_project(project_dir: Path) -> bytes:
    """Comprime todos os arquivos do projeto (exceto .git) em um zip em memória."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in project_dir.rglob("*"):
            if f.is_file() and ".git" not in f.parts and not f.name.startswith("."):
                zf.write(f, f.relative_to(project_dir))
    return buf.getvalue()


def _deploy_to_netlify(project_dir: Path, project_slug: str, token: str) -> str:
    """Faz deploy no Netlify via zip. Retorna a URL do site ou mensagem de erro."""
    auth = {"Authorization": f"Bearer {token}"}

    # Cria o site (tenta com o nome do slug; se já existir, usa sem nome customizado)
    site_resp = requests.post(
        "https://api.netlify.com/api/v1/sites",
        headers=auth,
        json={"name": project_slug},
        timeout=30,
    )
    if site_resp.status_code == 422:
        # Nome já usado no Netlify — cria sem nome customizado
        site_resp = requests.post(
            "https://api.netlify.com/api/v1/sites",
            headers=auth,
            json={},
            timeout=30,
        )
    if site_resp.status_code not in (200, 201):
        return f"error: Netlify create site falhou — {site_resp.status_code}: {site_resp.text[:150]}"

    site_data = site_resp.json()
    site_id   = site_data["id"]

    # Faz o zip do projeto e envia para Netlify
    zip_data    = _zip_project(project_dir)
    deploy_resp = requests.post(
        f"https://api.netlify.com/api/v1/sites/{site_id}/deploys",
        headers={**auth, "Content-Type": "application/zip"},
        data=zip_data,
        timeout=120,
    )
    if deploy_resp.status_code not in (200, 201):
        return f"error: Netlify deploy falhou — {deploy_resp.status_code}: {deploy_resp.text[:150]}"

    deploy_data = deploy_resp.json()
    return (
        deploy_data.get("ssl_url")
        or deploy_data.get("url")
        or site_data.get("ssl_url")
        or site_data.get("url")
        or f"https://{project_slug}.netlify.app"
    )


def get_github_tool() -> GitHubPushTool:
    return GitHubPushTool()
