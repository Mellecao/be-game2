# Habbo-style Chat Bubbles + Secretário + Multi-Chat Windows — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir o sistema de chat in-game atual por bolhas estilo Habbo Hotel moderno, multi-chat windows draggable, NPC Secretário acionado por T, e persistência SQLite de todas as mensagens dos agentes.

**Architecture:** Backend Python ganha SQLite `agent_messages` + helpers + 2 endpoints novos (`/api/chat/secretario`, `/api/chat/bibliotecario`). Frontend Pixi.js ganha `SpeechBubble` + `BubbleStack` substituindo o `whisperLabel` atual. UI HTML ganha `ChatWindow` draggable + `ChatWindowManager` (substitui `ChatPanel.ts`) + `PlayerChatInput` (T). Pipeline emite handoff via LLM ao fim de cada step do agente. Todos os agentes do pipeline ficam read-only no chat; só Secretário e Bibliotecário aceitam input.

**Tech Stack:** Python 3.11 (FastAPI, SQLite via stdlib `sqlite3`, CrewAI, OpenRouter), TypeScript + Pixi.js v8, Vite, GSAP (já no projeto pra animação).

**Spec:** `docs/superpowers/specs/2026-05-07-habbo-chat-bubbles-design.md`

**Sem framework de teste frontend** — TS valida via `tsc --noEmit`; verificação visual = smoke manual no browser. Backend tem TDD completo via pytest.

---

## Phase 1 — DB foundation

### Task 1: `server/db.py` — conexão SQLite

**Files:**
- Create: `server/db.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: Escrever teste**

Create `tests/test_db.py`:

```python
import os
from pathlib import Path

import pytest


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB_PATH", str(tmp_path / "test.db"))
    # forca recarregar o modulo pra pegar a env nova
    import importlib
    from server import db
    importlib.reload(db)
    db.init_schema()
    yield db
    

def test_init_schema_creates_table(temp_db):
    with temp_db.get_conn() as c:
        cur = c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='agent_messages'")
        assert cur.fetchone() is not None


def test_init_schema_creates_indexes(temp_db):
    with temp_db.get_conn() as c:
        cur = c.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='agent_messages'")
        names = {row[0] for row in cur.fetchall()}
        assert "idx_am_agent" in names
        assert "idx_am_slug" in names


def test_get_conn_returns_row_factory(temp_db):
    with temp_db.get_conn() as c:
        c.execute("INSERT INTO agent_messages (slug, agent_id, type, text, ts) VALUES (?, ?, ?, ?, ?)",
                  ("x", "researcher", "say", "hello", 1.0))
        row = c.execute("SELECT * FROM agent_messages").fetchone()
        assert row["agent_id"] == "researcher"
```

- [ ] **Step 2: Rodar — deve falhar**

Run: `pytest tests/test_db.py -v`
Expected: ERROR — `ModuleNotFoundError: No module named 'server.db'`.

- [ ] **Step 3: Implementar**

Create `server/db.py`:

```python
"""SQLite connection + schema init para agent_messages."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def _db_path() -> Path:
    return Path(os.environ.get("AGENT_DB_PATH", "agent_messages.db"))


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path()))
    conn.row_factory = sqlite3.Row
    return conn


def init_schema() -> None:
    with get_conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS agent_messages (
              id          INTEGER PRIMARY KEY AUTOINCREMENT,
              slug        TEXT NOT NULL,
              agent_id    TEXT NOT NULL,
              type        TEXT NOT NULL,
              text        TEXT NOT NULL,
              ts          REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_am_agent ON agent_messages(agent_id, ts DESC);
            CREATE INDEX IF NOT EXISTS idx_am_slug  ON agent_messages(slug, ts DESC);
        """)
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/test_db.py -v`
Expected: PASS (3 testes).

- [ ] **Step 5: Commit**

```bash
git add server/db.py tests/test_db.py
git commit -m "feat(db): add sqlite conn + agent_messages schema"
```

(Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>.)

---

### Task 2: `server/agent_messages.py` — record/history/recent

**Files:**
- Create: `server/agent_messages.py`
- Test: `tests/test_agent_messages.py`

- [ ] **Step 1: Escrever teste**

Create `tests/test_agent_messages.py`:

```python
import time

import pytest


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB_PATH", str(tmp_path / "test.db"))
    import importlib
    from server import db, agent_messages
    importlib.reload(db)
    importlib.reload(agent_messages)
    db.init_schema()
    yield agent_messages


def test_record_inserts_and_returns_id(temp_db, monkeypatch):
    emitted = []
    monkeypatch.setattr("server.event_bus.emit",
                        lambda kind, payload: emitted.append((kind, payload)))

    msg_id = temp_db.record("rose-beauty", "researcher", "say", "Pesquisa pronta.")
    assert msg_id > 0

    # SSE emitido
    assert len(emitted) == 1
    assert emitted[0][0] == "agent_message"
    payload = emitted[0][1]
    import json
    p = json.loads(payload) if isinstance(payload, str) else payload
    assert p["agent_id"] == "researcher"
    assert p["type"] == "say"


def test_history_returns_chronological_asc(temp_db):
    base = time.time()
    temp_db.record("x", "researcher", "whisper", "msg1")
    time.sleep(0.01)
    temp_db.record("x", "researcher", "say", "msg2")
    time.sleep(0.01)
    temp_db.record("x", "designer", "say", "msg3")  # outro agente

    hist = temp_db.history("researcher")
    assert len(hist) == 2
    assert hist[0]["text"] == "msg1"
    assert hist[1]["text"] == "msg2"


def test_history_respects_limit(temp_db):
    for i in range(10):
        temp_db.record("x", "a", "say", f"msg{i}")
    hist = temp_db.history("a", limit=5)
    assert len(hist) == 5
    # ultimas 5, em ordem cronologica asc
    assert hist[0]["text"] == "msg5"
    assert hist[-1]["text"] == "msg9"


def test_recent_filters_by_slug_and_since(temp_db):
    temp_db.record("a", "x", "say", "old")
    cutoff = time.time()
    time.sleep(0.01)
    temp_db.record("a", "x", "say", "new1")
    temp_db.record("b", "x", "say", "other-slug")  # ignorado pelo filtro de slug

    out = temp_db.recent("a", since_ts=cutoff)
    assert len(out) == 1
    assert out[0]["text"] == "new1"
```

- [ ] **Step 2: Rodar — deve falhar**

Run: `pytest tests/test_agent_messages.py -v`
Expected: ERROR.

- [ ] **Step 3: Implementar**

Create `server/agent_messages.py`:

```python
"""Helpers de leitura/escrita de agent_messages + emite SSE."""
from __future__ import annotations

import json
import time
from typing import Any

from . import db
from . import event_bus


def record(slug: str, agent_id: str, type: str, text: str) -> int:
    """Insere msg + emite SSE 'agent_message'. Retorna id da row."""
    ts = time.time()
    with db.get_conn() as c:
        cur = c.execute(
            "INSERT INTO agent_messages (slug, agent_id, type, text, ts) VALUES (?, ?, ?, ?, ?)",
            (slug, agent_id, type, text, ts),
        )
        msg_id = cur.lastrowid

    payload = json.dumps({
        "id": msg_id,
        "slug": slug,
        "agent_id": agent_id,
        "type": type,
        "text": text,
        "ts": ts,
    }, ensure_ascii=False)
    event_bus.emit("agent_message", payload)
    return msg_id


def history(agent_id: str, limit: int = 200) -> list[dict[str, Any]]:
    """Ultimas N msgs do agente, ordem cronologica asc."""
    with db.get_conn() as c:
        rows = c.execute(
            "SELECT * FROM (SELECT * FROM agent_messages WHERE agent_id = ? ORDER BY ts DESC LIMIT ?) "
            "ORDER BY ts ASC",
            (agent_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def recent(slug: str, since_ts: float, limit: int = 100) -> list[dict[str, Any]]:
    """Msgs do projeto desde timestamp."""
    with db.get_conn() as c:
        rows = c.execute(
            "SELECT * FROM agent_messages WHERE slug = ? AND ts >= ? ORDER BY ts ASC LIMIT ?",
            (slug, since_ts, limit),
        ).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/test_agent_messages.py -v`
Expected: PASS (4 testes).

- [ ] **Step 5: Commit**

```bash
git add server/agent_messages.py tests/test_agent_messages.py
git commit -m "feat(agent_messages): add record/history/recent with SSE emit"
```

---

## Phase 2 — Handoff generation

### Task 3: `server/handoff.py` — LLM-gen + cache + fallback

**Files:**
- Create: `server/handoff.py`
- Test: `tests/test_handoff.py`

- [ ] **Step 1: Escrever teste**

Create `tests/test_handoff.py`:

```python
def test_generate_handoff_returns_llm_output(monkeypatch):
    from server import handoff
    monkeypatch.setattr(handoff, "_call_llm",
                        lambda prompt: "Pesquisa pronta, 5 refs, passando pro Copy.")

    handoff._generate_cached.cache_clear()
    out = handoff.generate_handoff("researcher", "Researcher", "5 refs do Frankenstein", "Copywriter")
    assert "passando pro Copy" in out


def test_generate_handoff_truncates_to_140(monkeypatch):
    from server import handoff
    monkeypatch.setattr(handoff, "_call_llm", lambda p: "x" * 500)
    handoff._generate_cached.cache_clear()
    out = handoff.generate_handoff("a", "A", "y", "B")
    assert len(out) <= 140


def test_generate_handoff_falls_back_on_exception(monkeypatch):
    from server import handoff
    def boom(p):
        raise RuntimeError("llm offline")
    monkeypatch.setattr(handoff, "_call_llm", boom)
    handoff._generate_cached.cache_clear()
    out = handoff.generate_handoff("dev", "Dev", "build ok", "QA")
    assert "Dev" in out
    assert "QA" in out


def test_generate_handoff_caches(monkeypatch):
    from server import handoff
    calls = []
    monkeypatch.setattr(handoff, "_call_llm",
                        lambda p: calls.append(p) or "ok")
    handoff._generate_cached.cache_clear()

    handoff.generate_handoff("a", "A", "did x", "B")
    handoff.generate_handoff("a", "A", "did x", "B")
    assert len(calls) == 1  # cached


def test_generate_handoff_handles_no_next_agent(monkeypatch):
    from server import handoff
    monkeypatch.setattr(handoff, "_call_llm",
                        lambda p: "Pipeline concluido.")
    handoff._generate_cached.cache_clear()
    out = handoff.generate_handoff("devops", "DevOps", "deploy ok", None)
    assert "concluido" in out.lower() or "DevOps" in out
```

- [ ] **Step 2: Rodar — deve falhar**

Run: `pytest tests/test_handoff.py -v`
Expected: ERROR.

- [ ] **Step 3: Implementar**

Create `server/handoff.py`:

```python
"""Gera mensagem curta de handoff entre agentes via LLM."""
from __future__ import annotations

from functools import lru_cache


def _call_llm(prompt: str) -> str:
    """Chama o llm global. Isolado em func separada pra ser mockavel."""
    from .agents import llm
    return llm.call(messages=[{"role": "user", "content": prompt}])


@lru_cache(maxsize=128)
def _generate_cached(agent_id: str, agent_name: str, what_summary: str, next_agent: str) -> str:
    prompt = (
        f"Voce e o {agent_name}. Acabou de entregar: {what_summary}.\n"
        f"Proximo agente: {next_agent or '(fim do pipeline)'}.\n"
        f"Em 1 frase <= 120 caracteres, em portugues coloquial, anuncie o que entregou "
        f"e pra quem passa. Sem meta-comentario, sem aspas."
    )
    try:
        out = _call_llm(prompt).strip()
        return out[:140]
    except Exception:
        return _fallback(agent_name, next_agent or "")


def _fallback(agent_name: str, next_agent: str) -> str:
    if next_agent:
        return f"{agent_name} terminou. Passando pro {next_agent}."
    return f"{agent_name} terminou."


def generate_handoff(agent_id: str, agent_name: str, what_was_done: str, next_agent: str | None) -> str:
    """Gera mensagem curta de transicao via LLM. Cacheia por hash do input."""
    return _generate_cached(agent_id, agent_name, what_was_done[:200], next_agent or "")
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/test_handoff.py -v`
Expected: PASS (5 testes).

- [ ] **Step 5: Commit**

```bash
git add server/handoff.py tests/test_handoff.py
git commit -m "feat(handoff): add LLM-generated handoff messages with lru_cache + fallback"
```

---

## Phase 3 — Endpoints + agent_messages_tools

### Task 4: `server/agent_messages_tools.py` — 3 tools pro Secretário

**Files:**
- Create: `server/agent_messages_tools.py`
- Test: `tests/test_agent_messages_tools.py`

- [ ] **Step 1: Escrever teste**

Create `tests/test_agent_messages_tools.py`:

```python
import time

import pytest


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB_PATH", str(tmp_path / "test.db"))
    import importlib
    from server import db, agent_messages
    importlib.reload(db)
    importlib.reload(agent_messages)
    db.init_schema()
    return agent_messages


def test_pipeline_status_returns_active_tasks(monkeypatch):
    from server import agent_messages_tools

    fake_tasks = [
        {"id": "t1", "card_name": "Rose Beauty", "status": "designing", "step": 4, "log": "Designer working..."},
    ]
    monkeypatch.setattr(agent_messages_tools, "_get_tasks_fn", lambda: fake_tasks)

    tool = agent_messages_tools.GetPipelineStatusTool()
    out = tool._run()
    assert "Rose Beauty" in out
    assert "designing" in out


def test_active_tasks_returns_summary(monkeypatch):
    from server import agent_messages_tools

    fake_tasks = [
        {"id": "t1", "card_name": "A", "status": "developing", "step": 7, "log": "Dev"},
        {"id": "t2", "card_name": "B", "status": "qa_crew", "step": 9, "log": "QA"},
    ]
    monkeypatch.setattr(agent_messages_tools, "_get_tasks_fn", lambda: fake_tasks)

    tool = agent_messages_tools.GetActiveTasksTool()
    out = tool._run()
    assert "2" in out
    assert "A" in out and "B" in out


def test_agent_history_returns_text_block(temp_db, monkeypatch):
    monkeypatch.setattr("server.event_bus.emit", lambda *a, **kw: None)
    temp_db.record("x", "researcher", "say", "Pesquisa pronta.")
    temp_db.record("x", "researcher", "whisper", "Buscando refs...")

    from server import agent_messages_tools
    tool = agent_messages_tools.GetAgentHistoryTool()
    out = tool._run(agent_id="researcher", limit=10)
    assert "Pesquisa pronta" in out
    assert "Buscando refs" in out


def test_agent_history_handles_unknown_agent(temp_db):
    from server import agent_messages_tools
    tool = agent_messages_tools.GetAgentHistoryTool()
    out = tool._run(agent_id="ghost")
    assert "(sem mensagens)" in out or out.strip() == ""
```

- [ ] **Step 2: Rodar — deve falhar**

Run: `pytest tests/test_agent_messages_tools.py -v`
Expected: ERROR.

- [ ] **Step 3: Implementar**

Create `server/agent_messages_tools.py`:

```python
"""Tools usadas pelo agente Secretario pra ler estado do pipeline + historico."""
from __future__ import annotations

from datetime import datetime
from crewai.tools import BaseTool
from pydantic import Field

from . import agent_messages


def _get_tasks_fn():
    """Indireto pra ser mockavel em testes."""
    from .planner_loop import get_tasks
    return get_tasks()


class GetPipelineStatusTool(BaseTool):
    name: str = "get_pipeline_status"
    description: str = (
        "Retorna status compacto do pipeline atual: cards ativos, em que step cada um esta, "
        "e log curto. Use quando o usuario perguntar 'como esta o pipeline' ou 'o que esta rodando'."
    )

    def _run(self) -> str:
        tasks = _get_tasks_fn()
        if not tasks:
            return "Nenhum card ativo no momento."
        lines = []
        for t in tasks:
            card = t.get("card_name", "?")
            status = t.get("status", "?")
            step = t.get("step", 0)
            log = t.get("log", "")[:80]
            lines.append(f"- '{card}' (step {step}, status={status}): {log}")
        return f"{len(tasks)} card(s) ativo(s):\n" + "\n".join(lines)


class GetActiveTasksTool(BaseTool):
    name: str = "get_active_tasks"
    description: str = (
        "Lista nomes e status dos cards em execucao. Use quando o usuario "
        "perguntar 'quantos projetos rodando' ou 'quais cards'."
    )

    def _run(self) -> str:
        tasks = _get_tasks_fn()
        if not tasks:
            return "Sem cards ativos."
        active = [t for t in tasks if t.get("status") not in ("done", "error", "qa_blocked", "cancelled")]
        return f"{len(active)} card(s) em execucao: " + ", ".join(t.get("card_name", "?") for t in active)


class GetAgentHistoryTool(BaseTool):
    name: str = "get_agent_history"
    description: str = (
        "Retorna ultimas mensagens de um agente especifico. Use quando o usuario "
        "perguntar 'o que o Researcher disse' ou 'historico do Designer'. "
        "agent_id: id do agente (ex: researcher, designer, dev)."
    )
    limit: int = Field(default=20)

    def _run(self, agent_id: str, limit: int = 20) -> str:
        msgs = agent_messages.history(agent_id, limit=limit)
        if not msgs:
            return f"(sem mensagens registradas pra {agent_id})"
        lines = []
        for m in msgs[-limit:]:
            ts_str = datetime.fromtimestamp(m["ts"]).strftime("%H:%M")
            lines.append(f"[{ts_str}] ({m['type']}) {m['text']}")
        return "\n".join(lines)
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/test_agent_messages_tools.py -v`
Expected: PASS (4 testes).

- [ ] **Step 5: Commit**

```bash
git add server/agent_messages_tools.py tests/test_agent_messages_tools.py
git commit -m "feat: add 3 read-only tools for Secretario (pipeline status + tasks + agent history)"
```

---

### Task 5: `create_secretario` + `create_bibliotecario_agent` em `agents.py`

**Files:**
- Modify: `server/agents.py` (anexar)
- Test: `tests/test_new_agents.py` (anexar)

- [ ] **Step 1: Escrever teste**

Append em `tests/test_new_agents.py`:

```python


def test_create_secretario_has_3_tools():
    from server.agents import create_secretario
    from crewai import Agent
    agent = create_secretario()
    assert isinstance(agent, Agent)
    tool_names = {t.name for t in agent.tools}
    assert "get_pipeline_status" in tool_names
    assert "get_active_tasks" in tool_names
    assert "get_agent_history" in tool_names
    assert agent.allow_delegation is False


def test_create_bibliotecario_agent_has_vault_tools():
    from server.agents import create_bibliotecario_agent
    from crewai import Agent
    agent = create_bibliotecario_agent()
    assert isinstance(agent, Agent)
    tool_names = {t.name for t in agent.tools}
    # ferramenta principal: search no vault
    assert any("vault" in n for n in tool_names) or any("obsidian" in n for n in tool_names)
```

- [ ] **Step 2: Rodar — deve falhar**

Run: `pytest tests/test_new_agents.py -v -k "secretario or bibliotecario_agent"`
Expected: ERROR.

- [ ] **Step 3: Implementar**

Append em `server/agents.py`:

```python


def create_secretario() -> Agent:
    from .agent_messages_tools import (
        GetPipelineStatusTool, GetActiveTasksTool, GetAgentHistoryTool,
    )
    return Agent(
        role="Atendente do Player",
        goal=(
            "Responder duvidas do jogador sobre status do pipeline, atividades "
            "atuais e historico de execucao. Direto, em 1-3 frases, sem rodeio."
        ),
        backstory=(
            "Voce e o secretario da Black Elephant. Tem visao completa do que esta "
            "rodando no pipeline. Responde em portugues brasileiro, factual, sem "
            "inventar dados. Se nao souber, diz 'sem info no momento'."
        ),
        tools=[GetPipelineStatusTool(), GetActiveTasksTool(), GetAgentHistoryTool()],
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )


def create_bibliotecario_agent() -> Agent:
    """Agente Crew (NPC do jogo) - distinto dos hooks de librarian.py."""
    return Agent(
        role="Curador do Vault",
        goal=(
            "Buscar contexto no vault Obsidian e responder perguntas sobre "
            "projetos passados, padroes registrados, aprendizados arquivados."
        ),
        backstory=(
            "Voce e o bibliotecario da Black Elephant. Conhece o vault Ideaverse "
            "de cor. Antes de responder, sempre busca via obsidian_vault_search. "
            "Cita fontes (path da nota) quando possivel."
        ),
        tools=[get_vault_tool()],  # ja existe em agents.py imports
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )
```

- [ ] **Step 4: Rodar teste**

Run: `pytest tests/test_new_agents.py -v`
Expected: PASS (todos, incluindo existentes).

- [ ] **Step 5: Commit**

```bash
git add server/agents.py tests/test_new_agents.py
git commit -m "feat(agents): add create_secretario + create_bibliotecario_agent"
```

---

### Task 6: Endpoints `/api/chat/secretario` + `/api/chat/bibliotecario` + `/api/agents/{id}/messages`

**Files:**
- Modify: `server/api.py`
- Test: `tests/test_chat_endpoints.py`

- [ ] **Step 1: Escrever teste**

Create `tests/test_chat_endpoints.py`:

```python
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB_PATH", str(tmp_path / "test.db"))
    import importlib
    from server import db, agent_messages
    importlib.reload(db)
    importlib.reload(agent_messages)
    db.init_schema()
    from server import api
    importlib.reload(api)
    return TestClient(api.app)


def test_chat_secretario_returns_reply(client, monkeypatch):
    # mock o Crew kickoff pra nao chamar LLM real
    from server import api
    class FakeCrew:
        def __init__(self, *a, **kw): pass
        def kickoff(self):
            return "Pipeline ok, 1 card em design."
    monkeypatch.setattr(api, "Crew", FakeCrew)

    r = client.post("/api/chat/secretario", json={"message": "como ta o pipeline?"})
    assert r.status_code == 200
    body = r.json()
    assert "reply" in body
    assert "Pipeline" in body["reply"]


def test_chat_secretario_records_player_and_reply(client, monkeypatch):
    from server import api, agent_messages
    class FakeCrew:
        def __init__(self, *a, **kw): pass
        def kickoff(self): return "Resposta X"
    monkeypatch.setattr(api, "Crew", FakeCrew)

    client.post("/api/chat/secretario", json={"message": "hello"})

    # gravou player + reply
    from server import db
    with db.get_conn() as c:
        rows = c.execute("SELECT type, text FROM agent_messages ORDER BY ts").fetchall()
    types = [r["type"] for r in rows]
    assert "player" in types
    assert "reply" in types


def test_chat_bibliotecario_returns_reply(client, monkeypatch):
    from server import api
    class FakeCrew:
        def __init__(self, *a, **kw): pass
        def kickoff(self): return "Encontrei no vault."
    monkeypatch.setattr(api, "Crew", FakeCrew)

    r = client.post("/api/chat/bibliotecario", json={"message": "ja fizemos pricing saas?"})
    assert r.status_code == 200
    assert "reply" in r.json()


def test_get_agent_messages_returns_history(client, monkeypatch):
    from server import agent_messages
    monkeypatch.setattr("server.event_bus.emit", lambda *a, **kw: None)
    agent_messages.record("x", "researcher", "say", "msg1")
    agent_messages.record("x", "researcher", "say", "msg2")

    r = client.get("/api/agents/researcher/messages?limit=10")
    assert r.status_code == 200
    body = r.json()
    assert "messages" in body
    assert len(body["messages"]) == 2
    assert body["messages"][0]["text"] == "msg1"


def test_chat_secretario_rejects_empty_message(client):
    r = client.post("/api/chat/secretario", json={"message": ""})
    assert r.status_code == 400
```

- [ ] **Step 2: Rodar — deve falhar**

Run: `pytest tests/test_chat_endpoints.py -v`
Expected: ERROR (404 nas rotas).

- [ ] **Step 3: Implementar**

Modify `server/api.py` — anexar (não duplicar imports já presentes):

```python
# (no topo se nao tiver)
from crewai import Crew, Task
from . import agent_messages
from .agents import create_secretario, create_bibliotecario_agent
from . import db as _db

# init schema no startup
@app.on_event("startup")
def _init_agent_messages_db():
    _db.init_schema()


@app.post("/api/chat/secretario")
async def chat_secretario(payload: dict):
    message = (payload.get("message") or "").strip()
    if not message:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="mensagem vazia")

    # grava input do player
    agent_messages.record("global", "player", "player", message)

    agent = create_secretario()
    task = Task(
        description=(
            f"O jogador perguntou: '{message}'\n\n"
            "Use suas tools (get_pipeline_status, get_active_tasks, get_agent_history) "
            "pra responder com dados reais. 1-3 frases, direto."
        ),
        expected_output="Resposta curta em portugues brasileiro.",
        agent=agent,
    )
    crew = Crew(agents=[agent], tasks=[task], verbose=False)
    reply = str(crew.kickoff()).strip()

    agent_messages.record("global", "secretario", "reply", reply)
    return {"reply": reply}


@app.post("/api/chat/bibliotecario")
async def chat_bibliotecario(payload: dict):
    message = (payload.get("message") or "").strip()
    if not message:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="mensagem vazia")

    agent_messages.record("global", "player", "player", message)

    agent = create_bibliotecario_agent()
    task = Task(
        description=(
            f"O jogador perguntou: '{message}'\n\n"
            "Use obsidian_vault_search pra buscar contexto antes de responder. "
            "Cite a fonte (path da nota) quando aplicavel."
        ),
        expected_output="Resposta com contexto do vault, em portugues.",
        agent=agent,
    )
    crew = Crew(agents=[agent], tasks=[task], verbose=False)
    reply = str(crew.kickoff()).strip()

    agent_messages.record("global", "bibliotecario", "reply", reply)
    return {"reply": reply}


@app.get("/api/agents/{agent_id}/messages")
async def get_agent_messages(agent_id: str, limit: int = 200):
    msgs = agent_messages.history(agent_id, limit=limit)
    return {"messages": msgs}
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/test_chat_endpoints.py -v`
Expected: PASS (5 testes).

- [ ] **Step 5: Commit**

```bash
git add server/api.py tests/test_chat_endpoints.py
git commit -m "feat(api): add /api/chat/secretario + /api/chat/bibliotecario + /api/agents/{id}/messages"
```

---

## Phase 4 — NPCs novos no AGENT_SEED

### Task 7: Adicionar Secretário e Bibliotecário no AGENT_SEED

**Files:**
- Modify: `server/api.py` (AGENT_SEED + _AGENT_DISPLAY)
- Test: `tests/test_agent_seed.py` (anexar)

- [ ] **Step 1: Escrever teste**

Append em `tests/test_agent_seed.py`:

```python


def test_agent_seed_has_secretario():
    from server.api import AGENT_SEED
    ids = {a["id"] for a in AGENT_SEED}
    assert "secretario" in ids


def test_agent_seed_has_bibliotecario():
    from server.api import AGENT_SEED
    ids = {a["id"] for a in AGENT_SEED}
    assert "bibliotecario" in ids


def test_agent_display_has_new_npcs():
    from server.api import _AGENT_DISPLAY
    assert _AGENT_DISPLAY.get("secretario") == "Secretário"
    assert _AGENT_DISPLAY.get("bibliotecario") == "Bibliotecário"
```

- [ ] **Step 2: Rodar — deve falhar**

Run: `pytest tests/test_agent_seed.py -v`
Expected: 3 NEW failing.

- [ ] **Step 3: Implementar**

Modify `server/api.py`. Localize `AGENT_SEED` (lista de dicts) e adicione antes do fechamento da lista:

```python
{
    "id":           "secretario",
    "display_name": "Secretário",
    "role":         "Atendente do Player",
    "goal":         "Responder duvidas do jogador sobre o pipeline.",
    "backstory":    "Secretario da Black Elephant. Visao completa do pipeline.",
    "col":          0.5,
    "row":          0.5,
    "sprite_char":  4,
},
{
    "id":           "bibliotecario",
    "display_name": "Bibliotecário",
    "role":         "Curador do Vault",
    "goal":         "Buscar contexto no vault Obsidian.",
    "backstory":    "Bibliotecario da Black Elephant. Conhece o vault Ideaverse.",
    "col":          9.5,
    "row":          0.5,
    "sprite_char":  5,
},
```

(Se algum campo divergir do schema real do AGENT_SEED no codigo, copie do existente como template — o que importa eh `id`, `display_name`, `col`, `row`, `sprite_char`.)

E em `_AGENT_DISPLAY`:

```python
"secretario":   "Secretário",
"bibliotecario": "Bibliotecário",
```

- [ ] **Step 4: Rodar teste**

Run: `pytest tests/test_agent_seed.py -v`
Expected: PASS (todos).

- [ ] **Step 5: Commit**

```bash
git add server/api.py tests/test_agent_seed.py
git commit -m "feat(api): add secretario + bibliotecario NPCs to AGENT_SEED"
```

---

## Phase 5 — Whisper buffer + step_callback no planner_loop

### Task 8: Refactor `_on_llm_chunk` com debounce flush

**Files:**
- Modify: `server/planner_loop.py`
- Test: `tests/test_planner_whisper_flush.py`

- [ ] **Step 1: Escrever teste**

Create `tests/test_planner_whisper_flush.py`:

```python
import time

import pytest


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB_PATH", str(tmp_path / "test.db"))
    import importlib
    from server import db, agent_messages
    importlib.reload(db)
    importlib.reload(agent_messages)
    db.init_schema()
    return agent_messages


def test_whisper_buffer_accumulates_and_flushes(temp_db, monkeypatch):
    from server import planner_loop
    monkeypatch.setattr("server.event_bus.emit", lambda *a, **kw: None)

    # simula chunks chegando
    planner_loop._whisper_buffer_clear()
    planner_loop._whisper_buffer_append("researcher", "rose-beauty", "Buscando ")
    planner_loop._whisper_buffer_append("researcher", "rose-beauty", "refs no awwwards...")

    # ainda nao flushou
    assert len(temp_db.history("researcher")) == 0

    planner_loop._whisper_buffer_flush("researcher", "rose-beauty")
    msgs = temp_db.history("researcher")
    assert len(msgs) == 1
    assert msgs[0]["type"] == "whisper"
    assert "Buscando refs no awwwards" in msgs[0]["text"]


def test_whisper_buffer_independent_per_agent(temp_db, monkeypatch):
    from server import planner_loop
    monkeypatch.setattr("server.event_bus.emit", lambda *a, **kw: None)

    planner_loop._whisper_buffer_clear()
    planner_loop._whisper_buffer_append("researcher", "x", "abc")
    planner_loop._whisper_buffer_append("designer", "x", "xyz")

    planner_loop._whisper_buffer_flush("researcher", "x")
    planner_loop._whisper_buffer_flush("designer", "x")

    r = temp_db.history("researcher")
    d = temp_db.history("designer")
    assert r[0]["text"] == "abc"
    assert d[0]["text"] == "xyz"


def test_whisper_buffer_flush_empty_is_noop(temp_db, monkeypatch):
    from server import planner_loop
    monkeypatch.setattr("server.event_bus.emit", lambda *a, **kw: None)
    planner_loop._whisper_buffer_clear()
    planner_loop._whisper_buffer_flush("nobody", "x")
    assert temp_db.history("nobody") == []
```

- [ ] **Step 2: Rodar — deve falhar**

Run: `pytest tests/test_planner_whisper_flush.py -v`
Expected: ERROR (funcs nao existem).

- [ ] **Step 3: Implementar**

Em `server/planner_loop.py`, adicionar (perto do topo, depois dos imports):

```python
import threading as _threading_wb

# Buffer de whisper por agente (acumula chunks pra flushar como 1 mensagem)
_whisper_buffer: dict[str, dict] = {}  # agent_id -> {slug, text}
_whisper_buffer_lock = _threading_wb.Lock()


def _whisper_buffer_append(agent_id: str, slug: str, chunk: str) -> None:
    with _whisper_buffer_lock:
        entry = _whisper_buffer.setdefault(agent_id, {"slug": slug, "text": ""})
        entry["slug"] = slug
        entry["text"] += chunk


def _whisper_buffer_flush(agent_id: str, slug: str) -> None:
    """Flush do buffer pro DB (whisper). Chamado em step transitions ou debounce."""
    from . import agent_messages
    with _whisper_buffer_lock:
        entry = _whisper_buffer.pop(agent_id, None)
    if not entry or not entry["text"].strip():
        return
    text = entry["text"].strip()[-600:]  # max 600 chars no whisper persistido
    agent_messages.record(slug, agent_id, "whisper", text)


def _whisper_buffer_clear() -> None:
    """Util pra testes."""
    with _whisper_buffer_lock:
        _whisper_buffer.clear()
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/test_planner_whisper_flush.py -v`
Expected: PASS (3 testes).

- [ ] **Step 5: Commit**

```bash
git add server/planner_loop.py tests/test_planner_whisper_flush.py
git commit -m "feat(planner): add whisper buffer with debounced flush to agent_messages"
```

---

### Task 9: Step callback chamando `generate_handoff` + `record('say')`

**Files:**
- Modify: `server/planner_loop.py`
- Test: `tests/test_planner_step_callback.py`

- [ ] **Step 1: Escrever teste**

Create `tests/test_planner_step_callback.py`:

```python
import pytest


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB_PATH", str(tmp_path / "test.db"))
    import importlib
    from server import db, agent_messages
    importlib.reload(db)
    importlib.reload(agent_messages)
    db.init_schema()
    return agent_messages


def test_emit_agent_step_records_say_with_handoff(temp_db, monkeypatch):
    from server import planner_loop, handoff
    monkeypatch.setattr("server.event_bus.emit", lambda *a, **kw: None)
    monkeypatch.setattr(handoff, "_call_llm", lambda p: "Pesquisa pronta, passando pro Copy.")
    handoff._generate_cached.cache_clear()

    planner_loop._emit_agent_step("researcher", "Researcher", "5 refs no Frankenstein", "copywriter", "rose-beauty")

    msgs = temp_db.history("researcher")
    assert len(msgs) == 1
    assert msgs[0]["type"] == "say"
    assert "Copy" in msgs[0]["text"]


def test_emit_agent_step_flushes_whisper_first(temp_db, monkeypatch):
    from server import planner_loop, handoff
    monkeypatch.setattr("server.event_bus.emit", lambda *a, **kw: None)
    monkeypatch.setattr(handoff, "_call_llm", lambda p: "fim")
    handoff._generate_cached.cache_clear()
    planner_loop._whisper_buffer_clear()

    planner_loop._whisper_buffer_append("designer", "x", "Pensando no manifest...")
    planner_loop._emit_agent_step("designer", "Designer", "manifest pronto", "image_artist", "x")

    msgs = temp_db.history("designer")
    types = [m["type"] for m in msgs]
    assert "whisper" in types
    assert "say" in types
    # whisper veio antes do say
    assert types.index("whisper") < types.index("say")
```

- [ ] **Step 2: Rodar — deve falhar**

Run: `pytest tests/test_planner_step_callback.py -v`
Expected: ERROR.

- [ ] **Step 3: Implementar**

Append em `server/planner_loop.py`:

```python
def _emit_agent_step(agent_id: str, agent_name: str, what_was_done: str,
                     next_agent: str | None, slug: str) -> None:
    """Chamado ao fim do step de um agente: flusha whisper, gera handoff, grava say."""
    from . import agent_messages
    from .handoff import generate_handoff

    # 1. Flush whisper pendente daquele agente
    _whisper_buffer_flush(agent_id, slug)

    # 2. Gera handoff via LLM (com cache + fallback)
    text = generate_handoff(agent_id, agent_name, what_was_done, next_agent)

    # 3. Grava say
    agent_messages.record(slug, agent_id, "say", text)
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/test_planner_step_callback.py -v`
Expected: PASS (2 testes).

- [ ] **Step 5: Commit**

```bash
git add server/planner_loop.py tests/test_planner_step_callback.py
git commit -m "feat(planner): _emit_agent_step flushes whisper + records say handoff"
```

---

### Task 10: Plugar `_emit_agent_step` no Crew via step_callback (e adaptar `_on_llm_chunk`)

**Files:**
- Modify: `server/planner_loop.py`

- [ ] **Step 1: Localizar `_on_llm_chunk`**

Run: `grep -n "_on_llm_chunk\|llm_chunk\|LLMStreamChunkEvent" server/planner_loop.py`

Esperar achar o handler atual que emite `llm_chunk` direto pro frontend (event_bus.emit).

- [ ] **Step 2: Modificar `_on_llm_chunk` pra alimentar o buffer**

Substituir o conteúdo de `_on_llm_chunk` por:

```python
@crewai_event_bus.on(LLMStreamChunkEvent)
def _on_llm_chunk(source, event: LLMStreamChunkEvent) -> None:
    task_id = getattr(_tls, "task_id", None)
    slug = getattr(_tls, "slug", None)
    agent_id = getattr(_tls, "current_agent_id", None)

    if task_id and event.chunk:
        # Mantem o stream pro frontend (whisper visual em tempo real)
        event_bus.emit("llm_chunk", json.dumps({"task_id": task_id, "text": event.chunk}))

        # Acumula no buffer pra flush posterior (persiste no DB)
        if slug and agent_id:
            _whisper_buffer_append(agent_id, slug, event.chunk)
```

(Adicionar `slug` e `current_agent_id` ao `_tls` no `_run_pipeline` pode requerer set/get conforme o crew transita entre agentes. Se a integracao com o Crew hierarchical nao expor essa info diretamente, deixar o `current_agent_id` como `None` por agora — a Phase 9 do spec pode refinar via callback do CrewAI quando a infraestrutura estiver completa.)

- [ ] **Step 3: Adicionar step_callback nos 2 Crews (Criativo e QA) em `_run_pipeline`**

Localizar onde `Crew(...)` é instanciado dentro de `_run_pipeline`. Adicionar parâmetro `step_callback`:

```python
def _make_step_callback(slug: str, crew_kind: str):
    """Retorna callback que invoca _emit_agent_step ao fim de cada agent step."""
    def cb(step_output):
        # CrewAI step_output pode ser dict ou objeto. Tentamos extrair info defensiva.
        try:
            agent_role = getattr(getattr(step_output, "agent", None), "role", "")
            agent_id = _role_to_agent_id(agent_role)  # helper abaixo
            agent_name = AGENT_DISPLAY_NAME.get(agent_id, agent_role)
            output_text = str(getattr(step_output, "output", step_output))[:300]
            next_agent = _next_agent_in_crew(crew_kind, agent_id)
            if agent_id:
                _emit_agent_step(agent_id, agent_name, output_text, next_agent, slug)
        except Exception as e:
            import logging
            logging.getLogger(__name__).debug("step_callback skipped: %s", e)
    return cb


# Mapeamento role → agent_id (best-effort)
_ROLE_TO_AGENT_ID = {
    "Pesquisador de Referencias e Concorrencia": "researcher",
    "Copywriter de Landing Pages":               "copywriter",
    "Designer Visual":                            "designer",  # ajuste conforme role real
    "Artista Visual de IA":                       "image_artist",
    "Artista 3D":                                 "agente_3d",
    "UI/UX Designer Revisor":                     "designer_reviewer",
    "QA Code":                                    "qa_code",
    "QA Visual / UX Reviewer":                    "qa_visual",
    "Developer":                                  "dev",
}

def _role_to_agent_id(role: str) -> str | None:
    return _ROLE_TO_AGENT_ID.get(role)


# Ordem nominal dos agentes em cada crew (pra deduzir next_agent)
_CREW_ORDER = {
    "creative": ["researcher", "copywriter", "designer", "image_artist", "agente_3d", "designer_reviewer"],
    "qa":       ["qa_code", "qa_visual"],
}

def _next_agent_in_crew(crew_kind: str, current: str | None) -> str | None:
    order = _CREW_ORDER.get(crew_kind, [])
    if not current or current not in order:
        return None
    idx = order.index(current)
    return order[idx + 1] if idx + 1 < len(order) else None


# Mapeamento agent_id → display name (pode reusar AGENT_DISPLAY de api.py)
AGENT_DISPLAY_NAME = {
    "researcher":        "Researcher",
    "copywriter":        "Copywriter",
    "designer":          "Designer",
    "image_artist":      "Image Artist",
    "agente_3d":         "3D Artist",
    "designer_reviewer": "Designer Reviewer",
    "qa_code":           "QA Código",
    "qa_visual":         "QA Visual",
    "dev":               "Dev",
}
```

E nos 2 Crews:

```python
creative_crew = Crew(
    agents=[...],
    tasks=[create_creative_brief_task(...)],
    process=Process.hierarchical,
    manager_llm=llm,
    step_callback=_make_step_callback(slug, "creative"),  # NOVO
    verbose=False,
)

qa_crew = Crew(
    agents=[qa_code, qa_visual],
    tasks=[create_qa_brief_task(...)],
    process=Process.hierarchical,
    manager_llm=llm,
    step_callback=_make_step_callback(slug, "qa"),  # NOVO
    verbose=False,
)
```

- [ ] **Step 4: Rodar testes (regressão)**

Run: `pytest tests/test_pipeline.py tests/test_planner_step_callback.py tests/test_planner_whisper_flush.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add server/planner_loop.py
git commit -m "feat(planner): wire step_callback em ambos Crews para emitir handoff"
```

---

## Phase 6 — SpeechBubble + BubbleStack (Pixi)

### Task 11: `src/game/SpeechBubble.ts` — componente Pixi

**Files:**
- Create: `src/game/SpeechBubble.ts`

- [ ] **Step 1: Implementar**

Create `src/game/SpeechBubble.ts`:

```typescript
import { Container, Graphics, Text, Sprite, Texture, Assets } from 'pixi.js';

export type BubbleKind = 'say' | 'whisper' | 'player';

export interface SpeechBubbleOptions {
  agentName?: string;
  agentAvatar?: Texture;
  ttl?: number;
  maxWidth?: number;
}

const COLORS = {
  sayBg1: 0xfbbf24,
  sayBg2: 0xf59e0b,
  sayBorderInner: 0xffffff,
  sayBorderOuter: 0x92400e,
  whisperBg: 0xf3f4f6,
  whisperBorder: 0x9ca3af,
  whisperText: 0x374151,
  sayText: 0xffffff,
};

export class SpeechBubble extends Container {
  private bg = new Graphics();
  private avatar?: Sprite;
  private nameText?: Text;
  private bodyText: Text;
  private kind: BubbleKind;

  constructor(text: string, kind: BubbleKind, opts: SpeechBubbleOptions = {}) {
    super();
    this.kind = kind;

    const isWhisper = kind === 'whisper';
    const maxWidth = opts.maxWidth ?? (isWhisper ? 240 : 320);

    this.addChild(this.bg);

    if (!isWhisper && opts.agentAvatar) {
      this.avatar = new Sprite(opts.agentAvatar);
      this.avatar.width = 24;
      this.avatar.height = 24;
      this.avatar.x = 8;
      this.avatar.y = 6;
      // máscara circular
      const mask = new Graphics().circle(20, 18, 12).fill(0xffffff);
      this.avatar.mask = mask;
      this.addChild(this.avatar);
      this.addChild(mask);
    }

    if (!isWhisper && opts.agentName) {
      this.nameText = new Text({
        text: `${opts.agentName}:`,
        style: {
          fontFamily: 'system-ui',
          fontSize: 13,
          fontWeight: 'bold',
          fill: COLORS.sayText,
          wordWrap: false,
        },
      });
      this.nameText.x = (this.avatar ? 40 : 8);
      this.nameText.y = 8;
      this.addChild(this.nameText);
    }

    const textOffsetX = isWhisper ? 8 : (this.nameText ? this.nameText.x + this.nameText.width + 6 : 8);
    const textY = isWhisper ? 6 : 8;

    this.bodyText = new Text({
      text: this._truncateForWhisper(text, isWhisper),
      style: {
        fontFamily: 'system-ui',
        fontSize: isWhisper ? 12 : 13,
        fill: isWhisper ? COLORS.whisperText : COLORS.sayText,
        fontStyle: isWhisper ? 'italic' : 'normal',
        wordWrap: true,
        wordWrapWidth: maxWidth - textOffsetX - 8,
        breakWords: true,
        lineHeight: isWhisper ? 16 : 18,
      },
    });
    this.bodyText.x = textOffsetX;
    this.bodyText.y = textY;
    this.addChild(this.bodyText);

    this._drawBackground(maxWidth);
  }

  /** Atualiza texto in-place (usado pra whisper que muda conforme chunks). */
  updateText(text: string): void {
    this.bodyText.text = this._truncateForWhisper(text, this.kind === 'whisper');
    this._drawBackground(this.bodyText.style.wordWrapWidth ?? 240 + 16);
  }

  /** Animação fade-out via direct alpha (sem GSAP por simplicidade). */
  fadeOut(durationMs: number): Promise<void> {
    return new Promise((resolve) => {
      const start = performance.now();
      const startAlpha = this.alpha;
      const tick = () => {
        const elapsed = performance.now() - start;
        const t = Math.min(elapsed / durationMs, 1);
        this.alpha = startAlpha * (1 - t);
        if (t < 1) requestAnimationFrame(tick);
        else resolve();
      };
      requestAnimationFrame(tick);
    });
  }

  private _truncateForWhisper(text: string, isWhisper: boolean): string {
    if (!isWhisper) return text;
    // Max ~5 linhas. wordWrapWidth garante quebra; aqui truncamos por chars.
    const MAX_CHARS = 200;
    if (text.length <= MAX_CHARS) return text;
    return '…' + text.slice(-MAX_CHARS);
  }

  private _drawBackground(maxWidth: number): void {
    const w = Math.min(this.bodyText.x + this.bodyText.width + 8, maxWidth);
    const h = Math.max(
      (this.bodyText.y + this.bodyText.height + 8),
      (this.avatar ? 36 : 24),
    );

    this.bg.clear();
    if (this.kind === 'whisper') {
      this.bg.roundRect(0, 0, w, h, 10).fill({ color: COLORS.whisperBg, alpha: 0.85 });
      // borda tracejada simples
      this.bg.stroke({ color: COLORS.whisperBorder, width: 1 });
    } else {
      // gradiente fake: 2 retângulos stackados
      this.bg.roundRect(0, 0, w, h * 0.5, 14).fill(COLORS.sayBg1);
      this.bg.roundRect(0, h * 0.5, w, h * 0.5, 14).fill(COLORS.sayBg2);
      this.bg.roundRect(0, 0, w, h, 14).stroke({ color: COLORS.sayBorderOuter, width: 1 });
      this.bg.roundRect(2, 2, w - 4, h - 4, 12).stroke({ color: COLORS.sayBorderInner, width: 2 });
    }
  }
}
```

- [ ] **Step 2: Type check**

Run: `cd C:\Users\v27me\Videos\be-game && npx tsc --noEmit`
Expected: 0 errors em `src/game/SpeechBubble.ts`.

- [ ] **Step 3: Commit**

```bash
git add src/game/SpeechBubble.ts
git commit -m "feat(game): add SpeechBubble Pixi component (say/whisper/player)"
```

---

### Task 12: `src/game/BubbleStack.ts` — gerencia stack + slot whisper

**Files:**
- Create: `src/game/BubbleStack.ts`

- [ ] **Step 1: Implementar**

Create `src/game/BubbleStack.ts`:

```typescript
import { Container, Texture } from 'pixi.js';
import { SpeechBubble, BubbleKind } from './SpeechBubble';

const BASE_OFFSET = 40;
const GAP = 6;
const WHISPER_LOWER = 16;

export interface BubbleStackHost {
  /** Container do NPC (ou Player) — bubbles são adicionados como filhos. */
  addChild(child: Container): void;
  removeChild(child: Container): void;
}

export class BubbleStack {
  private container: Container;
  private stack: SpeechBubble[] = [];
  private whisperSlot: SpeechBubble | null = null;

  constructor(private host: BubbleStackHost) {
    this.container = new Container();
    host.addChild(this.container);
  }

  pushSay(text: string, agentName: string, agentAvatar: Texture | undefined, ttl?: number): void {
    this._push(text, 'say', { agentName, agentAvatar, ttl });
  }

  pushPlayer(text: string, playerAvatar: Texture | undefined, ttl?: number): void {
    this._push(text, 'player', { agentName: 'Você', agentAvatar: playerAvatar, ttl });
  }

  setWhisper(text: string, agentName?: string): void {
    if (this.whisperSlot) {
      this.whisperSlot.updateText(text);
    } else {
      this.whisperSlot = new SpeechBubble(text, 'whisper', { agentName });
      this.container.addChild(this.whisperSlot);
    }
    this._repositionWhisper();
  }

  clearWhisper(): void {
    if (!this.whisperSlot) return;
    const slot = this.whisperSlot;
    this.whisperSlot = null;
    slot.fadeOut(200).then(() => slot.destroy());
  }

  destroy(): void {
    for (const b of this.stack) b.destroy();
    this.whisperSlot?.destroy();
    this.container.destroy({ children: true });
  }

  private _push(text: string, kind: BubbleKind, opts: { agentName?: string; agentAvatar?: Texture; ttl?: number }): void {
    const bubble = new SpeechBubble(text, kind, opts);
    this.container.addChild(bubble);
    bubble.y = -BASE_OFFSET;

    // empurra existentes pra cima
    for (const existing of this.stack) {
      const targetY = existing.y - (bubble.height + GAP);
      this._tweenY(existing, targetY, 150);
    }
    this.stack.push(bubble);

    // se whisper estava ativo, agente terminou de pensar
    if (this.whisperSlot) this.clearWhisper();
    this._repositionWhisper();

    const computedTtl = opts.ttl ?? Math.min(2000 + text.length * 60, 8000);
    setTimeout(() => this._removeBubble(bubble), computedTtl);
  }

  private _repositionWhisper(): void {
    if (!this.whisperSlot) return;
    let stackBottom = -BASE_OFFSET;
    for (const b of this.stack) stackBottom = Math.min(stackBottom, b.y);
    this.whisperSlot.y = stackBottom + WHISPER_LOWER + this.whisperSlot.height;
  }

  private _removeBubble(bubble: SpeechBubble): void {
    bubble.fadeOut(300).then(() => {
      bubble.destroy();
      this.stack = this.stack.filter((b) => b !== bubble);
    });
  }

  private _tweenY(target: SpeechBubble, toY: number, durationMs: number): void {
    const fromY = target.y;
    const start = performance.now();
    const tick = () => {
      const elapsed = performance.now() - start;
      const t = Math.min(elapsed / durationMs, 1);
      const eased = 1 - Math.pow(1 - t, 2); // ease-out quad
      target.y = fromY + (toY - fromY) * eased;
      if (t < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }
}
```

- [ ] **Step 2: Type check**

Run: `npx tsc --noEmit`
Expected: 0 errors.

- [ ] **Step 3: Commit**

```bash
git add src/game/BubbleStack.ts
git commit -m "feat(game): add BubbleStack — manages say stack + whisper slot per NPC"
```

---

## Phase 7 — Refactor NPC.ts

### Task 13: Substituir `whisperLabel` por `BubbleStack` em NPC.ts

**Files:**
- Modify: `src/game/NPC.ts`

- [ ] **Step 1: Localizar o código atual**

Run: `grep -n "whisperLabel\|setWhisperChunk\|clearWhisper" src/game/NPC.ts`

- [ ] **Step 2: Refatorar**

Substituir `whisperLabel` (Pixi Text) por `BubbleStack`. No constructor da classe `NPC`:

```typescript
import { BubbleStack } from './BubbleStack';

// REMOVER: import/criação do whisperLabel (Text)

export class NPC {
  // ... outros campos
  bubbles: BubbleStack;

  constructor(/* params existentes */) {
    // ... setup existente do sprite, indicator, etc.
    
    // REMOVER: this.whisperLabel = new Text({...}); this.addChild(this.whisperLabel);

    // ADICIONAR (depois do sprite ser criado):
    this.bubbles = new BubbleStack(this.container);  // ou this — usa o que for o Container do NPC
  }

  // REMOVER: setWhisperChunk(chunk: string) { ... }
  // REMOVER: clearWhisper() { ... } -- ou delega:

  setWhisper(text: string): void {
    this.bubbles.setWhisper(text, this.displayName);
  }

  clearWhisper(): void {
    this.bubbles.clearWhisper();
  }

  pushSay(text: string, avatarTexture: Texture | undefined): void {
    this.bubbles.pushSay(text, this.displayName, avatarTexture);
  }
}
```

(Adapte `this.displayName`, `this.container` aos nomes reais do código atual — eles existem; só substituindo a peça do whisper.)

- [ ] **Step 3: Type check**

Run: `npx tsc --noEmit`
Expected: 0 errors. Se quebrar, ajustar imports e nomes de campos.

- [ ] **Step 4: Smoke test manual**

```bash
npm run dev
```

Abrir browser. Ainda sem mensagens reais (vamos ver no próximo phase). Confirmar que o jogo carrega sem erro JS.

- [ ] **Step 5: Commit**

```bash
git add src/game/NPC.ts
git commit -m "refactor(npc): replace whisperLabel with BubbleStack"
```

---

## Phase 8 — ChatWindow + Manager

### Task 14: `src/ui/chat-windows.css` — estilos

**Files:**
- Create: `src/ui/chat-windows.css`
- Modify: `index.html` (link)

- [ ] **Step 1: Implementar CSS**

Create `src/ui/chat-windows.css` com o conteúdo da Seção 9.4 do spec (já completo lá).

- [ ] **Step 2: Linkar no `index.html`**

Adicionar no `<head>`:
```html
<link rel="stylesheet" href="/src/ui/chat-windows.css">
```

- [ ] **Step 3: Commit**

```bash
git add src/ui/chat-windows.css index.html
git commit -m "feat(ui): add chat-windows.css for floating chat windows"
```

---

### Task 15: `src/ui/ChatWindow.ts`

**Files:**
- Create: `src/ui/ChatWindow.ts`

- [ ] **Step 1: Implementar**

Create `src/ui/ChatWindow.ts`:

```typescript
export interface AgentMessage {
  id?: number;
  type: 'whisper' | 'say' | 'player' | 'reply';
  text: string;
  ts: number;
  slug?: string;
}

const INPUT_ENABLED_AGENTS = new Set(['secretario', 'bibliotecario']);

export class ChatWindow {
  el: HTMLDivElement;
  private body: HTMLDivElement;
  private input: HTMLInputElement | null = null;
  private dragOffset: { x: number; y: number } | null = null;

  constructor(public agentId: string, private agentLabel: string) {
    this.el = document.createElement('div');
    this.el.className = 'chat-window';
    this.el.dataset.agentId = agentId;

    this.el.innerHTML = `
      <div class="chat-header" data-drag-handle>
        <img class="chat-avatar" alt="" />
        <span class="chat-title">${escapeHtml(agentLabel)}</span>
        <button class="chat-close" aria-label="Fechar">×</button>
      </div>
      <div class="chat-body"></div>
      ${INPUT_ENABLED_AGENTS.has(agentId) ? `
        <div class="chat-input-area">
          <input type="text" placeholder="Pergunte..." maxlength="500" />
        </div>
      ` : ''}
    `;

    this.body = this.el.querySelector('.chat-body')!;
    this.input = this.el.querySelector<HTMLInputElement>('.chat-input-area input');

    this._wireEvents();
    document.body.appendChild(this.el);
  }

  setPosition(pos: { left: number; top: number }): void {
    this.el.style.left = `${pos.left}px`;
    this.el.style.top = `${pos.top}px`;
  }

  setZIndex(z: number): void {
    this.el.style.zIndex = String(z);
  }

  async loadHistory(): Promise<void> {
    try {
      const r = await fetch(`/api/agents/${this.agentId}/messages?limit=200`);
      const data = await r.json();
      for (const m of data.messages || []) this.appendMessage(m);
    } catch (err) {
      console.error('chat history load failed', err);
    }
  }

  appendMessage(msg: AgentMessage): void {
    const div = document.createElement('div');
    div.className = `msg msg-${msg.type}`;
    const time = new Date(msg.ts * 1000).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    if (msg.type === 'say' || msg.type === 'reply') {
      div.innerHTML = `<b>${escapeHtml(this.agentLabel)}:</b> ${escapeHtml(msg.text)} <span class="msg-time">[${time}]</span>`;
    } else if (msg.type === 'player') {
      div.innerHTML = `<b>Você:</b> ${escapeHtml(msg.text)} <span class="msg-time">[${time}]</span>`;
    } else {
      div.innerHTML = `${escapeHtml(msg.text)} <span class="msg-time">[${time}]</span>`;
    }
    this.body.appendChild(div);
    this.body.scrollTop = this.body.scrollHeight;
  }

  destroy(): void {
    this.el.remove();
  }

  private _wireEvents(): void {
    const close = this.el.querySelector('.chat-close')!;
    close.addEventListener('click', () => {
      this.destroy();
      this._savePosition();
      const event = new CustomEvent('chatwindow:close', { detail: { agentId: this.agentId } });
      window.dispatchEvent(event);
    });

    const handle = this.el.querySelector<HTMLElement>('[data-drag-handle]')!;
    handle.addEventListener('mousedown', (e) => {
      const rect = this.el.getBoundingClientRect();
      this.dragOffset = { x: e.clientX - rect.left, y: e.clientY - rect.top };
      document.addEventListener('mousemove', this._onMouseMove);
      document.addEventListener('mouseup', this._onMouseUp);
    });

    this.el.addEventListener('click', () => {
      const event = new CustomEvent('chatwindow:focus', { detail: { agentId: this.agentId } });
      window.dispatchEvent(event);
    });

    if (this.input) {
      this.input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          const text = this.input!.value.trim();
          if (!text) return;
          this._submitMessage(text);
          this.input!.value = '';
        }
      });
    }
  }

  private _onMouseMove = (e: MouseEvent) => {
    if (!this.dragOffset) return;
    this.el.style.left = `${e.clientX - this.dragOffset.x}px`;
    this.el.style.top = `${e.clientY - this.dragOffset.y}px`;
  };

  private _onMouseUp = () => {
    this.dragOffset = null;
    document.removeEventListener('mousemove', this._onMouseMove);
    document.removeEventListener('mouseup', this._onMouseUp);
    this._savePosition();
  };

  private _savePosition(): void {
    const r = this.el.getBoundingClientRect();
    localStorage.setItem(`chat:${this.agentId}:pos`, JSON.stringify({ left: r.left, top: r.top }));
  }

  private async _submitMessage(text: string): Promise<void> {
    try {
      const r = await fetch(`/api/chat/${this.agentId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      });
      // Resposta vem por SSE (record() emite agent_message); window vai apender via Manager.
      if (!r.ok) console.error('chat submit failed', r.status);
    } catch (err) {
      console.error('chat submit error', err);
    }
  }
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[c]!);
}
```

- [ ] **Step 2: Type check**

Run: `npx tsc --noEmit`
Expected: 0 errors.

- [ ] **Step 3: Commit**

```bash
git add src/ui/ChatWindow.ts
git commit -m "feat(ui): add ChatWindow with drag + history load + input for secretario/bibliotecario"
```

---

### Task 16: `src/ui/ChatWindowManager.ts`

**Files:**
- Create: `src/ui/ChatWindowManager.ts`

- [ ] **Step 1: Implementar**

Create `src/ui/ChatWindowManager.ts`:

```typescript
import { ChatWindow, AgentMessage } from './ChatWindow';

const AGENT_LABELS: Record<string, string> = {
  researcher: 'Researcher',
  copywriter: 'Copywriter',
  designer: 'Designer',
  image_artist: 'Image Artist',
  agente_3d: '3D Artist',
  designer_reviewer: 'Designer Reviewer',
  qa_code: 'QA Código',
  qa_visual: 'QA Visual',
  dev: 'Dev',
  devops: 'DevOps',
  planner: 'Planner',
  secretario: 'Secretário',
  bibliotecario: 'Bibliotecário',
};

const Z_BASE = 1100;

export class ChatWindowManager {
  private windows = new Map<string, ChatWindow>();
  private nextZ = Z_BASE;

  constructor() {
    window.addEventListener('chatwindow:close', (e: Event) => {
      const detail = (e as CustomEvent).detail;
      this.windows.delete(detail.agentId);
    });
    window.addEventListener('chatwindow:focus', (e: Event) => {
      const detail = (e as CustomEvent).detail;
      this.bringToFront(detail.agentId);
    });
  }

  open(agentId: string): ChatWindow {
    const existing = this.windows.get(agentId);
    if (existing) {
      this.bringToFront(agentId);
      return existing;
    }
    const label = AGENT_LABELS[agentId] ?? agentId;
    const win = new ChatWindow(agentId, label);
    win.setPosition(this._computePosition(agentId));
    win.setZIndex(this.nextZ++);
    win.loadHistory();
    this.windows.set(agentId, win);
    return win;
  }

  close(agentId: string): void {
    const w = this.windows.get(agentId);
    if (!w) return;
    w.destroy();
    this.windows.delete(agentId);
  }

  bringToFront(agentId: string): void {
    const w = this.windows.get(agentId);
    if (w) w.setZIndex(this.nextZ++);
  }

  appendMessage(agentId: string, msg: AgentMessage): void {
    const w = this.windows.get(agentId);
    if (w) w.appendMessage(msg);
  }

  private _computePosition(agentId: string): { left: number; top: number } {
    const stored = localStorage.getItem(`chat:${agentId}:pos`);
    if (stored) {
      try {
        return JSON.parse(stored);
      } catch {}
    }
    const count = this.windows.size;
    return { left: 80 + count * 30, top: 200 + count * 30 };
  }
}
```

- [ ] **Step 2: Type check**

Run: `npx tsc --noEmit`
Expected: 0 errors.

- [ ] **Step 3: Commit**

```bash
git add src/ui/ChatWindowManager.ts
git commit -m "feat(ui): add ChatWindowManager singleton for multi-window coordination"
```

---

## Phase 9 — PlayerChatInput (T)

### Task 17: `src/ui/PlayerChatInput.ts`

**Files:**
- Create: `src/ui/PlayerChatInput.ts`

- [ ] **Step 1: Implementar**

Create `src/ui/PlayerChatInput.ts`:

```typescript
export class PlayerChatInput {
  private el: HTMLDivElement;
  private input: HTMLInputElement;
  private listeners: { onSubmit: (text: string) => void };

  constructor(opts: { onSubmit: (text: string) => void }) {
    this.listeners = opts;

    this.el = document.createElement('div');
    this.el.id = 'player-chat-input';
    this.el.classList.add('hidden');
    this.el.innerHTML = `<input type="text" placeholder="Pergunte ao Secretário..." maxlength="500" />`;
    document.body.appendChild(this.el);

    this.input = this.el.querySelector('input')!;
    this.input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        const text = this.input.value.trim();
        if (text) this.listeners.onSubmit(text);
        this._close();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        this._close();
      }
    });
  }

  toggle(): void {
    if (this.el.classList.contains('hidden')) this._open();
    else this._close();
  }

  isOpen(): boolean {
    return !this.el.classList.contains('hidden');
  }

  hasFocus(): boolean {
    return document.activeElement === this.input;
  }

  private _open(): void {
    this.el.classList.remove('hidden');
    this.input.value = '';
    this.input.focus();
  }

  private _close(): void {
    this.el.classList.add('hidden');
    this.input.value = '';
    this.input.blur();
  }
}
```

- [ ] **Step 2: Type check**

Run: `npx tsc --noEmit`
Expected: 0 errors.

- [ ] **Step 3: Commit**

```bash
git add src/ui/PlayerChatInput.ts
git commit -m "feat(ui): add PlayerChatInput component triggered by T key"
```

---

## Phase 10 — Wiring + AgentToast SSE routing

### Task 18: Refactor `AgentToast.ts` — escutar `agent_message` e rotear

**Files:**
- Modify: `src/ui/AgentToast.ts`

- [ ] **Step 1: Localizar handler atual**

Run: `grep -n "llm_chunk\|EventSource\|connectEventStream" src/ui/AgentToast.ts`

Esperar achar handler que escuta `llm_chunk` e chama `npcWhisperCallback`.

- [ ] **Step 2: Adicionar handler `agent_message`**

Em `AgentToast.connectEventStream` (ou método equivalente), adicionar:

```typescript
es.addEventListener('agent_message', (e: MessageEvent) => {
  let payload;
  try {
    payload = JSON.parse(e.data);
  } catch {
    return;
  }
  const { agent_id, type, text } = payload;

  // 1. roteia pra ChatWindowManager (se janela aberta, append)
  if (this.chatWindowManager) {
    this.chatWindowManager.appendMessage(agent_id, payload);
  }

  // 2. roteia pro NPC's BubbleStack
  const npc = this.npcRegistry?.[agent_id];
  if (!npc) return;

  if (type === 'whisper') {
    npc.setWhisper(text);
  } else if (type === 'say' || type === 'reply') {
    npc.pushSay(text, npc.avatarTexture);
    // pushSay limpa whisper internamente
  }
});
```

E ajustar o handler de `llm_chunk` existente: ele agora atualiza o whisper visual diretamente (já era o caso), mas a versão persistida virá pelo `agent_message` quando o backend flushar o buffer. Sem mudança no chunk handler — só passa a coexistir com o handler novo.

(Se a estrutura atual de `AgentToast` não expuser `chatWindowManager` e `npcRegistry`, adicionar estes campos via construtor ou setters.)

- [ ] **Step 3: Type check**

Run: `npx tsc --noEmit`

- [ ] **Step 4: Commit**

```bash
git add src/ui/AgentToast.ts
git commit -m "feat(ui): route agent_message SSE to ChatWindowManager + BubbleStack"
```

---

### Task 19: Wire em `main.ts` — T key, ChatWindowManager singleton, PlayerChatInput

**Files:**
- Modify: `src/main.ts`

- [ ] **Step 1: Adicionar wiring**

Em `src/main.ts`, depois da inicialização do Game:

```typescript
import { ChatWindowManager } from './ui/ChatWindowManager';
import { PlayerChatInput } from './ui/PlayerChatInput';

// Singleton manager
const chatWindowManager = new ChatWindowManager();

// Conectar ao AgentToast (se existir)
// agentToast.setChatWindowManager(chatWindowManager);  // adapte ao API real
// agentToast.setNpcRegistry(game.npcRegistry);          // adapte

// Player input ativado por T
const playerInput = new PlayerChatInput({
  onSubmit: async (text: string) => {
    // 1. Mostra bubble player imediatamente
    game.player?.pushSay(text);  // adapte se Player nao tiver bubbles ainda

    // 2. Mostra whisper "..." no Secretário NPC
    const secretarioNpc = game.npcRegistry?.['secretario'];
    secretarioNpc?.setWhisper('...');

    // 3. POST pro endpoint
    try {
      await fetch('/api/chat/secretario', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      });
    } catch (err) {
      console.error('chat secretario failed', err);
      secretarioNpc?.setWhisper('(erro de conexão)');
      setTimeout(() => secretarioNpc?.clearWhisper(), 3000);
    }
    // SSE 'agent_message' tipo 'reply' do Secretário vira pushSay automaticamente
  },
});

// Listener global: T toggle
window.addEventListener('keydown', (e) => {
  if (e.key !== 't' && e.key !== 'T') return;
  // ignora se ja tem outro input focado (ex: chat window aberto)
  const active = document.activeElement;
  if (active?.tagName === 'INPUT' || active?.tagName === 'TEXTAREA') {
    if (!playerInput.hasFocus()) return;
  }
  e.preventDefault();
  playerInput.toggle();
});
```

(Adapte `game.player`, `game.npcRegistry` aos nomes reais. Se Player nao tem `pushSay`, adicione um BubbleStack a ele em Phase 11.)

- [ ] **Step 2: Type check**

Run: `npx tsc --noEmit`

- [ ] **Step 3: Smoke browser**

```bash
npm run dev
```

Abrir browser, apertar T, confirmar que aparece input bottom-left. Digitar "oi", apertar Enter. Confirmar que sai sem erro JS no console (resposta real só funciona se backend estiver rodando com o /api/chat/secretario implementado).

- [ ] **Step 4: Commit**

```bash
git add src/main.ts
git commit -m "feat(main): wire T key + ChatWindowManager + PlayerChatInput → Secretario"
```

---

## Phase 11 — Player BubbleStack + W/A/S/D block

### Task 20: Adicionar BubbleStack ao Player + bloquear movimento quando input focado

**Files:**
- Modify: `src/game/Player.ts`

- [ ] **Step 1: Localizar Player.bindInput**

Run: `grep -n "bindInput\|keydown\|WASD\|ArrowUp" src/game/Player.ts`

- [ ] **Step 2: Adicionar BubbleStack no constructor**

```typescript
import { BubbleStack } from './BubbleStack';

// dentro do constructor do Player, depois do sprite:
this.bubbles = new BubbleStack(this.container);  // adapte ao container real

pushSay(text: string): void {
  this.bubbles.pushPlayer(text, this.avatarTexture);
}
```

- [ ] **Step 3: Bloquear movimento com input ativo**

No handler de keydown do Player (`bindInput` ou similar), no início:

```typescript
// se algum input do chat tem foco, ignora movimento
const active = document.activeElement;
if (active?.tagName === 'INPUT' || active?.tagName === 'TEXTAREA') return;
```

- [ ] **Step 4: Type check + browser smoke**

Run: `npx tsc --noEmit && npm run dev`
Abrir browser. Apertar T → input abre. Tentar W/A/S/D → Player não deve mover (input está focado). Esc → input fecha. W → Player anda novamente.

- [ ] **Step 5: Commit**

```bash
git add src/game/Player.ts
git commit -m "feat(player): add BubbleStack to player + block W/A/S/D when input focused"
```

---

## Phase 12 — Game integration: spawn novos NPCs + click handler

### Task 21: Spawn Secretário e Bibliotecário no jogo + click → ChatWindowManager.open

**Files:**
- Modify: `src/game/Game.ts`

- [ ] **Step 1: Localizar load de agents**

Run: `grep -n "AGENT_SEED\|loadAgents\|setNpcClickHandler\|api/agents" src/game/Game.ts`

- [ ] **Step 2: Confirmar que NPCs novos vem do AGENT_SEED**

O endpoint `GET /api/agents` (que já existe no backend) deve retornar os 2 novos NPCs (Task 7 já garantiu). O loop existente em `Game.ts` cria NPC pra cada entrada. Sem mudança aqui — só confirmar que os 2 aparecem no jogo.

- [ ] **Step 3: Wirar click handler pra abrir ChatWindow**

Localizar onde `setNpcClickHandler` é chamado (ou similar). Substituir o handler atual (que abre ChatPanel) por:

```typescript
this.setNpcClickHandler((agentId: string) => {
  chatWindowManager.open(agentId);
});
```

`chatWindowManager` deve estar exportado/passado de `main.ts`. Se Game.ts é instanciado antes do Manager, passar via setter.

- [ ] **Step 4: Type check + smoke**

Run: `npx tsc --noEmit && npm run dev`
Abrir browser. Confirmar que Secretário e Bibliotecário aparecem nos cantos. Click neles abre janela. Click em outro agente abre nova janela (paralela). Drag funciona.

- [ ] **Step 5: Commit**

```bash
git add src/game/Game.ts
git commit -m "feat(game): wire NPC click to ChatWindowManager + verify secretario/bibliotecario spawn"
```

---

## Phase 13 — Cleanup

### Task 22: Deletar `ChatPanel.ts` + remover `<div id="chat-panel">` do index.html

**Files:**
- Delete: `src/ui/ChatPanel.ts`
- Modify: `index.html`

- [ ] **Step 1: Confirmar que nada mais importa ChatPanel**

Run: `grep -rn "ChatPanel" src/ index.html`

Esperar: 0 matches (após Tasks anteriores). Se ainda houver matches em arquivos não editados, remover esses imports primeiro.

- [ ] **Step 2: Deletar arquivo**

```bash
rm src/ui/ChatPanel.ts
```

- [ ] **Step 3: Limpar `index.html`**

Remover o bloco:
```html
<div id="chat-panel" class="hidden">...</div>
```

- [ ] **Step 4: Type check + smoke**

Run: `npx tsc --noEmit && npm run dev`

- [ ] **Step 5: Commit**

```bash
git add -A src/ui/ChatPanel.ts index.html
git commit -m "chore: remove deprecated ChatPanel.ts and #chat-panel div"
```

---

## Phase 14 — Smoke test e2e

### Task 23: Smoke test end-to-end no backend

**Files:**
- Create: `tests/test_chat_pipeline_smoke.py`

- [ ] **Step 1: Escrever smoke test**

Create `tests/test_chat_pipeline_smoke.py`:

```python
"""Smoke test: verifica que pipeline + handoff + chat coexistem sem crashar imports."""
import pytest


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB_PATH", str(tmp_path / "test.db"))
    import importlib
    from server import db, agent_messages
    importlib.reload(db)
    importlib.reload(agent_messages)
    db.init_schema()
    return agent_messages


def test_full_chat_message_flow(temp_db, monkeypatch):
    """Player envia mensagem, Secretario responde, ambas ficam no DB."""
    from server import api, agent_messages
    from fastapi.testclient import TestClient

    class FakeCrew:
        def __init__(self, *a, **kw): pass
        def kickoff(self): return "Pipeline ok, 1 card em desenvolvimento."
    monkeypatch.setattr(api, "Crew", FakeCrew)
    monkeypatch.setattr("server.event_bus.emit", lambda *a, **kw: None)

    client = TestClient(api.app)
    r = client.post("/api/chat/secretario", json={"message": "como ta?"})
    assert r.status_code == 200

    # 2 mensagens registradas: player + reply
    history_player = agent_messages.history("player")
    history_secretario = agent_messages.history("secretario")
    assert len(history_player) >= 1
    assert len(history_secretario) >= 1
    assert history_secretario[-1]["text"] == "Pipeline ok, 1 card em desenvolvimento."


def test_handoff_records_say_message(temp_db, monkeypatch):
    """Quando _emit_agent_step roda, gera mensagem 'say' do agente."""
    from server import planner_loop, handoff
    monkeypatch.setattr("server.event_bus.emit", lambda *a, **kw: None)
    monkeypatch.setattr(handoff, "_call_llm", lambda p: "Refs prontas, indo pro Copy.")
    handoff._generate_cached.cache_clear()

    planner_loop._emit_agent_step("researcher", "Researcher", "5 refs", "copywriter", "rose-beauty")

    msgs = temp_db.history("researcher")
    assert any(m["type"] == "say" and "Copy" in m["text"] for m in msgs)


def test_history_endpoint_after_pipeline_run(temp_db):
    """GET /api/agents/{id}/messages retorna o historico do agent_messages."""
    from server import api, agent_messages
    from fastapi.testclient import TestClient

    agent_messages.record("rose-beauty", "designer", "say", "Manifest pronto.")
    client = TestClient(api.app)
    r = client.get("/api/agents/designer/messages?limit=10")
    assert r.status_code == 200
    body = r.json()
    assert any("Manifest pronto" in m["text"] for m in body["messages"])
```

- [ ] **Step 2: Rodar**

Run: `pytest tests/test_chat_pipeline_smoke.py -v`
Expected: PASS (3 testes).

- [ ] **Step 3: Commit**

```bash
git add tests/test_chat_pipeline_smoke.py
git commit -m "test(e2e): smoke test for chat + handoff + history endpoints"
```

---

### Task 24: Smoke test manual no browser + README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Anexar seção no README**

Append em `README.md`:

```markdown

## Smoke test manual: chat bubbles + Secretário

Pré-requisitos: api server + frontend rodando.

1. `python -m uvicorn server.api:app --reload --port 8000`
2. `npm run dev` (em outro terminal)
3. Abrir `http://localhost:5173` no browser

**Verificações:**
- Secretário (canto esquerdo) e Bibliotecário (canto direito) aparecem como NPCs
- Apertar **T** → input abre bottom-left
- Digitar "como ta o pipeline?" + Enter → bubble player aparece acima do Player, whisper "..." aparece acima do Secretário, depois bubble dourado com a resposta
- W/A/S/D não move o Player enquanto input está aberto
- **Esc** fecha input sem enviar
- Click no Bibliotecário → abre janela de chat com input
- Click em outro agente (ex: Researcher) → abre nova janela paralela, **sem input** (read-only)
- Drag das janelas funciona; close (×) salva posição em localStorage
- Subir um card real no Trello → ver whisper aparecer enquanto agente trabalha, depois bubble dourado com handoff ("Pesquisa pronta, passando pro Copy")
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add smoke test instructions for chat bubbles feature"
```

---

## Self-Review

### Cobertura do spec

- Seção 3 (tipos de bolha) — Tasks 11, 12 (Pixi components)
- Seção 4 (Secretário) — Tasks 4, 5, 6, 7
- Seção 5 (Bibliotecário NPC) — Tasks 5, 7
- Seção 6 (SQLite agent_messages) — Tasks 1, 2
- Seção 7 (handoff LLM) — Tasks 3, 9, 10
- Seção 8 (Pixi rendering) — Tasks 11, 12, 13
- Seção 9 (multi-chat windows) — Tasks 14, 15, 16
- Seção 10 (input do T) — Tasks 17, 19, 20
- Seção 11 (endpoints + SSE) — Tasks 6, 18
- Seção 12 (fluxos) — coberto via Tasks 18+19+20+23
- Seção 13 (file map) — todos os arquivos do mapa têm task
- Seção 14 (testing) — testes em todas as Tasks de backend; smoke manual nas de Pixi/UI

### Placeholder scan

Rescan: nenhum "TBD", "TODO", "implement later". Code blocks completos. Comandos exatos. Adapte-X quando há ambiguidade real (ex: nomes de campo do Player.ts) — esses são pontos onde o implementador inspeciona o código existente, não placeholders.

### Type consistency

- `BubbleStack.pushSay(text, agentName, agentAvatar?, ttl?)` — usado consistentemente em Tasks 12, 13
- `BubbleStack.pushPlayer(text, playerAvatar?, ttl?)` — Task 12, usado em Task 20
- `BubbleStack.setWhisper(text, agentName?)` / `clearWhisper()` — consistente
- `ChatWindow(agentId, agentLabel)` — Task 15, instanciado em Task 16 com `AGENT_LABELS[agentId]`
- `agent_messages.record(slug, agent_id, type, text)` — Tasks 2, 6, 9 usam mesma assinatura
- `handoff.generate_handoff(agent_id, agent_name, what_was_done, next_agent)` — Tasks 3, 9 usam mesma assinatura
- `_emit_agent_step(agent_id, agent_name, what_was_done, next_agent, slug)` — Task 9, chamado em Task 10 step_callback

Sem inconsistências detectadas.

### Itens não cobertos por task explícita

- **Drop shadow filter no `say` bubble** (Seção 8.1 do spec): omitido pra simplicidade; pode adicionar manualmente em Task 11 com `pixi.js/filter-drop-shadow` se quiser.
- **Bordas tracejadas no whisper** (Seção 8.1): implementação simplificada (borda sólida cinza) em Task 11. Visual ainda diferenciado por alpha 0.85 + italic + cor cinza. Suficiente pra MVP.
- **Cache LRU do `_role_to_agent_id`** (Task 10): map literal já é O(1). YAGNI.
- **`purge_older_than(days)`** (Seção 6.3): explicitamente fora de escopo.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-07-habbo-chat-bubbles.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
