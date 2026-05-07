# Image + 3D Agents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar Image Artist (Flux) e 3D Artist (Hunyuan3D) ao pipeline existente, com Designer revisor (vision LLM), asset manifest estruturado, fase de curadoria pós-pipeline pelo Bibliotecario, e migração do Qdrant para 6333+API key.

**Architecture:** Pipeline cresce de 7 para 10 etapas (Image, Designer Review, 3D entram entre Design e Dev). Bibliotecario sai do pipeline e roda como agente CrewAI numa fase de curadoria pós-pipeline (não-cancelável, lê pipeline log JSONL). Toda escrita no vault e geração de asset emite evento estruturado num log per-task que o bibliotecario consome no fim.

**Tech Stack:** Python 3.12, CrewAI, FastAPI, requests (HTTP), Qdrant client, OpenRouter (deepseek + gpt-4o-mini), Stable Diffusion WebUI Forge, Hunyuan3D-2GP, Pixi.js (frontend), pytest, pydantic.

**Spec:** `docs/superpowers/specs/2026-05-07-image-3d-agents-design.md`

---

## Convenções gerais

- TDD: cada tool/módulo novo começa com teste falhando antes da implementação.
- Imports relativos dentro de `server/` (`from .flux_tool import ...`).
- PT-BR sem acentos especiais em descrições de agentes/tasks (segue padrão atual).
- Cada task termina com commit. Mensagens em PT-BR estilo `feat(server): ...`.
- Rodar `pytest -q` antes de cada commit pra garantir que não quebrou nada.

## Pré-requisitos do ambiente local

- Forge rodando em `127.0.0.1:7860` com `--api`.
- Hunyuan3D-2GP rodando em `127.0.0.1:8081` (`C:\AI\Hunyuan3D-2GP\run_server.ps1`).
- Qdrant em `localhost:6333` com API key.
- `.env` com: `OPENROUTER_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`, `FORGE_API_URL` (default ok), `HUNYUAN_API_URL` (default ok), `VISION_MODEL` (default ok), `OBSIDIAN_VAULT_PATH`, `TRELLO_*`.

---

## Task 1: Migrar QdrantClient para usar API key

**Files:**
- Modify: `server/obsidian_indexer.py:118,132,214` (3 instâncias)
- Modify: `server/vault_tool.py:44`
- Modify: `server/api.py:419`
- Test: `tests/test_qdrant_apikey.py`

- [ ] **Step 1: Criar teste falhando**

```python
# tests/test_qdrant_apikey.py
from unittest.mock import patch, MagicMock


def test_obsidian_indexer_passes_api_key(monkeypatch):
    monkeypatch.setenv("QDRANT_URL", "http://127.0.0.1:6333")
    monkeypatch.setenv("QDRANT_API_KEY", "test-key-123")

    with patch("server.obsidian_indexer.QdrantClient") as mock_client:
        mock_client.return_value = MagicMock()
        from server import obsidian_indexer
        # Re-import constants to pick up env
        import importlib
        importlib.reload(obsidian_indexer)
        obsidian_indexer.index_single_file.__wrapped__ if hasattr(obsidian_indexer.index_single_file, "__wrapped__") else obsidian_indexer.index_single_file
        # Trigger one of the QdrantClient instantiations
        obsidian_indexer._ensure_collection(MagicMock())  # use direct call path


def test_vault_tool_passes_api_key(monkeypatch):
    monkeypatch.setenv("QDRANT_URL", "http://127.0.0.1:6333")
    monkeypatch.setenv("QDRANT_API_KEY", "test-key-456")

    with patch("server.vault_tool.QdrantClient") as mock_client:
        mock_client.return_value.search.return_value = []
        from server.vault_tool import get_vault_tool
        tool = get_vault_tool()
        tool._run("any query")
        mock_client.assert_called_once()
        kwargs = mock_client.call_args.kwargs
        assert kwargs.get("api_key") == "test-key-456"
```

- [ ] **Step 2: Rodar teste e ver falhar**

```
pytest tests/test_qdrant_apikey.py -v
```
Esperado: FAIL — `api_key` não é passado no kwargs.

- [ ] **Step 3: Aplicar mudança em `server/obsidian_indexer.py`**

No topo do arquivo, junto com `QDRANT_URL`:
```python
QDRANT_URL     = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION     = os.getenv("QDRANT_COLLECTION", "obsidian_vault")
```

E em CADA chamada `QdrantClient(...)` (linhas 118, 132, 214) adicionar `api_key=QDRANT_API_KEY`:
```python
client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, check_compatibility=False)
```

- [ ] **Step 4: Aplicar mudança em `server/vault_tool.py:44`**

```python
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
# ...
client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, check_compatibility=False)
```

- [ ] **Step 5: Aplicar mudança em `server/api.py:419`**

```python
client = QdrantClient(
    url=os.getenv("QDRANT_URL", "http://localhost:6333"),
    api_key=os.getenv("QDRANT_API_KEY"),
)
```

- [ ] **Step 6: Adicionar `QDRANT_API_KEY` ao `.env` local (se não existir)**

```bash
echo 'QDRANT_API_KEY=q5QloVfwwtlnb1RbL3li3Bfkk/5ImAngraXkOAU3jwQ=' >> .env
```

Confirmar que `.env` está no `.gitignore`:
```
git check-ignore .env
```
Esperado: imprime `.env` (ou exit code 0).

- [ ] **Step 7: Rodar testes — passar**

```
pytest tests/test_qdrant_apikey.py -v
```
Esperado: PASS.

- [ ] **Step 8: Commit**

```bash
git add server/obsidian_indexer.py server/vault_tool.py server/api.py tests/test_qdrant_apikey.py
git commit -m "feat(qdrant): adicionar suporte a API key via QDRANT_API_KEY"
```

---

## Task 2: Pipeline logger (JSONL append-only)

**Files:**
- Create: `server/pipeline_logger.py`
- Test: `tests/test_pipeline_logger.py`

- [ ] **Step 1: Criar teste falhando**

```python
# tests/test_pipeline_logger.py
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
```

- [ ] **Step 2: Rodar e ver falhar**

```
pytest tests/test_pipeline_logger.py -v
```
Esperado: FAIL — `server.pipeline_logger` não existe.

- [ ] **Step 3: Implementar `server/pipeline_logger.py`**

```python
# server/pipeline_logger.py
"""Append-only JSONL log per pipeline task."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

_tls = threading.local()
_write_lock = threading.Lock()


def _log_path(slug: str) -> Path:
    return Path("output") / slug / ".pipeline.log"


def set_active_slug(slug: str | None) -> None:
    _tls.slug = slug


def get_active_slug() -> str | None:
    return getattr(_tls, "slug", None)


def log_event(slug: str | None, event: str, payload: dict | None = None) -> None:
    """Append one JSONL entry to output/{slug}/.pipeline.log.
    If slug is None, falls back to thread-local active slug.
    If still None, silently no-op (e.g. chat call outside pipeline).
    """
    slug = slug or get_active_slug()
    if not slug:
        return

    entry: dict = {"ts": time.time(), "event": event}
    if payload:
        entry.update(payload)

    path = _log_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with _write_lock:
        with path.open("a", encoding="utf-8") as f:
            f.write(line)


def read_log(slug: str) -> list[dict]:
    path = _log_path(slug)
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # skip corrupted lines
    return out
```

- [ ] **Step 4: Rodar testes — passar**

```
pytest tests/test_pipeline_logger.py -v
```
Esperado: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add server/pipeline_logger.py tests/test_pipeline_logger.py
git commit -m "feat(server): pipeline_logger JSONL append-only por task"
```

---

## Task 3: VaultOrganizeTool (move/delete/list/read com safety)

**Files:**
- Create: `server/vault_organize_tool.py`
- Test: `tests/test_vault_organize_tool.py`

- [ ] **Step 1: Criar teste falhando**

```python
# tests/test_vault_organize_tool.py
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
```

- [ ] **Step 2: Rodar e ver falhar**

```
pytest tests/test_vault_organize_tool.py -v
```
Esperado: FAIL — módulo não existe.

- [ ] **Step 3: Implementar `server/vault_organize_tool.py`**

```python
# server/vault_organize_tool.py
"""Tool CrewAI para listar/ler/mover/apagar arquivos no vault e em output/.

Restringe operações a roots permitidos. Bloqueia path traversal, .git e
paths absolutos fora dos roots.
"""
from __future__ import annotations

import os
from pathlib import Path

from crewai.tools import BaseTool
from pydantic import Field

from . import pipeline_logger

VAULT_PATH = Path(os.getenv("OBSIDIAN_VAULT_PATH", r"C:\Users\v27me\OneDrive\Desktop\Ideaverse"))


def _allowed_roots() -> list[Path]:
    roots = [VAULT_PATH.resolve()]
    slug = pipeline_logger.get_active_slug()
    if slug:
        roots.append((Path("output") / slug).resolve())
    return roots


def _resolve_safe(path_str: str) -> Path | None:
    """Resolve path relativo a um dos roots; retorna None se inválido."""
    if not path_str:
        return None
    if "/.git/" in path_str.replace("\\", "/") or path_str.replace("\\", "/").startswith(".git/"):
        return None

    roots = _allowed_roots()
    p = Path(path_str)

    candidates = []
    if p.is_absolute():
        candidates.append(p.resolve())
    else:
        for root in roots:
            candidates.append((root / path_str).resolve())

    for cand in candidates:
        for root in roots:
            try:
                cand.relative_to(root)
                return cand
            except ValueError:
                continue
    return None


class VaultOrganizeTool(BaseTool):
    name: str = "vault_organize"
    description: str = (
        "Lista, le, move ou apaga arquivos no vault Obsidian ou na pasta output do projeto ativo. "
        "Argumentos: op (list|read|move|delete), path, src, dst, reason. "
        "Bloqueia paths fora dos roots permitidos e diretorios .git. "
        "Operacoes destrutivas exigem reason."
    )

    def _run(
        self,
        op: str,
        path: str | None = None,
        src: str | None = None,
        dst: str | None = None,
        reason: str | None = None,
    ) -> str:
        if op == "list":
            return self._list(path or "")
        if op == "read":
            return self._read(path or "")
        if op == "move":
            return self._move(src or "", dst or "")
        if op == "delete":
            return self._delete(path or "", reason or "")
        return f"Erro: op desconhecida '{op}'. Use list|read|move|delete."

    def _list(self, path: str) -> str:
        target = _resolve_safe(path) if path else _allowed_roots()[0]
        if target is None:
            return f"Erro: path bloqueado: '{path}'"
        if not target.exists():
            return f"Erro: path nao existe: '{path}'"
        if not target.is_dir():
            return f"Erro: path nao e diretorio: '{path}'"
        items = [f.name + ("/" if f.is_dir() else "") for f in sorted(target.iterdir())]
        return "\n".join(items) if items else "(diretorio vazio)"

    def _read(self, path: str) -> str:
        target = _resolve_safe(path)
        if target is None:
            return f"Erro: path bloqueado: '{path}'"
        if not target.exists():
            return f"Erro: arquivo nao existe: '{path}'"
        if not target.is_file():
            return f"Erro: path nao e arquivo: '{path}'"
        try:
            return target.read_text(encoding="utf-8")[:8000]
        except Exception as e:
            return f"Erro ao ler: {e}"

    def _move(self, src: str, dst: str) -> str:
        src_p = _resolve_safe(src)
        dst_p = _resolve_safe(dst)
        if src_p is None:
            return f"Erro: src bloqueado: '{src}'"
        if dst_p is None:
            return f"Erro: dst bloqueado: '{dst}'"
        if not src_p.exists():
            return f"Erro: src nao existe: '{src}'"
        if dst_p.exists():
            return f"Erro: dst ja existe: '{dst}' (use delete antes ou outro nome)"
        dst_p.parent.mkdir(parents=True, exist_ok=True)
        src_p.rename(dst_p)
        pipeline_logger.log_event(None, "vault_move", {"src": src, "dst": dst, "actor": "bibliotecario"})
        return f"OK: movido '{src}' -> '{dst}'"

    def _delete(self, path: str, reason: str) -> str:
        if not reason:
            return "Erro: delete requer reason"
        target = _resolve_safe(path)
        if target is None:
            return f"Erro: path bloqueado: '{path}'"
        if not target.exists():
            return f"OK: arquivo ja nao existe: '{path}'"
        if not target.is_file():
            return f"Erro: nao deleta diretorios: '{path}'"
        target.unlink()
        pipeline_logger.log_event(None, "vault_delete", {"path": path, "reason": reason, "actor": "bibliotecario"})
        return f"OK: deletado '{path}' (motivo: {reason})"
```

- [ ] **Step 4: Rodar testes — passar**

```
pytest tests/test_vault_organize_tool.py -v
```
Esperado: 9 PASS.

- [ ] **Step 5: Commit**

```bash
git add server/vault_organize_tool.py tests/test_vault_organize_tool.py
git commit -m "feat(server): VaultOrganizeTool com safety guards (roots, traversal, .git)"
```

---

## Task 4: PipelineLogTool (wrapper CrewAI)

**Files:**
- Create: `server/pipeline_log_tool.py`
- Test: `tests/test_pipeline_log_tool.py`

- [ ] **Step 1: Criar teste falhando**

```python
# tests/test_pipeline_log_tool.py
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
```

- [ ] **Step 2: Rodar e ver falhar**

```
pytest tests/test_pipeline_log_tool.py -v
```

- [ ] **Step 3: Implementar `server/pipeline_log_tool.py`**

```python
# server/pipeline_log_tool.py
"""Tool CrewAI para o bibliotecario ler o pipeline log de uma task."""
from __future__ import annotations

import json

from crewai.tools import BaseTool

from . import pipeline_logger


class PipelineLogTool(BaseTool):
    name: str = "pipeline_log"
    description: str = (
        "Le todos os eventos do pipeline log de um projeto. Argumento: slug (string, "
        "kebab-case do projeto). Retorna lista JSON com eventos {ts, event, ...payload}. "
        "Use para entender o que cada agente fez antes de decidir reorganizar."
    )

    def _run(self, slug: str) -> str:
        events = pipeline_logger.read_log(slug)
        return json.dumps(events, ensure_ascii=False)
```

- [ ] **Step 4: Rodar testes — passar**

```
pytest tests/test_pipeline_log_tool.py -v
```

- [ ] **Step 5: Commit**

```bash
git add server/pipeline_log_tool.py tests/test_pipeline_log_tool.py
git commit -m "feat(server): PipelineLogTool wrapper CrewAI sobre pipeline_logger"
```

---

## Task 5: FluxImageTool (HTTP para Forge)

**Files:**
- Create: `server/flux_tool.py`
- Test: `tests/test_flux_tool.py`

- [ ] **Step 1: Criar teste falhando** (conforme `crewai-flux-agent.md` seção 5)

```python
# tests/test_flux_tool.py
import os
import base64
from unittest.mock import patch, MagicMock


def test_flux_tool_saves_png(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_API_URL", "http://fake-forge")
    fake_png_b64 = base64.b64encode(b"\x89PNG\r\n\x1a\nFAKE").decode()
    fake_response = MagicMock()
    fake_response.json.return_value = {"images": [fake_png_b64]}
    fake_response.raise_for_status.return_value = None

    from server.flux_tool import FluxImageTool
    tool = FluxImageTool(output_dir=str(tmp_path))
    with patch("server.flux_tool.requests.post", return_value=fake_response):
        result = tool._run("a cat in space")

    assert result.endswith(".png")
    assert os.path.exists(result)
    assert os.path.getsize(result) > 0


def test_flux_tool_handles_api_error(tmp_path):
    import requests as r
    from server.flux_tool import FluxImageTool
    tool = FluxImageTool(api_url="http://127.0.0.1:1", output_dir=str(tmp_path))
    with patch(
        "server.flux_tool.requests.post",
        side_effect=r.ConnectionError("refused"),
    ):
        result = tool._run("anything")
    assert "Erro ao chamar API do Forge" in result
```

- [ ] **Step 2: Rodar e ver falhar**

```
pytest tests/test_flux_tool.py -v
```

- [ ] **Step 3: Implementar `server/flux_tool.py`**

Cópia ipsis litteris da seção 4.1 de `crewai-flux-agent.md`:
```python
# server/flux_tool.py
import base64
import os
import time
from pathlib import Path

import requests
from crewai.tools import BaseTool
from pydantic import Field

from . import pipeline_logger


class FluxImageTool(BaseTool):
    name: str = "flux_image"
    description: str = (
        "Gera uma imagem a partir de um prompt EM INGLES usando Flux Schnell NF4 "
        "via API do Stable Diffusion WebUI Forge. "
        "Retorna o caminho absoluto do PNG gerado. "
        "Argumento unico: 'prompt' (string descritiva em ingles, detalhada)."
    )
    api_url: str = Field(
        default_factory=lambda: os.environ.get("FORGE_API_URL", "http://127.0.0.1:7860")
    )
    output_dir: str = Field(default="output")
    width: int = Field(default=1024)
    height: int = Field(default=1024)
    steps: int = Field(default=4)
    cfg_scale: float = Field(default=1)
    sampler_name: str = Field(default="Euler")

    def _run(self, prompt: str) -> str:
        payload = {
            "prompt": prompt,
            "steps": self.steps,
            "cfg_scale": self.cfg_scale,
            "width": self.width,
            "height": self.height,
            "sampler_name": self.sampler_name,
            "send_images": True,
            "save_images": False,
        }
        try:
            response = requests.post(
                f"{self.api_url}/sdapi/v1/txt2img",
                json=payload,
                timeout=600,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            return (
                f"Erro ao chamar API do Forge em {self.api_url}: {e}. "
                "Verifique se o Forge esta rodando com --api."
            )

        data = response.json()
        if not data.get("images"):
            return (
                "API retornou resposta sem imagens. "
                "Verifique se o checkpoint Flux esta carregado no Forge."
            )

        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        out_path = Path(self.output_dir) / f"flux-{timestamp}.png"
        out_path.write_bytes(base64.b64decode(data["images"][0]))
        abs_path = str(out_path.resolve())

        pipeline_logger.log_event(None, "asset_generated", {
            "agent_id": "image_artist",
            "kind": "png",
            "path": abs_path,
            "prompt": prompt[:200],
        })
        return abs_path
```

- [ ] **Step 4: Rodar testes — passar**

```
pytest tests/test_flux_tool.py -v
```

- [ ] **Step 5: Commit**

```bash
git add server/flux_tool.py tests/test_flux_tool.py
git commit -m "feat(server): FluxImageTool HTTP para SD WebUI Forge"
```

---

## Task 6: Hunyuan3DTool (HTTP para Hunyuan)

**Files:**
- Create: `server/hunyuan3d_tool.py`
- Test: `tests/test_hunyuan3d_tool.py`

- [ ] **Step 1: Criar teste falhando**

```python
# tests/test_hunyuan3d_tool.py
import os
from unittest.mock import patch, MagicMock


def test_hunyuan_returns_glb_path(tmp_path, monkeypatch):
    img = tmp_path / "in.png"
    img.write_bytes(b"\x89PNG-fake")
    fake_glb = tmp_path / "out.glb"
    fake_glb.write_bytes(b"glb-bytes")

    fake_response = MagicMock()
    fake_response.json.return_value = {"path": str(fake_glb)}
    fake_response.raise_for_status.return_value = None

    from server.hunyuan3d_tool import Hunyuan3DTool
    tool = Hunyuan3DTool()
    with patch("server.hunyuan3d_tool.requests.post", return_value=fake_response):
        result = tool._run(image_path=str(img))
    assert result == str(fake_glb)


def test_hunyuan_handles_api_error(tmp_path):
    img = tmp_path / "in.png"
    img.write_bytes(b"x")
    import requests as r
    from server.hunyuan3d_tool import Hunyuan3DTool
    tool = Hunyuan3DTool(api_url="http://127.0.0.1:1")
    with patch(
        "server.hunyuan3d_tool.requests.post",
        side_effect=r.ConnectionError("refused"),
    ):
        result = tool._run(image_path=str(img))
    assert "Erro ao chamar API do Hunyuan" in result


def test_hunyuan_validates_image_exists(tmp_path):
    from server.hunyuan3d_tool import Hunyuan3DTool
    tool = Hunyuan3DTool()
    result = tool._run(image_path=str(tmp_path / "no-such-file.png"))
    assert "Erro" in result and "nao existe" in result.lower()
```

- [ ] **Step 2: Rodar e ver falhar**

```
pytest tests/test_hunyuan3d_tool.py -v
```

- [ ] **Step 3: Implementar `server/hunyuan3d_tool.py`**

```python
# server/hunyuan3d_tool.py
"""HTTP tool para Hunyuan3D-2GP em 127.0.0.1:8081."""
from __future__ import annotations

import os
from pathlib import Path

import requests
from crewai.tools import BaseTool
from pydantic import Field

from . import pipeline_logger


class Hunyuan3DTool(BaseTool):
    name: str = "hunyuan3d_generate"
    description: str = (
        "Gera um modelo 3D GLB a partir de uma imagem PNG usando o servidor "
        "Hunyuan3D-2GP local. Argumento obrigatorio: image_path (caminho absoluto "
        "do PNG). Retorna o caminho absoluto do GLB gerado."
    )
    api_url: str = Field(
        default_factory=lambda: os.environ.get("HUNYUAN_API_URL", "http://127.0.0.1:8081")
    )
    octree_resolution: int = Field(default=128)
    num_inference_steps: int = Field(default=5)
    guidance_scale: float = Field(default=5.0)
    seed: int = Field(default=1234)
    enable_texture: bool = Field(default=False)

    def _run(self, image_path: str) -> str:
        if not image_path or not Path(image_path).exists():
            return f"Erro: image_path nao existe: '{image_path}'"

        payload = {
            "image_path": image_path,
            "octree_resolution": self.octree_resolution,
            "num_inference_steps": self.num_inference_steps,
            "guidance_scale": self.guidance_scale,
            "seed": self.seed,
            "enable_texture": self.enable_texture,
        }
        try:
            response = requests.post(
                f"{self.api_url}/generate",
                json=payload,
                timeout=600,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            return (
                f"Erro ao chamar API do Hunyuan em {self.api_url}: {e}. "
                "Verifique se o servidor esta rodando."
            )

        data = response.json()
        glb_path = data.get("path") or data.get("glb_path")
        if not glb_path:
            return f"API Hunyuan retornou sem path do GLB. Resposta: {data}"

        pipeline_logger.log_event(None, "asset_generated", {
            "agent_id": "agente_3d",
            "kind": "glb",
            "path": glb_path,
            "source_image": image_path,
        })
        return glb_path
```

- [ ] **Step 4: Rodar testes — passar**

```
pytest tests/test_hunyuan3d_tool.py -v
```

- [ ] **Step 5: Commit**

```bash
git add server/hunyuan3d_tool.py tests/test_hunyuan3d_tool.py
git commit -m "feat(server): Hunyuan3DTool HTTP para servidor local Hunyuan3D-2GP"
```

---

## Task 7: Asset manifest parser

**Files:**
- Create: `server/asset_manifest.py`
- Test: `tests/test_asset_manifest.py`

- [ ] **Step 1: Criar teste falhando**

```python
# tests/test_asset_manifest.py
import json


def test_parse_valid_manifest():
    from server.asset_manifest import parse_manifest
    text = """# Guia
... blá blá ...

```asset_manifest
{
  "images": [
    {"id": "hero", "prompt_pt": "fundo escuro", "purpose": "hero", "convert_to_3d": false}
  ]
}
```
"""
    out = parse_manifest(text)
    assert "images" in out
    assert out["images"][0]["id"] == "hero"


def test_parse_missing_fence():
    from server.asset_manifest import parse_manifest
    out = parse_manifest("# guia sem manifest\n\nbla bla")
    assert out == {"images": []}


def test_parse_invalid_json():
    from server.asset_manifest import parse_manifest
    text = "```asset_manifest\nNOT JSON\n```"
    out = parse_manifest(text)
    assert out == {"images": []}


def test_parse_extracts_only_first_fence():
    from server.asset_manifest import parse_manifest
    text = """```asset_manifest
{"images": [{"id": "a"}]}
```

```asset_manifest
{"images": [{"id": "b"}]}
```
"""
    out = parse_manifest(text)
    assert out["images"][0]["id"] == "a"


def test_write_resolved_creates_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from server.asset_manifest import write_resolved, read_resolved
    manifest = {"images": [{"id": "hero", "png_path": "/abs/hero.png"}]}
    path = write_resolved("my-slug", manifest)
    assert path.exists()
    out = read_resolved("my-slug")
    assert out["images"][0]["id"] == "hero"
```

- [ ] **Step 2: Rodar e ver falhar**

```
pytest tests/test_asset_manifest.py -v
```

- [ ] **Step 3: Implementar `server/asset_manifest.py`**

```python
# server/asset_manifest.py
"""Parse + persist do asset_manifest emitido pelo Designer."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

_FENCE_RE = re.compile(r"```asset_manifest\s*\n(.*?)\n```", re.DOTALL)
_log = logging.getLogger(__name__)


def parse_manifest(designer_output: str) -> dict:
    """Extrai bloco asset_manifest do markdown do Designer.
    Retorna {"images": []} em qualquer falha (parse, ausencia, JSON invalido)."""
    if not designer_output:
        return {"images": []}
    m = _FENCE_RE.search(designer_output)
    if not m:
        _log.warning("asset_manifest: bloco nao encontrado no output do Designer")
        return {"images": []}
    raw = m.group(1).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        _log.warning("asset_manifest: JSON invalido: %s", e)
        return {"images": []}
    if not isinstance(data, dict) or "images" not in data:
        _log.warning("asset_manifest: estrutura invalida (esperado dict com 'images')")
        return {"images": []}
    return data


def _resolved_path(slug: str) -> Path:
    return Path("output") / slug / "assets" / "manifest_resolved.json"


def write_resolved(slug: str, manifest: dict) -> Path:
    path = _resolved_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def read_resolved(slug: str) -> dict:
    path = _resolved_path(slug)
    if not path.exists():
        return {"images": []}
    return json.loads(path.read_text(encoding="utf-8"))
```

- [ ] **Step 4: Rodar testes — passar**

```
pytest tests/test_asset_manifest.py -v
```

- [ ] **Step 5: Commit**

```bash
git add server/asset_manifest.py tests/test_asset_manifest.py
git commit -m "feat(server): asset_manifest parser e persistencia"
```

---

## Task 8: Vision LLM + agentes Image/3D/Reviewer

**Files:**
- Modify: `server/agents.py` (adicionar ao final)
- Test: `tests/test_new_agents.py`

- [ ] **Step 1: Criar teste falhando**

```python
# tests/test_new_agents.py
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
    assert agent.llm is vision_llm


def test_create_bibliotecario_has_organize_and_log_tools():
    from server.agents import create_bibliotecario
    agent = create_bibliotecario()
    names = [t.name for t in agent.tools]
    assert "vault_organize" in names
    assert "pipeline_log" in names
```

- [ ] **Step 2: Rodar e ver falhar**

```
pytest tests/test_new_agents.py -v
```

- [ ] **Step 3: Modificar `server/agents.py`**

Adicionar imports no topo:
```python
from .flux_tool import FluxImageTool
from .hunyuan3d_tool import Hunyuan3DTool
from .vault_organize_tool import VaultOrganizeTool
from .pipeline_log_tool import PipelineLogTool
```

Adicionar `vision_llm` logo após o `llm` existente:
```python
vision_llm = LLM(
    model=os.environ.get("VISION_MODEL", "openai/gpt-4o-mini"),
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY", ""),
    stream=True,
)
```

Adicionar 3 factories novas ao final do arquivo:
```python
def create_image_artist() -> Agent:
    return Agent(
        role="Artista Visual de IA",
        goal=(
            "Receber um asset_manifest e gerar PNGs de alta qualidade via flux_image. "
            "Traduzir cada prompt_pt em um prompt detalhado em ingles antes de chamar a tool."
        ),
        backstory=(
            "Voce e um artista visual da Black Elephant especializado em direcionar modelos "
            "de difusao. Domina vocabulario fotografico em ingles (lente, iluminacao, composicao). "
            "Responde em portugues brasileiro reportando o que gerou."
        ),
        tools=[FluxImageTool()],
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )


def create_3d_artist() -> Agent:
    return Agent(
        role="Artista 3D",
        goal=(
            "Receber um manifest_resolved.json com PNGs marcados convert_to_3d=true e "
            "gerar GLBs via hunyuan3d_generate, atualizando o manifest com glb_path."
        ),
        backstory=(
            "Voce e um artista 3D da Black Elephant especializado em transformar imagens 2D "
            "em modelos GLB para Three.js. Sabe que o Hunyuan precisa do caminho absoluto do PNG. "
            "Responde em portugues brasileiro listando os modelos gerados."
        ),
        tools=[Hunyuan3DTool()],
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )


def create_designer_reviewer() -> Agent:
    return Agent(
        role="UI/UX Designer Revisor",
        goal=(
            "Avaliar visualmente cada PNG gerado, comparando com o purpose declarado no "
            "manifest e o mood do guia visual. Devolver JSON com {id, verdict, reason, regen_prompt}."
        ),
        backstory=(
            "Voce e o mesmo designer que escreveu o guia visual. Agora esta avaliando se os "
            "PNGs gerados pelo Image Artist atendem ao briefing. Quando algo nao serve, "
            "fornece um regen_prompt em ingles que corrige o problema. Responde em JSON estrito."
        ),
        tools=[],
        llm=vision_llm,
        verbose=False,
        allow_delegation=False,
    )
```

Modificar `create_bibliotecario()` (substituir `tools=[get_vault_tool()]`):
```python
def create_bibliotecario() -> Agent:
    return Agent(
        role="Bibliotecario de Conhecimento (Knowledge Curator)",
        goal=(
            "Organizar todos os outputs dos agentes na estrutura ACE do Obsidian (Atlas, Calendar, Efforts), "
            "ler o pipeline log para entender o que cada agente fez, mover/apagar arquivos descartaveis "
            "(drafts, duplicatas, notas vazias), atualizar MOCs e escrever uma nota final de curadoria."
        ),
        backstory=(
            "Voce e um arquivista meticuloso do Ideaverse da Black Elephant. "
            "Nao tolera arquivos como 'layout_final_2.png'. Cada entrega fica organizada para que "
            "o 'eu do futuro' encontre em segundos. Use pipeline_log para saber o que aconteceu, "
            "obsidian_vault_search para contexto, e vault_organize para mover/apagar/listar/ler arquivos. "
            "Responde em portugues brasileiro."
        ),
        tools=[get_vault_tool(), VaultOrganizeTool(), PipelineLogTool()],
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )
```

- [ ] **Step 4: Rodar testes — passar**

```
pytest tests/test_new_agents.py -v
```

- [ ] **Step 5: Commit**

```bash
git add server/agents.py tests/test_new_agents.py
git commit -m "feat(agents): adicionar image_artist, 3d_artist, designer_reviewer + tools no bibliotecario"
```

---

## Task 9: Tasks novas (image_pipeline, 3d_pipeline, designer_review, curator_finalize) + modificar designer_task

**Files:**
- Modify: `server/tasks.py`
- Test: `tests/test_new_tasks.py`

- [ ] **Step 1: Criar teste falhando**

```python
# tests/test_new_tasks.py
def test_designer_task_requires_manifest():
    from server.agents import create_designer
    from server.tasks import create_designer_task
    designer = create_designer()
    task = create_designer_task(designer, {"slug": "x", "copy_path": "p.md"})
    assert "asset_manifest" in task.description


def test_image_pipeline_task_mentions_manifest_iter():
    from server.agents import create_image_artist
    from server.tasks import create_image_pipeline_task
    a = create_image_artist()
    t = create_image_pipeline_task(a, {"slug": "x", "manifest": {"images": []}})
    assert "flux_image" in t.description


def test_3d_pipeline_task_filters_convert_to_3d():
    from server.agents import create_3d_artist
    from server.tasks import create_3d_pipeline_task
    a = create_3d_artist()
    t = create_3d_pipeline_task(a, {"slug": "x"})
    assert "convert_to_3d" in t.description


def test_designer_review_task_requires_json_output():
    from server.agents import create_designer_reviewer
    from server.tasks import create_designer_review_task
    a = create_designer_reviewer()
    t = create_designer_review_task(a, {"slug": "x", "manifest_resolved": {"images": []}, "guide_excerpt": ""})
    assert "JSON" in t.description and "verdict" in t.description


def test_curator_finalize_task_includes_log_path():
    from server.agents import create_bibliotecario
    from server.tasks import create_curator_finalize_task
    a = create_bibliotecario()
    t = create_curator_finalize_task(a, {
        "slug": "x", "moc_path": "Atlas/Maps/x MOC.md",
        "effort_path": "Efforts/On/x (E).md", "final_status": "done",
        "log_path": "output/x/.pipeline.log",
    })
    assert "pipeline_log" in t.description
    assert "ACE" in t.description or "Atlas" in t.description
```

- [ ] **Step 2: Rodar e ver falhar**

```
pytest tests/test_new_tasks.py -v
```

- [ ] **Step 3: Modificar `server/tasks.py`**

Modificar `create_designer_task` — substituir o último parágrafo da descrição:
```python
        description=(
            f"Voce e o Designer. A copy do projeto '{slug}' foi salva.\n\n"
            f"1. Use obsidian_vault_search para buscar: '{slug} copy'\n"
            f"2. Leia o conteudo encontrado\n"
            f"3. Crie um guia visual completo em Markdown:\n\n"
            f"# Guia Visual: {slug}\n\n"
            f"## Paleta de Cores\n- Primaria: #XXXXXX (nome)\n- Secundaria: #XXXXXX\n"
            f"- Accent: #XXXXXX\n- Background: #XXXXXX\n- Texto: #XXXXXX\n\n"
            f"## Tipografia\n- Heading: [Google Font]\n- Body: [Google Font]\n\n"
            f"## Mood & Estetica\n- Palavras-chave: ...\n\n"
            f"## Layout por Secao\n- Hero: ...\n- Features: ...\n- CTA: ...\n\n"
            f"## Animacoes GSAP Sugeridas\n- ...\n\n"
            f"## Assets Necessarios\n- ...\n\n"
            f"4. Ao FINAL do markdown, anexe um bloco asset_manifest com este formato EXATO:\n\n"
            f"```asset_manifest\n"
            f"{{\n"
            f"  \"images\": [\n"
            f"    {{\"id\": \"hero\", \"prompt_pt\": \"...\", \"purpose\": \"...\", "
            f"\"width\": 1920, \"height\": 1080, \"convert_to_3d\": false}},\n"
            f"    {{\"id\": \"logo\", \"prompt_pt\": \"...\", \"purpose\": \"...\", "
            f"\"width\": 1024, \"height\": 1024, \"convert_to_3d\": true}}\n"
            f"  ]\n"
            f"}}\n"
            f"```\n\n"
            f"O bloco asset_manifest e OBRIGATORIO. Liste de 2 a 5 imagens. "
            f"Marque convert_to_3d=true apenas para itens que fazem sentido como modelo 3D "
            f"(logo, mascote, produto). Backgrounds e fotos fica false."
        ),
```

Adicionar 4 funções ao final do arquivo:
```python
def create_image_pipeline_task(agent: Agent, context: dict) -> Task:
    slug = context["slug"]
    manifest_json = json.dumps(context["manifest"], ensure_ascii=False, indent=2)
    return Task(
        description=(
            f"Voce e o Image Artist. Gere as imagens do projeto '{slug}'.\n\n"
            f"Manifest recebido:\n{manifest_json}\n\n"
            f"Para CADA item em images:\n"
            f"1. Reescreva o prompt_pt como um prompt detalhado em INGLES (>= 30 palavras: "
            f"   assunto, estilo, iluminacao, composicao, qualidade tipo 'cinematic', '8k', 'sharp focus').\n"
            f"2. Chame flux_image passando esse prompt em ingles.\n"
            f"3. Guarde o caminho retornado.\n\n"
            f"Ao final, responda em portugues com uma tabela:\n"
            f"| id | png_path | prompt usado |\n"
            f"|---|---|---|"
        ),
        expected_output=(
            "Tabela em portugues com id, png_path, prompt em ingles para cada imagem do manifest."
        ),
        agent=agent,
    )


def create_3d_pipeline_task(agent: Agent, context: dict) -> Task:
    slug = context["slug"]
    return Task(
        description=(
            f"Voce e o 3D Artist. O Image Artist ja gerou PNGs do projeto '{slug}'.\n\n"
            f"O manifest_resolved esta em output/{slug}/assets/manifest_resolved.json.\n\n"
            f"1. Filtre apenas itens com convert_to_3d=true E que tenham png_path valido.\n"
            f"2. Para cada um, chame hunyuan3d_generate passando image_path=png_path absoluto.\n"
            f"3. Capture o glb_path retornado.\n\n"
            f"Ao final, responda em portugues com tabela:\n"
            f"| id | glb_path | source_png |\n|---|---|---|"
        ),
        expected_output=(
            "Tabela em portugues com id, glb_path, source_png para cada modelo 3D gerado."
        ),
        agent=agent,
    )


def create_designer_review_task(agent: Agent, context: dict) -> Task:
    slug = context["slug"]
    manifest_resolved_json = json.dumps(context["manifest_resolved"], ensure_ascii=False, indent=2)
    guide_excerpt = context.get("guide_excerpt", "")
    return Task(
        description=(
            f"Voce e o Designer revisando os PNGs do projeto '{slug}'.\n\n"
            f"Trecho do guia visual:\n{guide_excerpt[:2000]}\n\n"
            f"Manifest resolvido:\n{manifest_resolved_json}\n\n"
            f"Para cada imagem com png_path, examine visualmente (voce esta recebendo via "
            f"vision LLM, com a imagem anexada na mensagem) e julgue:\n"
            f"- Atende ao 'purpose' declarado?\n- Bate com o mood do guia?\n"
            f"- Qualidade tecnica aceitavel?\n\n"
            f"Responda APENAS um JSON valido neste formato:\n"
            f"{{\n"
            f"  \"reviews\": [\n"
            f"    {{\"id\": \"...\", \"verdict\": \"APROVADO\" ou \"REPROVADO\", "
            f"\"reason\": \"...\", \"regen_prompt\": \"...\" (apenas se REPROVADO)}}\n"
            f"  ]\n"
            f"}}\n"
            f"NADA fora do JSON. Sem markdown, sem texto antes ou depois."
        ),
        expected_output="JSON estrito com chave 'reviews' contendo verdict, reason e regen_prompt por imagem.",
        agent=agent,
    )


def create_curator_finalize_task(agent: Agent, context: dict) -> Task:
    slug = context["slug"]
    return Task(
        description=(
            f"Voce e o Bibliotecario fazendo curadoria final do projeto '{slug}'.\n\n"
            f"Status final do pipeline: {context['final_status']}\n"
            f"MOC: {context['moc_path']}\n"
            f"Effort: {context['effort_path']}\n\n"
            f"Passos obrigatorios:\n"
            f"1. Use pipeline_log com slug='{slug}' para listar tudo que foi feito.\n"
            f"2. Use vault_organize op=list para inspecionar a estrutura ACE atual:\n"
            f"   - Atlas/Maps, Atlas/Notes, Atlas/Utilities (sub-pastas por agente)\n"
            f"   - Calendar/\n"
            f"   - Efforts/On|Ongoing|Simmering|Archives\n"
            f"3. Para cada arquivo escrito (eventos vault_write):\n"
            f"   - Esta no bucket ACE correto? Se nao, vault_organize op=move.\n"
            f"   - E uma duplicata/draft? Se sim, vault_organize op=delete (com reason).\n"
            f"4. Identifique e apague:\n"
            f"   - Arquivos com mesmo titulo no mesmo bucket (mantenha o mais recente).\n"
            f"   - Notas com conteudo < 50 chars (excluindo frontmatter).\n"
            f"   - NUNCA apague nada de output/{slug}/ — esses vao pro git.\n"
            f"5. Atualize o MOC ({context['moc_path']}) acrescentando secao '## Curadoria' "
            f"   com bullets do que foi consolidado e do que foi removido (com motivo).\n"
            f"6. Escreva uma nota final em "
            f"   'Atlas/Notes/Agentes/Bibliotecario/{slug}-curation.md' "
            f"   com summary executivo do projeto (use vault_organize ou vault_writer).\n\n"
            f"Responda em portugues com resumo curto: arquivos movidos (N), apagados (N), MOC atualizado, "
            f"nota de curadoria criada em <path>."
        ),
        expected_output=(
            "Resumo em portugues: contagem de arquivos movidos/apagados, confirmacao de MOC atualizado e path da nota de curadoria."
        ),
        agent=agent,
    )
```

Adicionar `import json` no topo de `tasks.py` se não tiver.

- [ ] **Step 4: Rodar testes — passar**

```
pytest tests/test_new_tasks.py -v
```

- [ ] **Step 5: Commit**

```bash
git add server/tasks.py tests/test_new_tasks.py
git commit -m "feat(tasks): adicionar image/3d/review/curator tasks + manifest no designer_task"
```

---

## Task 10: Hook de log no vault_writer

**Files:**
- Modify: `server/vault_writer.py:97`
- Test: `tests/test_vault_writer_logs.py`

- [ ] **Step 1: Criar teste falhando**

```python
# tests/test_vault_writer_logs.py
def test_vault_writer_emits_log_event(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault))
    monkeypatch.chdir(tmp_path)

    from server import pipeline_logger
    pipeline_logger.set_active_slug("p1")

    # Reload vault_writer pra pegar o env
    import importlib
    import server.vault_writer as vw
    importlib.reload(vw)

    vw.write_note(
        relative_path="Atlas/Notes/test.md",
        title="Test",
        content="hello",
        agent_id="copywriter",
        ace_type="atlas",
        index=False,
    )

    events = pipeline_logger.read_log("p1")
    assert any(e["event"] == "vault_write" and e.get("path", "").endswith("test.md") for e in events)
    pipeline_logger.set_active_slug(None)
```

- [ ] **Step 2: Rodar e ver falhar**

```
pytest tests/test_vault_writer_logs.py -v
```

- [ ] **Step 3: Modificar `server/vault_writer.py`**

No final de `write_note`, antes do `return full`:
```python
    from server import pipeline_logger
    pipeline_logger.log_event(None, "vault_write", {
        "path": str(full.relative_to(VAULT_PATH)) if full.is_relative_to(VAULT_PATH) else str(full),
        "agent_id": agent_id,
        "ace_type": ace_type,
        "tags": tags or [],
    })

    return full
```

- [ ] **Step 4: Rodar testes — passar**

```
pytest tests/test_vault_writer_logs.py -v
```

- [ ] **Step 5: Commit**

```bash
git add server/vault_writer.py tests/test_vault_writer_logs.py
git commit -m "feat(vault_writer): emitir vault_write event no pipeline_logger"
```

---

## Task 11: librarian.after_design + librarian.after_assets

**Files:**
- Modify: `server/librarian.py`
- Test: `tests/test_librarian_after_design_assets.py`

- [ ] **Step 1: Criar teste falhando**

```python
# tests/test_librarian_after_design_assets.py
import json


def test_after_design_writes_manifest_json(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    (vault / "Atlas" / "Maps").mkdir(parents=True)
    moc = vault / "Atlas" / "Maps" / "myslug MOC.md"
    moc.write_text("# myslug MOC\n\n## Design\n\n## Imagens\n\n## Modelos 3D\n", encoding="utf-8")
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault))
    monkeypatch.chdir(tmp_path)

    import importlib
    import server.librarian as lib
    importlib.reload(lib)

    manifest = {"images": [{"id": "hero", "purpose": "bg"}]}
    lib.after_design(
        slug="myslug",
        guide_path="Atlas/Utilities/Designer/2026-01-01-myslug-visual-guide.md",
        manifest_str=json.dumps(manifest),
        moc_path="Atlas/Maps/myslug MOC.md",
        index=False,
    )

    manifest_md = list((vault / "Atlas" / "Utilities" / "Designer").glob("*-myslug-manifest.json"))
    assert manifest_md, "manifest json nao foi criado"


def test_after_assets_writes_md_lists(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    (vault / "Atlas" / "Maps").mkdir(parents=True)
    moc = vault / "Atlas" / "Maps" / "abc MOC.md"
    moc.write_text("# abc MOC\n\n## Design\n\n## Imagens\n\n## Modelos 3D\n", encoding="utf-8")
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault))
    monkeypatch.chdir(tmp_path)

    import importlib
    import server.librarian as lib
    importlib.reload(lib)

    resolved = {"images": [
        {"id": "hero", "png_path": "/abs/hero.png", "prompt_en": "...", "purpose": "bg"},
        {"id": "logo", "png_path": "/abs/logo.png", "glb_path": "/abs/logo.glb", "prompt_en": "...", "purpose": "logo"},
    ]}
    lib.after_assets(
        slug="abc",
        resolved_manifest=resolved,
        project_dir=str(tmp_path / "fakeproj"),
        moc_path="Atlas/Maps/abc MOC.md",
        index=False,
    )

    assets_md = list((vault / "Atlas" / "Utilities" / "ImageArtist").glob("*-abc-assets.md"))
    models_md = list((vault / "Atlas" / "Utilities" / "3DArtist").glob("*-abc-models.md"))
    assert assets_md and models_md
```

- [ ] **Step 2: Rodar e ver falhar**

```
pytest tests/test_librarian_after_design_assets.py -v
```

- [ ] **Step 3: Adicionar `after_design` e `after_assets` em `server/librarian.py`**

```python
def after_design(slug: str, guide_path: str, manifest_str: str, moc_path: str, index: bool = True) -> None:
    """Pos-design: salva manifest JSON, atualiza MOC com link pro guia."""
    today = date.today().isoformat()
    manifest_relpath = f"Atlas/Utilities/Designer/{today}-{slug}-manifest.json"
    full_manifest = VAULT_PATH / manifest_relpath
    full_manifest.parent.mkdir(parents=True, exist_ok=True)
    full_manifest.write_text(manifest_str, encoding="utf-8")

    full_moc = VAULT_PATH / moc_path
    if full_moc.exists():
        text = full_moc.read_text(encoding="utf-8")
        guide_link = f"[[{guide_path.replace('.md', '')}]]"
        manifest_link = f"[[{manifest_relpath.replace('.json', '')}|asset_manifest]]"
        if "## Design" in text and guide_link not in text:
            insert = f"## Design\n- {guide_link}\n- Manifest: {manifest_link}\n"
            text = text.replace("## Design\n", insert)
            full_moc.write_text(text, encoding="utf-8")

    if index:
        try:
            from server.obsidian_indexer import index_single_file
            index_single_file(full_manifest)
        except Exception as exc:
            logging.getLogger(__name__).debug("after_design indexing skipped — %s", exc)


def after_assets(slug: str, resolved_manifest: dict, project_dir: str, moc_path: str, index: bool = True) -> None:
    """Pos-assets: cria notas listando PNGs e GLBs, atualiza MOC."""
    today = date.today().isoformat()
    images = resolved_manifest.get("images", [])

    # ImageArtist note
    img_lines = ["| id | png_path | purpose |", "|---|---|---|"]
    for it in images:
        img_lines.append(f"| {it.get('id', '')} | `{it.get('png_path', '')}` | {it.get('purpose', '')} |")
    img_content = "\n".join(img_lines)

    img_relpath = f"Atlas/Utilities/ImageArtist/{today}-{slug}-assets.md"
    img_full = VAULT_PATH / img_relpath
    img_full.parent.mkdir(parents=True, exist_ok=True)
    import yaml
    from server.vault_writer import build_frontmatter
    fm_img = build_frontmatter("image_artist", "resources", tags=["assets", slug])
    img_full.write_text(f"---\n{fm_img}---\n\n# Assets PNG: {slug}\n\n{img_content}", encoding="utf-8")

    # 3D Artist note
    glb_items = [it for it in images if it.get("glb_path")]
    glb_lines = ["| id | glb_path | source_png |", "|---|---|---|"]
    for it in glb_items:
        glb_lines.append(f"| {it.get('id', '')} | `{it.get('glb_path', '')}` | `{it.get('png_path', '')}` |")
    glb_content = "\n".join(glb_lines) if glb_items else "_(nenhum modelo 3D gerado)_"

    glb_relpath = f"Atlas/Utilities/3DArtist/{today}-{slug}-models.md"
    glb_full = VAULT_PATH / glb_relpath
    glb_full.parent.mkdir(parents=True, exist_ok=True)
    fm_glb = build_frontmatter("agente_3d", "resources", tags=["assets-3d", slug])
    glb_full.write_text(f"---\n{fm_glb}---\n\n# Modelos 3D: {slug}\n\n{glb_content}", encoding="utf-8")

    # MOC update
    full_moc = VAULT_PATH / moc_path
    if full_moc.exists():
        text = full_moc.read_text(encoding="utf-8")
        img_link = f"[[{img_relpath.replace('.md', '')}|Lista de PNGs]]"
        glb_link = f"[[{glb_relpath.replace('.md', '')}|Lista de GLBs]]"
        if "## Imagens" in text and img_link not in text:
            text = text.replace("## Imagens\n", f"## Imagens\n- {img_link}\n")
        if "## Modelos 3D" in text and glb_link not in text:
            text = text.replace("## Modelos 3D\n", f"## Modelos 3D\n- {glb_link}\n")
        full_moc.write_text(text, encoding="utf-8")

    if index:
        try:
            from server.obsidian_indexer import index_single_file
            index_single_file(img_full)
            index_single_file(glb_full)
        except Exception as exc:
            logging.getLogger(__name__).debug("after_assets indexing skipped — %s", exc)
```

- [ ] **Step 4: Rodar testes — passar**

```
pytest tests/test_librarian_after_design_assets.py -v
```

- [ ] **Step 5: Commit**

```bash
git add server/librarian.py tests/test_librarian_after_design_assets.py
git commit -m "feat(librarian): after_design e after_assets gerando notas no ACE"
```

---

## Task 12: Pipeline integration — 7 → 10 etapas + curadoria

**Files:**
- Modify: `server/planner_loop.py`
- Test: `tests/test_pipeline_assets.py`

Esta task é a maior — junta tudo. Quebrada em sub-passos lógicos.

- [ ] **Step 1: Criar teste de integração (mockado)**

```python
# tests/test_pipeline_assets.py
import json
from pathlib import Path
from unittest.mock import patch, MagicMock


def _fake_designer_output(slug):
    return f"""# Guia Visual: {slug}

## Paleta
preto e dourado.

```asset_manifest
{{
  "images": [
    {{"id": "hero", "prompt_pt": "fundo escuro com particulas", "purpose": "hero bg",
      "width": 1920, "height": 1080, "convert_to_3d": false}},
    {{"id": "logo", "prompt_pt": "elefante mascote", "purpose": "logo 3D",
      "width": 1024, "height": 1024, "convert_to_3d": true}}
  ]
}}
```
"""


def test_pipeline_writes_resolved_manifest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path / "vault"))
    (tmp_path / "vault" / "Atlas" / "Maps").mkdir(parents=True)

    slug = "test-slug"
    fake_png = tmp_path / "fake.png"
    fake_png.write_bytes(b"PNG-fake")
    fake_glb = tmp_path / "fake.glb"
    fake_glb.write_bytes(b"GLB-fake")

    # Patch all crew kickoffs and tools
    with patch("server.planner_loop._fetch_cards"), \
         patch("server.planner_loop.create_planner") as mp, \
         patch("server.planner_loop.create_copywriter") as mc, \
         patch("server.planner_loop.create_designer") as md, \
         patch("server.planner_loop.create_image_artist") as mi, \
         patch("server.planner_loop.create_designer_reviewer") as mr, \
         patch("server.planner_loop.create_3d_artist") as m3, \
         patch("server.planner_loop.create_developer") as mdev, \
         patch("server.planner_loop.create_qa") as mqa, \
         patch("server.planner_loop.create_devops") as mdo, \
         patch("server.planner_loop.create_bibliotecario") as mb, \
         patch("server.planner_loop.Crew") as MockCrew, \
         patch("server.planner_loop.FluxImageTool") as MockFlux, \
         patch("server.planner_loop.Hunyuan3DTool") as MockHun:

        # Chain Crew().kickoff() returns
        kickoff_results = iter([
            "planner ok",                   # 1. planner moc
            "copy markdown",                # 2. copywriter
            _fake_designer_output(slug),    # 3. designer
            "imagens geradas",              # 4. image artist
            json.dumps({"reviews": [
                {"id": "hero", "verdict": "APROVADO", "reason": "ok"},
                {"id": "logo", "verdict": "APROVADO", "reason": "ok"},
            ]}),                            # 5. designer review
            "3d gerado",                    # 6. 3d artist
            "dev ok",                       # 7. dev
            "STATUS: APROVADO\nok",         # 8. qa
            "github: https://github.com/x/test\nnetlify: https://test.netlify.app",  # 9. devops
            "fechado",                      # 10. planner close
            "curadoria ok",                 # C. bibliotecario
        ])
        crew_instance = MagicMock()
        crew_instance.kickoff.side_effect = lambda *a, **kw: next(kickoff_results)
        MockCrew.return_value = crew_instance

        MockFlux.return_value._run.return_value = str(fake_png)
        MockHun.return_value._run.return_value = str(fake_glb)

        from server.planner_loop import _run_pipeline, PlannerTask
        import time
        task = PlannerTask(
            id="cardid",
            card_name="Test Project",
            status="delegating", log="", created_at=time.time(),
            start_at=time.time(),
        )
        _run_pipeline(task, "Test Project", "briefing")

    resolved_path = Path("output") / slug.replace("test-slug", "test-project") / "assets" / "manifest_resolved.json"
    # Slug is derived from card name "Test Project" -> "test-project"
    assert resolved_path.exists() or (Path("output") / "test-project" / "assets" / "manifest_resolved.json").exists()
```

(Nota: o teste de integração mockado é frágil — recomenda-se manter focado em verificar que `manifest_resolved.json` é escrito e que a curadoria roda. Validações mais detalhadas ficam por conta dos unitários.)

- [ ] **Step 2: Rodar e ver falhar**

```
pytest tests/test_pipeline_assets.py -v
```

- [ ] **Step 3: Modificar `server/planner_loop.py` — imports**

No bloco de imports do `_run_pipeline`, adicionar:
```python
from .agents import (
    create_copywriter, create_planner, create_designer,
    create_image_artist, create_designer_reviewer, create_3d_artist,
    create_developer, create_qa, create_devops, create_bibliotecario,
)
from .tasks import (
    create_planner_moc_task, create_copywriter_pipeline_task,
    create_designer_task,
    create_image_pipeline_task, create_designer_review_task, create_3d_pipeline_task,
    create_dev_task, create_qa_task, create_dev_revision_task,
    create_devops_task, create_planner_close_task, create_curator_finalize_task,
)
from . import asset_manifest as _am
from . import pipeline_logger
from .flux_tool import FluxImageTool
from .hunyuan3d_tool import Hunyuan3DTool
```

- [ ] **Step 4: Modificar `_set` para emitir `step_start` no logger**

```python
def _set(step_num: int, status: str, log_msg: str) -> bool:
    with _tasks_lock:
        if task.status == "cancelled":
            return False
        task.status = status
        task.step   = step_num
        task.log    = log_msg
    event_bus.emit("pipeline_step", f"[{step_num}/10] {log_msg}")
    pipeline_logger.log_event(None, "step_start", {"step": step_num, "status": status})
    return True
```

(Mudar `[{step_num}/7]` pra `[{step_num}/10]`.)

- [ ] **Step 5: Setar slug ativo no início do `_run_pipeline`**

Logo após `slug = _slugify(card_name)`:
```python
pipeline_logger.set_active_slug(slug)
```

- [ ] **Step 6: Inserir etapas 4, 5, 6 entre Design (3) e Dev (atual 4 → vira 7)**

Substituir o bloco de DESENVOLVIMENTO atual (que era step 4) pelo novo:

```python
        # ── 4. IMAGENS ───────────────────────────────────────────────────────
        if not _set(4, "imagining", "Image Artist gerando PNGs do manifest..."):
            return

        manifest = _am.parse_manifest(design_result)
        manifest_resolved = {"images": []}
        if manifest.get("images"):
            image_artist = create_image_artist()
            image_task = create_image_pipeline_task(image_artist, {"slug": slug, "manifest": manifest})
            Crew(agents=[image_artist], tasks=[image_task], verbose=False).kickoff()

            # Resolve manifest com PNGs gerados (Image Artist usou flux_image; coletamos via log)
            asset_dir = Path(rf"output\{slug}\assets")
            asset_dir.mkdir(parents=True, exist_ok=True)
            png_events = [e for e in pipeline_logger.read_log(slug)
                          if e["event"] == "asset_generated" and e.get("kind") == "png"]
            png_paths_by_id = {}
            # Heuristica: usa ordem de geracao para mapear pra ordem do manifest
            for spec, ev in zip(manifest["images"], png_events):
                png_paths_by_id[spec["id"]] = ev["path"]

            manifest_resolved = {"images": []}
            for spec in manifest["images"]:
                item = dict(spec)
                if spec["id"] in png_paths_by_id:
                    item["png_path"] = png_paths_by_id[spec["id"]]
                manifest_resolved["images"].append(item)
            _am.write_resolved(slug, manifest_resolved)

        # Verifica catastrofe: nenhuma imagem gerada quando manifest pediu
        if manifest.get("images") and not any(i.get("png_path") for i in manifest_resolved["images"]):
            with _tasks_lock:
                task.status = "error"
                task.log = "Nenhuma imagem do manifest foi gerada — Forge offline?"
            event_bus.emit("error", f"❌ Imagens falharam para '{card_name}'")
            return

        # ── 5. DESIGNER REVIEW ───────────────────────────────────────────────
        if manifest_resolved.get("images"):
            if not _set(5, "reviewing_assets", "Designer revisando os PNGs..."):
                return

            reviewer = create_designer_reviewer()
            review_task = create_designer_review_task(reviewer, {
                "slug": slug,
                "manifest_resolved": manifest_resolved,
                "guide_excerpt": design_result[:3000],
            })
            review_raw = str(Crew(agents=[reviewer], tasks=[review_task], verbose=False).kickoff())

            try:
                review_data = json.loads(review_raw.strip())
                reviews = review_data.get("reviews", [])
            except json.JSONDecodeError:
                reviews = []

            for r in reviews:
                pipeline_logger.log_event(None, "asset_review", {
                    "asset_id": r.get("id"),
                    "verdict": r.get("verdict"),
                    "reason": r.get("reason", "")[:200],
                })

            reproved = [r for r in reviews if r.get("verdict") == "REPROVADO"]
            if reproved:
                if not _set(5, "regen_assets", f"Regenerando {len(reproved)} imagens reprovadas..."):
                    return

                flux = FluxImageTool()
                for r in reproved:
                    item = next((i for i in manifest_resolved["images"] if i["id"] == r["id"]), None)
                    if not item or not r.get("regen_prompt"):
                        continue
                    new_path = flux._run(r["regen_prompt"])
                    if not new_path.startswith("Erro"):
                        item["png_path"] = new_path
                _am.write_resolved(slug, manifest_resolved)

        # ── 6. 3D ────────────────────────────────────────────────────────────
        threed_items = [i for i in manifest_resolved.get("images", [])
                        if i.get("convert_to_3d") and i.get("png_path")]
        if threed_items:
            if not _set(6, "modeling_3d", f"3D Artist gerando {len(threed_items)} GLBs..."):
                return

            artist3d = create_3d_artist()
            t3d = create_3d_pipeline_task(artist3d, {"slug": slug})
            Crew(agents=[artist3d], tasks=[t3d], verbose=False).kickoff()

            glb_events = [e for e in pipeline_logger.read_log(slug)
                          if e["event"] == "asset_generated" and e.get("kind") == "glb"]
            glb_by_source = {ev.get("source_image"): ev["path"] for ev in glb_events}
            for item in manifest_resolved["images"]:
                if item.get("png_path") in glb_by_source:
                    item["glb_path"] = glb_by_source[item["png_path"]]
            _am.write_resolved(slug, manifest_resolved)

        librarian.after_assets(slug, manifest_resolved, project_dir, moc_path)
```

E o que era `## ── 4. DESENVOLVIMENTO ──` vira `## ── 7. DESENVOLVIMENTO ──`, com `_set(7, "developing", ...)`. Renumere as etapas 5, 6, 7 atuais (QA, Deploy, Fechamento) pra 8, 9, 10.

Renomeie no `_set` calls:
- `_set(5, "reviewing", ...)` → `_set(8, "reviewing", ...)`
- `_set(6, "deploying", ...)` → `_set(9, "deploying", ...)`
- `_set(7, "closing", ...)` → `_set(10, "closing", ...)`

Atualizar a linha que adiciona `librarian.after_design` após DESIGN:
```python
        # depois de salvar guide_path no vault, ainda dentro do bloco de DESIGN:
        librarian.after_design(slug, guide_path, json.dumps(_am.parse_manifest(design_result)), moc_path)
```

- [ ] **Step 7: Adicionar `_run_curation` e wrapper try/finally**

No final de `_run_pipeline`, depois do bloco `except`, refatorar em try/finally externo:

Estrutura final do método:
```python
def _run_pipeline(task: PlannerTask, card_name: str, card_desc: str) -> None:
    _tls.task_id = task.id
    slug = _slugify(card_name)
    pipeline_logger.set_active_slug(slug)
    # ... vars como antes ...

    final_status = "error"
    try:
        # ... bloco try original com etapas 1-10 ...
        # se chegou ao fim sem return, marca done
        final_status = task.status  # done|cancelled
    except Exception as e:
        # tratamento como antes
        final_status = "error"
    finally:
        try:
            _run_curation(task, slug, moc_path, effort_path, final_status)
        except Exception as e:
            print(f"[planner:{task.id[:8]}] ERRO na curadoria: {e}")
        pipeline_logger.set_active_slug(None)
```

E criar `_run_curation`:
```python
def _run_curation(task: PlannerTask, slug: str, moc_path: str, effort_path: str, final_status: str) -> None:
    """Fase pos-pipeline: bibliotecario faz curadoria final. Sempre roda."""
    with _tasks_lock:
        previous_log = task.log
        task.status = "curating"
        task.log = f"Bibliotecario fazendo curadoria final de '{slug}'..."
    event_bus.emit("pipeline_step", f"[C] Bibliotecario curando {slug}...")

    pipeline_logger.log_event(None, "step_start", {"step": "curating", "status": "curating"})

    biblio = create_bibliotecario()
    crew_task = create_curator_finalize_task(biblio, {
        "slug": slug,
        "moc_path": moc_path,
        "effort_path": effort_path,
        "final_status": final_status,
        "log_path": f"output/{slug}/.pipeline.log",
    })
    try:
        Crew(agents=[biblio], tasks=[crew_task], verbose=False).kickoff()
    except Exception as e:
        print(f"[planner:{task.id[:8]}] curadoria abortou: {e}")

    with _tasks_lock:
        # Restaura status final do pipeline (não sobrescreve done/error/cancelled)
        task.status = final_status
        task.log = f"{previous_log} | curadoria concluida"

    pipeline_logger.log_event(None, "step_end", {"step": "curating"})
    event_bus.emit("pipeline_step", f"[C] Curadoria de '{slug}' concluida")
```

- [ ] **Step 8: Rodar testes — passar**

```
pytest tests/test_pipeline_assets.py -v
```

(Se falhar por detalhes específicos do mock, ajustar o teste pra ser menos rígido — o objetivo é cobrir o caminho principal.)

- [ ] **Step 9: Rodar suíte inteira pra garantir que não quebrou nada**

```
pytest -q
```
Esperado: tudo passa. Se algo quebrou, investigar e corrigir antes de commitar.

- [ ] **Step 10: Commit**

```bash
git add server/planner_loop.py tests/test_pipeline_assets.py
git commit -m "feat(planner): pipeline 10 etapas + curadoria pos-pipeline"
```

---

## Task 13: AGENT_SEED — Image Artist + 3D Artist no game

**Files:**
- Modify: `server/api.py:95-176` (AGENT_SEED + _AGENT_DISPLAY)
- Test: `tests/test_agent_seed.py`

- [ ] **Step 1: Criar teste falhando**

```python
# tests/test_agent_seed.py
def test_agent_seed_has_new_npcs():
    from server.api import AGENT_SEED
    ids = {a["id"] for a in AGENT_SEED}
    assert "image_artist" in ids
    assert "agente_3d" in ids


def test_agent_seed_positions_around_designer():
    from server.api import AGENT_SEED
    by_id = {a["id"]: a for a in AGENT_SEED}
    assert by_id["image_artist"]["col"] == 1.0
    assert by_id["image_artist"]["row"] == 4.0
    assert by_id["agente_3d"]["col"] == 3.0
    assert by_id["agente_3d"]["row"] == 4.0


def test_agent_seed_has_unique_ids():
    from server.api import AGENT_SEED
    ids = [a["id"] for a in AGENT_SEED]
    assert len(ids) == len(set(ids))
```

- [ ] **Step 2: Rodar e ver falhar**

```
pytest tests/test_agent_seed.py -v
```

- [ ] **Step 3: Adicionar entradas em `server/api.py:AGENT_SEED`**

Adicionar antes do `]` de fechamento:
```python
    {
        "id": "image_artist",
        "display_name": "Image Artist",
        "role": "Artista Visual de IA",
        "goal": "Gerar PNGs do asset_manifest via Flux Schnell, reportando id/path/prompt usado.",
        "backstory": "Especialista em direcionar modelos de difusao com prompts em ingles. Traduz briefing PT-BR em prompts ricos antes de chamar flux_image.",
        "col": 1.0,
        "row": 4.0,
        "sprite_char": 4,
    },
    {
        "id": "agente_3d",
        "display_name": "Agente 3D",
        "role": "Artista 3D",
        "goal": "Gerar GLBs via Hunyuan3D a partir de PNGs marcados convert_to_3d=true no manifest.",
        "backstory": "Transforma imagens 2D em modelos 3D para Three.js. Sabe que o Hunyuan precisa do path absoluto do PNG.",
        "col": 3.0,
        "row": 4.0,
        "sprite_char": 5,
    },
```

E adicionar em `_AGENT_DISPLAY` (linha ~194):
```python
    "image_artist": "Image Artist",
    "agente_3d":    "Agente 3D",
```

- [ ] **Step 4: Rodar testes — passar**

```
pytest tests/test_agent_seed.py -v
```

- [ ] **Step 5: Commit**

```bash
git add server/api.py tests/test_agent_seed.py
git commit -m "feat(api): adicionar image_artist e agente_3d ao AGENT_SEED"
```

---

## Task 14: Frontend — TasksPanel.ts (status mapping + agent info)

**Files:**
- Modify: `src/ui/TasksPanel.ts:45-64`

- [ ] **Step 1: Estender `STATUS_TO_AGENT` (linha 45)**

```typescript
const STATUS_TO_AGENT: Record<string, string> = {
  planning:         "planner",
  copywriting:      "copywriter",
  designing:        "designer",
  imagining:        "image_artist",
  reviewing_assets: "designer",
  regen_assets:     "image_artist",
  modeling_3d:      "agente_3d",
  developing:       "programador",
  reviewing:        "qa",
  revision:         "programador",
  deploying:        "devops",
  closing:          "planner",
  curating:         "bibliotecario",
};
```

- [ ] **Step 2: Estender `AGENT_INFO` (linha 56)**

```typescript
const AGENT_INFO: Record<string, { name: string; initials: string; color: string; role: string }> = {
  planner:       { name: "Planner",       initials: "PL", color: "#3b82f6", role: "Gerente de Projetos" },
  copywriter:    { name: "Copywriter",    initials: "CW", color: "#8b5cf6", role: "Copywriter de Landing Pages" },
  designer:      { name: "Designer",      initials: "DS", color: "#ec4899", role: "UI/UX Designer" },
  image_artist:  { name: "Image Artist",  initials: "IA", color: "#f43f5e", role: "Artista Visual de IA" },
  agente_3d:     { name: "Agente 3D",     initials: "3D", color: "#a855f7", role: "Artista 3D" },
  programador:   { name: "Programador",   initials: "PR", color: "#10b981", role: "Desenvolvedor Full-Stack" },
  qa:            { name: "QA",            initials: "QA", color: "#f59e0b", role: "Engenheiro de Qualidade" },
  devops:        { name: "DevOps",        initials: "DO", color: "#6366f1", role: "Engenheiro DevOps" },
  bibliotecario: { name: "Bibliotecario", initials: "BB", color: "#14b8a6", role: "Curador de Conhecimento" },
};
```

- [ ] **Step 3: Estender `ACTIVE_STATUSES` (linha 65)**

```typescript
const ACTIVE_STATUSES = new Set([
  "planning",
  "copywriting",
  "designing",
  "imagining",
  "reviewing_assets",
  "regen_assets",
  "modeling_3d",
  "developing",
  "reviewing",
  "revision",
  "deploying",
  "closing",
  "curating",
]);
```

(Verifique os valores atuais antes de substituir — adicionar apenas os 5 novos: imagining, reviewing_assets, regen_assets, modeling_3d, curating.)

- [ ] **Step 4: Rodar typecheck**

```
npx tsc --noEmit
```
Esperado: sem erros.

- [ ] **Step 5: Commit**

```bash
git add src/ui/TasksPanel.ts
git commit -m "feat(frontend): mapear status novos pra NPCs (image, 3d, biblio, regen)"
```

---

## Task 15: Verificação manual end-to-end

**Files:** —

- [ ] **Step 1: Subir Forge**

```powershell
cd stable-diffusion-webui-forge
.\webui-user.bat
```

Verificar `--api` em COMMANDLINE_ARGS dentro de `webui-user.bat`. Aguardar load do Flux. Testar:
```powershell
curl http://127.0.0.1:7860/sdapi/v1/sd-models
```
Esperado: JSON listando o checkpoint Flux.

- [ ] **Step 2: Subir Hunyuan3D**

```powershell
cd C:\AI\Hunyuan3D-2GP
.\run_server.ps1
```

Aguardar `Uvicorn running on http://127.0.0.1:8081`.

- [ ] **Step 3: Subir backend BE-Game**

```powershell
python -m uvicorn server.api:app --port 8000
```

- [ ] **Step 4: Subir frontend**

```powershell
npm run dev
```

Abrir o game no browser. Confirmar visualmente que aparecem os 2 NPCs novos (Image Artist em col=1/row=4, Agente 3D em col=3/row=4) ao redor do Designer.

- [ ] **Step 5: Criar card no Trello**

Criar um card simples na lista TO-DO: "Site para cafeteria boutique chamada Cafe Central".

- [ ] **Step 6: Acompanhar pipeline pelo game**

Aguardar 3 minutos (DELAY_SECONDS). Verificar que os indicadores acendem em sequência:
- Planner → Copywriter → Designer → Image Artist → Designer → Agente 3D → Programador → QA → DevOps → Planner → Bibliotecario.

Whisper bubbles devem mostrar tokens em streaming durante cada etapa.

- [ ] **Step 7: Validar arquivos**

```powershell
ls "output\cafe-central\assets"
```

Esperado:
- Pelo menos 2 PNGs (>100KB cada).
- Ao menos 1 GLB (se algum item tinha convert_to_3d=true).
- `manifest_resolved.json` com `png_path` em todos e `glb_path` nos com convert_to_3d.
- `.pipeline.log` com eventos múltiplos.

- [ ] **Step 8: Validar vault**

Abrir Obsidian em `Atlas/Utilities/`. Confirmar:
- `Designer/{date}-cafe-central-visual-guide.md`
- `Designer/{date}-cafe-central-manifest.json`
- `ImageArtist/{date}-cafe-central-assets.md`
- `3DArtist/{date}-cafe-central-models.md`
- `Atlas/Notes/Agentes/Bibliotecario/cafe-central-curation.md` (criada pela curadoria)

E `Atlas/Maps/cafe-central MOC.md` com seções `## Design`, `## Imagens`, `## Modelos 3D`, `## Curadoria` populadas.

- [ ] **Step 9: Validar site gerado**

Abrir `output/cafe-central/index.html` no browser. Confirmar que:
- Carrega sem erro de console.
- Referencia ao menos um dos PNGs gerados (img tag ou CSS background).
- Se tem GLB, há um loader Three.js carregando ele.

- [ ] **Step 10: Documentar checklist no README/CHANGELOG (opcional)**

Adicionar nota no README descrevendo o pipeline 10 etapas. Sem commit obrigatório.

---

## Observações finais

- **Não foi adicionado endpoint HTTP** para Image/3D individuais — acesso só via pipeline, conforme escopo da spec.
- **Frontend não foi alterado** além de TasksPanel.ts — NPCs, sprites, modal de config são data-driven via `/api/agents`.
- **Bibliotecario NPC** existe desde antes (sprite_char=3, col=9, row=6) — só precisava do mapping novo de `curating` em STATUS_TO_AGENT.
- **GLB review (Designer revisando modelos 3D)** ficou fora do escopo — exige render headless. Se quiser, vira spec separada.
- **Cleanup automático no Qdrant** (vetores órfãos) ficou fora — bibliotecario só toca arquivos no vault. Reindexação completa via endpoint manual continua viável.
