# Agent Training Panel — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a right-side Agents drawer to BE-Game with agent profiles, editable CrewAI definitions, and a full training panel that creates/deletes `.md` files directly in the Obsidian vault and re-indexes into Qdrant.

**Architecture:** A new `AgentsPanel.ts` (frontend) follows the `TasksPanel.ts` pattern — HTML in `index.html`, CSS in `styles.css`, TypeScript class wired in `main.ts`. Five new FastAPI endpoints handle vault CRUD backed by three new functions in `obsidian_indexer.py`.

**Tech Stack:** FastAPI, Pydantic v2, qdrant-client ≥ 1.17, TypeScript, Vite, plain DOM manipulation (no frameworks).

---

## File Map

| Action | File |
|--------|------|
| Modify | `server/obsidian_indexer.py` — add `_iter_chunks_for_file`, `index_single_file`, `delete_file_chunks`, `get_agent_files` |
| Modify | `server/api.py` — add imports, models, helpers, 5 new endpoints |
| Modify | `requirements.txt` — add `python-multipart` |
| Modify | `index.html` — add agents FAB + panel HTML |
| Modify | `src/styles.css` — add agents panel CSS |
| Create | `src/ui/AgentsPanel.ts` — full panel component |
| Modify | `src/main.ts` — import and instantiate `AgentsPanel` |

---

## Task 1: Extend obsidian_indexer.py with single-file operations

**Files:**
- Modify: `server/obsidian_indexer.py`

- [ ] **Step 1: Refactor `_iter_chunks` to delegate to a new `_iter_chunks_for_file` helper**

In `server/obsidian_indexer.py`, replace the existing `_iter_chunks` function and add the new helper. The `_iter_chunks` loop becomes a one-liner:

```python
def _iter_chunks_for_file(file_path: Path) -> Iterator[dict]:
    """Yields payload dicts for every chunk in a single .md file."""
    rel   = file_path.relative_to(VAULT_PATH).as_posix()
    title = file_path.stem
    try:
        raw = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return
    meta, content = _parse_frontmatter(raw)
    tags = meta.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]
    up = meta.get("up", "")
    for heading, body in _split_sections(content):
        for chunk in _chunk_text(body):
            chunk = chunk.strip()
            if len(chunk) < 30:
                continue
            section_label = f"{title} › {heading}" if heading else title
            yield {
                "id":      str(uuid.uuid4()),
                "text":    f"{section_label}\n\n{chunk}",
                "title":   title,
                "section": heading,
                "content": chunk,
                "path":    rel,
                "tags":    tags,
                "up":      str(up),
            }


def _iter_chunks(vault: Path) -> Iterator[dict]:
    """Yields payload dicts for every chunk across all .md files."""
    for md in vault.rglob("*.md"):
        yield from _iter_chunks_for_file(md)
```

- [ ] **Step 2: Add `index_single_file`, `delete_file_chunks`, and `get_agent_files`**

Append these three public functions after `_iter_chunks` (before the `_ensure_collection` block):

```python
def index_single_file(file_path: str | Path) -> int:
    """Index a single .md file into Qdrant. Returns number of chunks upserted."""
    path   = Path(file_path)
    client = QdrantClient(url=QDRANT_URL)
    delete_file_chunks(path)
    chunks = list(_iter_chunks_for_file(path))
    if not chunks:
        return 0
    _upsert_batch(client, chunks)
    return len(chunks)


def delete_file_chunks(file_path: str | Path) -> None:
    """Delete all Qdrant points whose payload.path equals the given vault-relative path."""
    from qdrant_client.models import FilterSelector, Filter, FieldCondition, MatchValue
    path = Path(file_path)
    rel  = path.relative_to(VAULT_PATH).as_posix()
    client = QdrantClient(url=QDRANT_URL)
    try:
        client.delete(
            collection_name=COLLECTION,
            points_selector=FilterSelector(
                filter=Filter(must=[FieldCondition(key="path", match=MatchValue(value=rel))])
            ),
        )
    except Exception:
        pass  # collection may not exist yet


def get_agent_files(agent_id: str) -> list[dict]:
    """Scan vault for .md files that have `agent: {agent_id}` in their frontmatter."""
    results: list[dict] = []
    for md in VAULT_PATH.rglob("*.md"):
        try:
            raw = md.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        meta, content = _parse_frontmatter(raw)
        if meta.get("agent") != agent_id:
            continue
        tags = meta.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        results.append({
            "path":    md.relative_to(VAULT_PATH).as_posix(),
            "title":   md.stem,
            "preview": " ".join(content[:200].split()),
            "tags":    tags,
            "created": str(meta.get("created", "")),
        })
    return results
```

- [ ] **Step 3: Commit**

```bash
git add server/obsidian_indexer.py
git commit -m "feat: add single-file index/delete and agent-file scan to obsidian_indexer"
```

---

## Task 2: Add vault API endpoints to server/api.py

**Files:**
- Modify: `server/api.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Add `python-multipart` to requirements.txt**

Append to `requirements.txt`:
```
python-multipart>=0.0.9
```

- [ ] **Step 2: Add new imports at the top of `server/api.py`**

After the existing imports block, add:
```python
import base64
import datetime
import re
from pathlib import Path as _Path

import yaml as _yaml
from fastapi import File, UploadFile
```

- [ ] **Step 3: Add Pydantic models for vault endpoints**

After the existing `AgentUpdate` model, add:
```python
class VaultKnowledgeCreate(BaseModel):
    agent_id: str
    title: str
    content: str
    ace_type: str          # atlas|calendar|cards|efforts|resources|sources
    ace_subtype: str | None = None
    tags: list[str] = []
    rank: int | None = None
    effort_status: str | None = None   # on|ongoing|simmering
    date: str | None = None
    source_url: str | None = None
    source_author: str | None = None
    image_base64: str | None = None
    image_filename: str | None = None


class VaultKnowledgeDelete(BaseModel):
    path: str
    agent_id: str
```

- [ ] **Step 4: Add helper functions `_vault_file_path` and `_build_frontmatter`**

Add after `_sync_agent_configs` and before the first `@app.get`:
```python
_AGENT_DISPLAY = {
    "copywriter": "Copywriter",
    "vendedor": "Vendedor",
    "programador": "Programador",
    "planner": "Planner",
}


def _vault_file_path(req: VaultKnowledgeCreate) -> _Path:
    from .obsidian_indexer import VAULT_PATH
    safe = re.sub(r'[<>:"/\\|?*]', "", req.title).strip() or "nota"
    name = _AGENT_DISPLAY.get(req.agent_id, req.agent_id.capitalize())
    v = VAULT_PATH
    t, s = req.ace_type, req.ace_subtype or ""
    if t == "atlas":
        if s == "moc":
            return v / "Atlas" / "Maps" / f"{safe} MOC.md"
        return v / "Atlas" / "Notes" / "Agentes" / name / f"{safe}.md"
    if t == "calendar":
        d = req.date or datetime.date.today().isoformat()
        return v / "Calendar" / f"{d}-{safe}.md"
    if t == "cards":
        return v / "Atlas" / "Notes" / "Cards" / name / f"{safe}.md"
    if t == "efforts":
        folder_map = {"on": "On", "ongoing": "Ongoing", "simmering": "Simmering"}
        folder  = folder_map.get(req.effort_status or "on", "On")
        suffix  = "(OE)" if req.effort_status == "ongoing" else "(E)"
        return v / "Efforts" / folder / f"{safe} {suffix}.md"
    if t == "resources":
        return v / "Atlas" / "Utilities" / name / f"{safe}.md"
    if t == "sources":
        return v / "Atlas" / "Notes" / "Sources" / name / f"{safe}.md"
    return v / "Atlas" / "Notes" / "Agentes" / name / f"{safe}.md"


def _build_frontmatter(req: VaultKnowledgeCreate) -> str:
    today = datetime.date.today().isoformat()
    tags  = list(dict.fromkeys(["agente", req.agent_id] + req.tags))
    up_map = {
        "atlas":     "[[Black Elephant MOC]]",
        "calendar":  "[[Calendar]]",
        "cards":     "[[Atlas]]",
        "efforts":   "[[Efforts]]",
        "resources": "[[Atlas]]",
        "sources":   "[[Atlas]]",
    }
    fm: dict = {
        "up":      [up_map.get(req.ace_type, "[[Black Elephant MOC]]")],
        "agent":   req.agent_id,
        "tags":    tags,
        "created": today,
    }
    if req.rank is not None:
        fm["rank"] = req.rank
    if req.source_url:
        fm["source_url"] = req.source_url
    if req.source_author:
        fm["source_author"] = req.source_author
    return "---\n" + _yaml.dump(fm, allow_unicode=True, default_flow_style=False) + "---\n\n"
```

- [ ] **Step 5: Add the five vault endpoints**

Append after the existing `@app.get("/api/vault/status")` endpoint:

```python
@app.get("/api/vault/knowledge/{agent_id}")
async def get_vault_knowledge(agent_id: str):
    from . import obsidian_indexer
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, obsidian_indexer.get_agent_files, agent_id)


@app.post("/api/vault/knowledge")
async def create_vault_knowledge(req: VaultKnowledgeCreate):
    from . import obsidian_indexer

    image_link = ""
    if req.image_base64 and req.image_filename:
        img_dir = obsidian_indexer.VAULT_PATH / "Atlas" / "Utilities" / "Images"
        img_dir.mkdir(parents=True, exist_ok=True)
        img_data  = base64.b64decode(req.image_base64)
        img_fname = req.image_filename
        img_path  = img_dir / img_fname
        if img_path.exists():
            stem, ext = _Path(img_fname).stem, _Path(img_fname).suffix
            img_fname = f"{stem}_{int(datetime.datetime.now().timestamp())}{ext}"
            img_path  = img_dir / img_fname
        img_path.write_bytes(img_data)
        image_link = f"\n\n![[{img_fname}]]"

    file_path = _vault_file_path(req)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    if file_path.exists():
        stem      = file_path.stem
        file_path = file_path.parent / f"{stem}_{int(datetime.datetime.now().timestamp())}.md"

    body = _build_frontmatter(req) + f"# {req.title}\n\n{req.content}{image_link}"
    file_path.write_text(body, encoding="utf-8")

    indexed = False
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, obsidian_indexer.index_single_file, file_path)
        indexed = True
    except Exception:
        pass

    return {
        "path":    file_path.relative_to(obsidian_indexer.VAULT_PATH).as_posix(),
        "indexed": indexed,
    }


@app.delete("/api/vault/knowledge")
async def delete_vault_knowledge(req: VaultKnowledgeDelete):
    from . import obsidian_indexer
    file_path = obsidian_indexer.VAULT_PATH / req.path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, obsidian_indexer.delete_file_chunks, file_path)
    except Exception:
        pass
    file_path.unlink()
    return {"deleted": True}


@app.post("/api/vault/image")
async def upload_vault_image(file: UploadFile = File(...)):
    import shutil
    from . import obsidian_indexer
    if file.size and file.size > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Imagem maior que 10MB")
    img_dir = obsidian_indexer.VAULT_PATH / "Atlas" / "Utilities" / "Images"
    img_dir.mkdir(parents=True, exist_ok=True)
    fname    = file.filename or "image.png"
    img_path = img_dir / fname
    if img_path.exists():
        stem, ext = _Path(fname).stem, _Path(fname).suffix
        fname    = f"{stem}_{int(datetime.datetime.now().timestamp())}{ext}"
        img_path = img_dir / fname
    with img_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return {
        "vault_path":    img_path.relative_to(obsidian_indexer.VAULT_PATH).as_posix(),
        "markdown_link": f"![[{fname}]]",
    }


@app.post("/api/vault/reindex/{agent_id}")
async def reindex_agent_knowledge(agent_id: str):
    from . import obsidian_indexer
    loop  = asyncio.get_event_loop()
    files = await loop.run_in_executor(None, obsidian_indexer.get_agent_files, agent_id)
    count = 0
    for f in files:
        fp = obsidian_indexer.VAULT_PATH / f["path"]
        try:
            n = await loop.run_in_executor(None, obsidian_indexer.index_single_file, fp)
            count += n
        except Exception:
            pass
    return {"indexed_count": count}
```

- [ ] **Step 6: Commit**

```bash
git add server/api.py requirements.txt
git commit -m "feat: add vault knowledge CRUD and image upload endpoints"
```

---

## Task 3: Add HTML structure and CSS

**Files:**
- Modify: `index.html`
- Modify: `src/styles.css`

- [ ] **Step 1: Add agents FAB and panel to `index.html`**

Insert before the closing `</body>` tag (after the tasks panel block):

```html
    <!-- Agents FAB -->
    <button id="agents-fab">
      <span>👥</span>
      <span>Agentes</span>
    </button>

    <!-- Agents Panel (right-side drawer) -->
    <div id="agents-panel">
      <!-- View 1: Agent List -->
      <div id="agents-view-list" class="agents-view">
        <div class="agents-panel-header">
          <span>Agentes</span>
          <button id="agents-close">×</button>
        </div>
        <div id="agents-list"></div>
      </div>

      <!-- View 2: Agent Profile -->
      <div id="agents-view-profile" class="agents-view" style="display:none">
        <div class="agents-panel-header">
          <button id="agents-back-profile" class="agents-back">← Voltar</button>
          <span id="agents-profile-name"></span>
        </div>
        <div id="agents-profile-content"></div>
      </div>

      <!-- View 3: Training Panel -->
      <div id="agents-view-training" class="agents-view" style="display:none">
        <div class="agents-panel-header">
          <button id="agents-back-training" class="agents-back">← Voltar</button>
          <span id="agents-training-title"></span>
        </div>
        <div class="agents-tabs-bar">
          <button class="agents-tab active" data-tab="quick">Quick-Add</button>
          <button class="agents-tab" data-tab="novo">Novo Doc</button>
          <button class="agents-tab" data-tab="knowledge">Conhecimento</button>
        </div>
        <div id="agents-training-content"></div>
      </div>
    </div>
```

- [ ] **Step 2: Add CSS to `src/styles.css`**

Append to the end of `src/styles.css`:

```css
/* ── Agents FAB ─────────────────────────────────────────────────────────────── */
#agents-fab {
  position: fixed;
  bottom: 20px;
  right: 430px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 16px;
  background: #1e1e2e;
  color: #ccc;
  border: 2px solid #444;
  border-radius: 24px;
  cursor: pointer;
  font-size: 13px;
  font-family: inherit;
  font-weight: bold;
  z-index: 200;
  transition: background 0.15s, border-color 0.15s;
}
#agents-fab:hover { background: #2a2a42; border-color: #888; color: #fff; }

/* ── Agents Panel ────────────────────────────────────────────────────────────── */
#agents-panel {
  position: fixed;
  top: 0; right: 0;
  width: 420px;
  height: 100vh;
  background: #12121c;
  border-left: 2px solid #333;
  z-index: 150;
  transform: translateX(100%);
  transition: transform 0.25s ease;
  box-shadow: -4px 0 20px rgba(0,0,0,0.5);
  overflow: hidden;
}
#agents-panel.open { transform: translateX(0); }

.agents-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

.agents-panel-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  background: #1a1a2e;
  border-bottom: 2px solid #333;
  font-weight: bold;
  font-size: 14px;
  flex-shrink: 0;
}
.agents-panel-header span { flex: 1; }

#agents-close {
  background: #c0392b; color: white; border: none;
  width: 28px; height: 28px; cursor: pointer;
  font-weight: bold; border-radius: 4px;
}
#agents-close:hover { background: #e74c3c; }

.agents-back {
  background: none; color: #888; border: none;
  cursor: pointer; font-size: 13px;
  padding: 2px 6px; border-radius: 4px;
}
.agents-back:hover { color: #eee; background: #2a2a3a; }

/* Agent list */
#agents-list {
  flex: 1; overflow-y: auto;
  padding: 12px;
  display: flex; flex-direction: column; gap: 8px;
}

.agent-card {
  display: flex; align-items: center; gap: 12px;
  padding: 12px; background: #1a1a2e;
  border: 1px solid #333; border-radius: 8px;
  cursor: pointer;
  transition: background 0.12s, border-color 0.12s;
}
.agent-card:hover { background: #22223e; border-color: #555; }

.agent-card-avatar {
  width: 42px; height: 42px;
  background: #2980b9; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-weight: bold; font-size: 16px; color: white; flex-shrink: 0;
}
.agent-card-name { font-weight: bold; font-size: 14px; }
.agent-card-role { font-size: 12px; color: #888; margin-top: 2px; }

/* Profile view */
#agents-profile-content {
  flex: 1; overflow-y: auto;
  padding: 16px;
  display: flex; flex-direction: column; gap: 12px;
}
.agent-profile-avatar {
  width: 64px; height: 64px;
  background: #2980b9; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 26px; font-weight: bold; color: white;
  margin: 4px auto 8px;
}
.agent-profile-name { text-align: center; font-weight: bold; font-size: 18px; }
.agent-profile-role  { text-align: center; font-size: 12px; color: #888; }

.agent-crew-section h4 {
  font-size: 11px; text-transform: uppercase;
  color: #555; letter-spacing: 0.08em;
  margin: 8px 0 6px;
}
.agent-edit-field {
  width: 100%; padding: 8px;
  background: #0d0d1a; border: 1px solid #333;
  color: #eee; border-radius: 4px;
  font-size: 13px; font-family: inherit; resize: vertical;
  transition: border-color 0.12s;
}
.agent-edit-field:focus { outline: none; border-color: #2980b9; }

.agent-train-btn {
  width: 100%; padding: 12px;
  background: #6c3483; color: white; border: none;
  border-radius: 6px; cursor: pointer;
  font-size: 14px; font-weight: bold; font-family: inherit;
  transition: background 0.12s;
}
.agent-train-btn:hover { background: #8e44ad; }

/* Training tabs */
.agents-tabs-bar {
  display: flex; border-bottom: 2px solid #333; flex-shrink: 0;
}
.agents-tab {
  flex: 1; padding: 10px 6px;
  background: none; color: #666; border: none;
  cursor: pointer; font-size: 12px; font-family: inherit; font-weight: bold;
  border-bottom: 2px solid transparent; margin-bottom: -2px;
  transition: color 0.12s, background 0.12s;
}
.agents-tab:hover { color: #ccc; background: #1a1a2e; }
.agents-tab.active { color: #9b59b6; border-bottom-color: #9b59b6; }

#agents-training-content { flex: 1; overflow-y: auto; padding: 12px; }

/* ACE grid */
.ace-grid { display: flex; flex-direction: column; gap: 6px; }
.ace-card-wrapper { border-radius: 8px; overflow: hidden; border: 1px solid #333; }
.ace-card {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 12px; background: #1a1a2e;
  cursor: pointer; transition: background 0.12s;
}
.ace-card:hover, .ace-card.ace-card-open { background: #22223e; }
.ace-card-icon  { font-size: 18px; flex-shrink: 0; }
.ace-card-label { font-weight: bold; font-size: 13px; }
.ace-card-desc  { font-size: 11px; color: #666; flex: 1; text-align: right; }

.ace-form-container { background: #0f0f1d; border-top: 1px solid #2a2a3a; }
.ace-form { padding: 12px; display: flex; flex-direction: column; gap: 8px; }

/* Form shared */
.form-group { display: flex; flex-direction: column; gap: 4px; }
.form-group > label { font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: 0.05em; }
.form-toggle > label { display: flex; align-items: center; gap: 6px; font-size: 12px; text-transform: none; cursor: pointer; }

.form-input, .form-textarea, .form-select {
  padding: 7px 9px; background: #0d0d1a;
  border: 1px solid #333; color: #eee;
  border-radius: 4px; font-size: 13px; font-family: inherit;
}
.form-textarea { resize: vertical; }
.form-select   { appearance: none; }
.form-input:focus, .form-textarea:focus, .form-select:focus {
  outline: none; border-color: #8e44ad;
}
.form-select option { background: #1a1a2e; }

.ace-submit-btn {
  width: 100%; padding: 10px;
  background: #6c3483; color: white; border: none;
  border-radius: 6px; cursor: pointer;
  font-size: 13px; font-weight: bold; font-family: inherit;
  transition: background 0.12s;
}
.ace-submit-btn:hover:not(:disabled) { background: #8e44ad; }
.ace-submit-btn:disabled { background: #444; cursor: not-allowed; }

/* Novo Doc form */
.novo-doc-form { display: flex; flex-direction: column; gap: 10px; }

/* Image upload */
.image-drop-zone {
  border: 2px dashed #3a3a4a; border-radius: 6px;
  padding: 16px; text-align: center;
  color: #555; font-size: 12px; cursor: pointer;
  transition: border-color 0.12s, color 0.12s;
  display: flex; align-items: center; justify-content: center;
}
.image-drop-zone:hover, .image-drop-zone.dragover { border-color: #8e44ad; color: #ccc; }
.image-clear-btn {
  display: inline-block; margin-top: 6px;
  background: none; color: #e74c3c; border: none;
  cursor: pointer; font-size: 12px;
}

/* Knowledge tab */
.knowledge-toolbar { display: flex; gap: 8px; margin-bottom: 10px; align-items: center; }
.knowledge-toolbar .form-input { flex: 1; }
.reindex-btn {
  padding: 7px 10px; background: #0f2e1a; color: #2ecc71;
  border: 1px solid #2ecc71; border-radius: 4px;
  cursor: pointer; font-size: 11px; font-weight: bold;
  white-space: nowrap; font-family: inherit;
}
.reindex-btn:hover:not(:disabled) { background: #1a4a2a; }
.reindex-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.knowledge-loading, .knowledge-empty {
  text-align: center; color: #555; font-size: 13px; padding: 24px 16px;
}
.knowledge-card {
  padding: 10px 12px; background: #1a1a2e;
  border: 1px solid #2a2a3a; border-radius: 6px; margin-bottom: 6px;
}
.knowledge-card-header {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px;
}
.knowledge-title   { font-weight: bold; font-size: 13px; }
.knowledge-delete-btn {
  background: none; border: none; cursor: pointer;
  font-size: 14px; padding: 2px; opacity: 0.5;
  transition: opacity 0.12s;
}
.knowledge-delete-btn:hover { opacity: 1; }
.knowledge-path    { font-size: 11px; color: #444; margin-bottom: 4px; }
.knowledge-preview { font-size: 12px; color: #777; line-height: 1.4; }

/* Toast info (plain panel messages) */
.toast-info {
  background: #1a3a4a !important;
  border-left: 3px solid #3498db !important;
}
```

- [ ] **Step 3: Commit**

```bash
git add index.html src/styles.css
git commit -m "feat: add agents panel HTML structure and CSS"
```

---

## Task 4: Create src/ui/AgentsPanel.ts

**Files:**
- Create: `src/ui/AgentsPanel.ts`

- [ ] **Step 1: Create the file with the full implementation**

Create `src/ui/AgentsPanel.ts`:

```typescript
interface AgentData {
  id: string;
  display_name: string;
  role: string;
  goal: string;
  backstory: string;
  col: number;
  row: number;
  sprite_char: number;
}

interface KnowledgeItem {
  path: string;
  title: string;
  preview: string;
  tags: string[];
  created: string;
}

const ACE_CATEGORIES = [
  { id: "atlas",     icon: "🗺️",  label: "Atlas",     desc: "Conhecimento permanente e MOCs" },
  { id: "calendar",  icon: "📅",  label: "Calendar",  desc: "Registros temporais" },
  { id: "cards",     icon: "🃏",  label: "Cards",     desc: "Notas atômicas e curtas" },
  { id: "efforts",   icon: "🔥",  label: "Efforts",   desc: "Projetos ativos" },
  { id: "resources", icon: "📚",  label: "Resources", desc: "Biblioteca de consulta" },
  { id: "sources",   icon: "🌐",  label: "Sources",   desc: "O que vem de fora" },
];

export class AgentsPanel {
  private fab: HTMLElement;
  private panel: HTMLElement;
  private viewList: HTMLElement;
  private viewProfile: HTMLElement;
  private viewTraining: HTMLElement;
  private isOpen = false;
  private agents: AgentData[] = [];
  private currentAgent: AgentData | null = null;
  private currentTab = "quick";

  constructor() {
    this.fab          = document.getElementById("agents-fab")!;
    this.panel        = document.getElementById("agents-panel")!;
    this.viewList     = document.getElementById("agents-view-list")!;
    this.viewProfile  = document.getElementById("agents-view-profile")!;
    this.viewTraining = document.getElementById("agents-view-training")!;

    this.fab.addEventListener("click", () => this.toggle());
    document.getElementById("agents-close")!.addEventListener("click", () => this.close());
    document.getElementById("agents-back-profile")!.addEventListener("click", () => this.showView("list"));
    document.getElementById("agents-back-training")!.addEventListener("click", () => this.showView("profile"));

    document.querySelectorAll<HTMLElement>(".agents-tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        document.querySelectorAll(".agents-tab").forEach((t) => t.classList.remove("active"));
        tab.classList.add("active");
        this.currentTab = tab.dataset.tab!;
        if (this.currentAgent) this.renderTrainingTab();
      });
    });

    this.fetchAgents();
  }

  toggle(): void { this.isOpen ? this.close() : this.open(); }

  open(): void {
    this.isOpen = true;
    this.panel.classList.add("open");
  }

  close(): void {
    this.isOpen = false;
    this.panel.classList.remove("open");
  }

  private showView(view: "list" | "profile" | "training"): void {
    this.viewList.style.display     = view === "list"     ? "flex" : "none";
    this.viewProfile.style.display  = view === "profile"  ? "flex" : "none";
    this.viewTraining.style.display = view === "training" ? "flex" : "none";
  }

  // ── Agents List ─────────────────────────────────────────────────────────────

  private async fetchAgents(): Promise<void> {
    try {
      const res = await fetch("/api/agents");
      if (!res.ok) return;
      this.agents = await res.json();
      this.renderAgentList();
    } catch { /* ignore */ }
  }

  private renderAgentList(): void {
    const listEl = document.getElementById("agents-list")!;
    listEl.innerHTML = "";
    for (const agent of this.agents) {
      const card = document.createElement("div");
      card.className = "agent-card";
      card.innerHTML = `
        <div class="agent-card-avatar">${agent.display_name[0]}</div>
        <div class="agent-card-info">
          <div class="agent-card-name">${agent.display_name}</div>
          <div class="agent-card-role">${agent.role}</div>
        </div>
      `;
      card.addEventListener("click", () => this.openProfile(agent));
      listEl.appendChild(card);
    }
  }

  // ── Agent Profile ───────────────────────────────────────────────────────────

  private openProfile(agent: AgentData): void {
    this.currentAgent = agent;
    document.getElementById("agents-profile-name")!.textContent = agent.display_name;
    this.renderProfileContent();
    this.showView("profile");
  }

  private renderProfileContent(): void {
    const agent = this.currentAgent!;
    const el    = document.getElementById("agents-profile-content")!;
    el.innerHTML = `
      <div class="agent-profile-avatar">${agent.display_name[0]}</div>
      <div class="agent-profile-name">${agent.display_name}</div>
      <div class="agent-profile-role">${agent.role}</div>
      <div class="agent-crew-section">
        <h4>Definições CrewAI</h4>
        <div class="form-group">
          <label>Goal</label>
          <textarea id="agent-edit-goal" class="agent-edit-field" rows="3">${this.esc(agent.goal)}</textarea>
        </div>
        <div class="form-group">
          <label>Backstory</label>
          <textarea id="agent-edit-backstory" class="agent-edit-field" rows="5">${this.esc(agent.backstory)}</textarea>
        </div>
      </div>
      <button id="agent-train-btn" class="agent-train-btn">Treinar</button>
    `;

    el.querySelector<HTMLTextAreaElement>("#agent-edit-goal")!.addEventListener("blur", async (e) => {
      const val = (e.target as HTMLTextAreaElement).value;
      await this.saveAgentField(agent.id, "goal", val);
      agent.goal = val;
    });

    el.querySelector<HTMLTextAreaElement>("#agent-edit-backstory")!.addEventListener("blur", async (e) => {
      const val = (e.target as HTMLTextAreaElement).value;
      await this.saveAgentField(agent.id, "backstory", val);
      agent.backstory = val;
    });

    el.querySelector("#agent-train-btn")!.addEventListener("click", () => this.openTraining());
  }

  private async saveAgentField(agentId: string, field: string, value: string): Promise<void> {
    try {
      await fetch(`/api/agents/${agentId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ [field]: value }),
      });
    } catch { /* ignore */ }
  }

  // ── Training Panel ──────────────────────────────────────────────────────────

  private openTraining(): void {
    document.getElementById("agents-training-title")!.textContent =
      `Treinar: ${this.currentAgent!.display_name}`;
    this.currentTab = "quick";
    document.querySelectorAll(".agents-tab").forEach((t) => t.classList.remove("active"));
    document.querySelector<HTMLElement>('.agents-tab[data-tab="quick"]')!.classList.add("active");
    this.renderTrainingTab();
    this.showView("training");
  }

  private renderTrainingTab(): void {
    const container = document.getElementById("agents-training-content")!;
    container.innerHTML = "";
    if (this.currentTab === "quick")     this.renderQuickAdd(container);
    else if (this.currentTab === "novo") this.renderNovoDoc(container);
    else                                 this.renderKnowledge(container);
  }

  // ── Tab: Quick-Add ACE ───────────────────────────────────────────────────────

  private renderQuickAdd(container: HTMLElement): void {
    const grid = document.createElement("div");
    grid.className = "ace-grid";

    for (const cat of ACE_CATEGORIES) {
      const wrapper = document.createElement("div");
      wrapper.className = "ace-card-wrapper";

      const card = document.createElement("div");
      card.className = "ace-card";
      card.innerHTML = `
        <span class="ace-card-icon">${cat.icon}</span>
        <span class="ace-card-label">${cat.label}</span>
        <span class="ace-card-desc">${cat.desc}</span>
      `;

      const formContainer = document.createElement("div");
      formContainer.className = "ace-form-container";
      formContainer.style.display = "none";

      card.addEventListener("click", () => {
        const isOpen = formContainer.style.display !== "none";
        grid.querySelectorAll<HTMLElement>(".ace-form-container").forEach((f) => (f.style.display = "none"));
        grid.querySelectorAll(".ace-card").forEach((c) => c.classList.remove("ace-card-open"));
        if (!isOpen) {
          formContainer.style.display = "block";
          card.classList.add("ace-card-open");
          this.buildAceForm(cat.id, formContainer, card);
        }
      });

      wrapper.appendChild(card);
      wrapper.appendChild(formContainer);
      grid.appendChild(wrapper);
    }

    container.appendChild(grid);
  }

  private buildAceForm(aceType: string, container: HTMLElement, card: HTMLElement): void {
    const agent = this.currentAgent!;
    container.innerHTML = "";

    const form = document.createElement("form");
    form.className = "ace-form";

    form.appendChild(this.makeField("Título", "text", "ace-title", ""));

    if (aceType === "atlas") {
      form.appendChild(this.makeToggle("Criar como MOC?", "ace-is-moc"));
      form.appendChild(this.makeField("Conteúdo", "textarea", "ace-content", ""));
      form.appendChild(this.makeField("Tags (vírgula)", "text", "ace-tags", ""));
    } else if (aceType === "calendar") {
      const today = new Date().toISOString().split("T")[0];
      form.appendChild(this.makeField("Data", "date", "ace-date", today));
      form.appendChild(this.makeField("Conteúdo", "textarea", "ace-content", ""));
    } else if (aceType === "cards") {
      form.appendChild(this.makeField("Conteúdo (curto)", "textarea", "ace-content", "", 3));
      form.appendChild(this.makeField("Tags (vírgula)", "text", "ace-tags", ""));
    } else if (aceType === "efforts") {
      const statusGroup = document.createElement("div");
      statusGroup.className = "form-group";
      statusGroup.innerHTML = `<label>Status</label>
        <select id="ace-effort-status" class="form-select">
          <option value="on">🔥 On (Ativo)</option>
          <option value="ongoing">♻️ Ongoing</option>
          <option value="simmering">〰️ Simmering</option>
        </select>`;
      form.appendChild(statusGroup);
      form.appendChild(this.makeField("Rank (1-10)", "number", "ace-rank", "5"));
      form.appendChild(this.makeField("Conteúdo", "textarea", "ace-content", ""));
    } else if (aceType === "resources") {
      const typeGroup = document.createElement("div");
      typeGroup.className = "form-group";
      typeGroup.innerHTML = `<label>Tipo</label>
        <select id="ace-res-type" class="form-select">
          <option value="design">Design</option>
          <option value="manual">Manual</option>
          <option value="referencia">Referência</option>
        </select>`;
      form.appendChild(typeGroup);
      form.appendChild(this.makeField("Conteúdo", "textarea", "ace-content", ""));
      const imgGroup = document.createElement("div");
      imgGroup.className = "form-group";
      imgGroup.innerHTML = `<label>Imagem (opcional)</label>
        <input type="file" id="ace-image-input" accept="image/*" class="form-input" />
        <div id="ace-image-preview" style="display:none;margin-top:6px">
          <img id="ace-image-thumb" style="max-width:100%;max-height:100px;border-radius:4px" />
        </div>`;
      form.appendChild(imgGroup);
    } else if (aceType === "sources") {
      form.appendChild(this.makeField("Origem (URL ou autor)", "text", "ace-source-url", ""));
      const srcTypeGroup = document.createElement("div");
      srcTypeGroup.className = "form-group";
      srcTypeGroup.innerHTML = `<label>Tipo</label>
        <select id="ace-src-type" class="form-select">
          <option value="artigo">Artigo</option>
          <option value="video">Vídeo</option>
          <option value="livro">Livro</option>
          <option value="dado">Dado</option>
        </select>`;
      form.appendChild(srcTypeGroup);
      form.appendChild(this.makeField("Conteúdo", "textarea", "ace-content", ""));
    }

    const submitBtn = document.createElement("button");
    submitBtn.type = "submit";
    submitBtn.className = "ace-submit-btn";
    submitBtn.textContent = "Salvar e Indexar";
    form.appendChild(submitBtn);
    container.appendChild(form);

    // Wire image preview after form is in DOM
    if (aceType === "resources") {
      const imgInput = form.querySelector<HTMLInputElement>("#ace-image-input")!;
      imgInput.addEventListener("change", () => {
        const file = imgInput.files?.[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = (e) => {
          const thumb   = form.querySelector<HTMLImageElement>("#ace-image-thumb")!;
          const preview = form.querySelector<HTMLElement>("#ace-image-preview")!;
          thumb.src             = e.target!.result as string;
          preview.style.display = "block";
        };
        reader.readAsDataURL(file);
      });
    }

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      submitBtn.disabled    = true;
      submitBtn.textContent = "Salvando...";
      try {
        await this.submitAceForm(aceType, form, agent.id);
        card.classList.remove("ace-card-open");
        container.style.display = "none";
        this.showToast("✅ Salvo e indexado!");
      } catch {
        this.showToast("❌ Erro ao salvar");
      } finally {
        submitBtn.disabled    = false;
        submitBtn.textContent = "Salvar e Indexar";
      }
    });
  }

  private async submitAceForm(aceType: string, form: HTMLFormElement, agentId: string): Promise<void> {
    const val = (id: string) =>
      (form.querySelector<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>(`#${id}`)?.value ?? "");

    const body: Record<string, unknown> = {
      agent_id: agentId,
      title:    val("ace-title"),
      content:  val("ace-content"),
      ace_type: aceType,
      tags:     val("ace-tags").split(",").map((t) => t.trim()).filter(Boolean),
    };

    if (aceType === "atlas") {
      body.ace_subtype = (form.querySelector<HTMLInputElement>("#ace-is-moc")?.checked) ? "moc" : "notes";
    } else if (aceType === "calendar") {
      body.date = val("ace-date");
    } else if (aceType === "efforts") {
      body.effort_status = val("ace-effort-status");
      const rank = parseInt(val("ace-rank"));
      if (!isNaN(rank)) body.rank = rank;
    } else if (aceType === "resources") {
      body.ace_subtype = val("ace-res-type");
      const imgInput = form.querySelector<HTMLInputElement>("#ace-image-input");
      if (imgInput?.files?.[0]) {
        const { b64, filename } = await this.fileToBase64(imgInput.files[0]);
        body.image_base64    = b64;
        body.image_filename  = filename;
      }
    } else if (aceType === "sources") {
      body.source_url  = val("ace-source-url");
      body.ace_subtype = val("ace-src-type");
    }

    const res = await fetch("/api/vault/knowledge", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error("API error");
  }

  // ── Tab: Novo Documento ──────────────────────────────────────────────────────

  private renderNovoDoc(container: HTMLElement): void {
    const agent = this.currentAgent!;
    container.innerHTML = `
      <form id="novo-doc-form" class="novo-doc-form">
        <div class="form-group">
          <label>Título</label>
          <input type="text" id="novo-titulo" class="form-input" required />
        </div>
        <div class="form-group">
          <label>Destino</label>
          <select id="novo-destino" class="form-select">
            <option value="atlas/notes">Atlas / Notes</option>
            <option value="atlas/cards">Atlas / Cards</option>
            <option value="atlas/sources">Atlas / Sources</option>
            <option value="atlas/resources">Atlas / Resources</option>
            <option value="calendar">Calendar</option>
            <option value="efforts/on">Efforts / On</option>
            <option value="efforts/ongoing">Efforts / Ongoing</option>
            <option value="efforts/simmering">Efforts / Simmering</option>
          </select>
        </div>
        <div class="form-group">
          <label>Tags (vírgula)</label>
          <input type="text" id="novo-tags" class="form-input" placeholder="ex: copywriting, referencia" />
        </div>
        <div class="form-group">
          <label>Conteúdo (Markdown)</label>
          <textarea id="novo-content" class="form-textarea" rows="7"></textarea>
        </div>
        <div class="form-group">
          <label>Imagem (opcional)</label>
          <div class="image-drop-zone" id="novo-drop-zone">
            <span>Arraste uma imagem ou clique para selecionar</span>
            <input type="file" id="novo-image-input" accept="image/*" style="display:none" />
          </div>
          <div id="novo-image-preview" style="display:none;margin-top:6px">
            <img id="novo-image-thumb" style="max-width:100%;max-height:120px;border-radius:4px" />
            <button type="button" id="novo-image-clear" class="image-clear-btn">✕ Remover imagem</button>
          </div>
        </div>
        <button type="submit" class="ace-submit-btn">Salvar e Indexar</button>
      </form>
    `;

    const dropZone = container.querySelector<HTMLElement>("#novo-drop-zone")!;
    const imgInput = container.querySelector<HTMLInputElement>("#novo-image-input")!;
    const preview  = container.querySelector<HTMLElement>("#novo-image-preview")!;
    const thumb    = container.querySelector<HTMLImageElement>("#novo-image-thumb")!;

    dropZone.addEventListener("click", () => imgInput.click());
    dropZone.addEventListener("dragover", (e) => { e.preventDefault(); dropZone.classList.add("dragover"); });
    dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
    dropZone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropZone.classList.remove("dragover");
      const f = (e as DragEvent).dataTransfer?.files[0];
      if (f) this.previewImage(f, thumb, preview, dropZone);
    });
    imgInput.addEventListener("change", () => {
      if (imgInput.files?.[0]) this.previewImage(imgInput.files[0], thumb, preview, dropZone);
    });
    container.querySelector("#novo-image-clear")!.addEventListener("click", () => {
      imgInput.value        = "";
      preview.style.display = "none";
      dropZone.style.display = "flex";
    });

    container.querySelector<HTMLFormElement>("#novo-doc-form")!.addEventListener("submit", async (e) => {
      e.preventDefault();
      const btn = container.querySelector<HTMLButtonElement>(".ace-submit-btn")!;
      btn.disabled = true; btn.textContent = "Salvando...";
      try {
        const titulo  = container.querySelector<HTMLInputElement>("#novo-titulo")!.value;
        const destino = container.querySelector<HTMLSelectElement>("#novo-destino")!.value;
        const tags    = container.querySelector<HTMLInputElement>("#novo-tags")!.value
          .split(",").map((t) => t.trim()).filter(Boolean);
        const content = container.querySelector<HTMLTextAreaElement>("#novo-content")!.value;
        const { ace_type, ace_subtype, effort_status } = this.mapDestino(destino);

        const body: Record<string, unknown> = { agent_id: agent.id, title: titulo, content, ace_type, ace_subtype, tags };
        if (effort_status) body.effort_status = effort_status;

        if (imgInput.files?.[0]) {
          const { b64, filename } = await this.fileToBase64(imgInput.files[0]);
          body.image_base64   = b64;
          body.image_filename = filename;
        }

        const res = await fetch("/api/vault/knowledge", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!res.ok) throw new Error();

        this.showToast("✅ Documento salvo e indexado!");
        container.querySelector<HTMLFormElement>("#novo-doc-form")!.reset();
        imgInput.value = "";
        preview.style.display  = "none";
        dropZone.style.display = "flex";
      } catch {
        this.showToast("❌ Erro ao salvar documento");
      } finally {
        btn.disabled = false; btn.textContent = "Salvar e Indexar";
      }
    });
  }

  private mapDestino(d: string): { ace_type: string; ace_subtype: string; effort_status: string | null } {
    const map: Record<string, { ace_type: string; ace_subtype: string; effort_status: string | null }> = {
      "atlas/notes":       { ace_type: "atlas",     ace_subtype: "notes",  effort_status: null },
      "atlas/cards":       { ace_type: "cards",     ace_subtype: "",       effort_status: null },
      "atlas/sources":     { ace_type: "sources",   ace_subtype: "",       effort_status: null },
      "atlas/resources":   { ace_type: "resources", ace_subtype: "",       effort_status: null },
      "calendar":          { ace_type: "calendar",  ace_subtype: "daily",  effort_status: null },
      "efforts/on":        { ace_type: "efforts",   ace_subtype: "",       effort_status: "on" },
      "efforts/ongoing":   { ace_type: "efforts",   ace_subtype: "",       effort_status: "ongoing" },
      "efforts/simmering": { ace_type: "efforts",   ace_subtype: "",       effort_status: "simmering" },
    };
    return map[d] ?? { ace_type: "atlas", ace_subtype: "notes", effort_status: null };
  }

  // ── Tab: Conhecimento Atual ──────────────────────────────────────────────────

  private renderKnowledge(container: HTMLElement): void {
    const agent = this.currentAgent!;
    container.innerHTML = `
      <div class="knowledge-toolbar">
        <input type="text" id="knowledge-search" class="form-input" placeholder="Buscar título ou preview..." />
        <button id="knowledge-reindex" class="reindex-btn">Re-indexar tudo</button>
      </div>
      <div id="knowledge-list"><div class="knowledge-loading">Carregando...</div></div>
    `;

    let allItems: KnowledgeItem[] = [];

    container.querySelector("#knowledge-search")!.addEventListener("input", (e) => {
      const q = (e.target as HTMLInputElement).value.toLowerCase();
      this.renderKnowledgeItems(
        allItems.filter((i) => i.title.toLowerCase().includes(q) || i.preview.toLowerCase().includes(q)),
        agent.id,
        container,
      );
    });

    const reindexBtn = container.querySelector<HTMLButtonElement>("#knowledge-reindex")!;
    reindexBtn.addEventListener("click", async () => {
      reindexBtn.disabled = true; reindexBtn.textContent = "Indexando...";
      try {
        const res  = await fetch(`/api/vault/reindex/${agent.id}`, { method: "POST" });
        const data = await res.json();
        this.showToast(`✅ ${data.indexed_count} chunks re-indexados`);
      } catch {
        this.showToast("❌ Erro ao re-indexar");
      } finally {
        reindexBtn.disabled = false; reindexBtn.textContent = "Re-indexar tudo";
      }
    });

    fetch(`/api/vault/knowledge/${agent.id}`)
      .then((r) => r.json())
      .then((items: KnowledgeItem[]) => {
        allItems = items;
        this.renderKnowledgeItems(items, agent.id, container);
      })
      .catch(() => {
        container.querySelector("#knowledge-list")!.innerHTML =
          '<div class="knowledge-empty">Erro ao carregar arquivos do vault.</div>';
      });
  }

  private renderKnowledgeItems(items: KnowledgeItem[], agentId: string, container: HTMLElement): void {
    const listEl = container.querySelector<HTMLElement>("#knowledge-list")!;
    if (items.length === 0) {
      listEl.innerHTML = '<div class="knowledge-empty">Nenhum arquivo encontrado. Adicione conhecimento nas abas acima.</div>';
      return;
    }
    listEl.innerHTML = "";
    for (const item of items) {
      const card = document.createElement("div");
      card.className = "knowledge-card";
      card.innerHTML = `
        <div class="knowledge-card-header">
          <span class="knowledge-title">${this.esc(item.title)}</span>
          <button class="knowledge-delete-btn" title="Excluir">🗑️</button>
        </div>
        <div class="knowledge-path">${this.esc(item.path)}</div>
        <div class="knowledge-preview">${this.esc(item.preview)}</div>
      `;
      card.querySelector(".knowledge-delete-btn")!.addEventListener("click", async () => {
        if (!confirm(`Excluir "${item.title}" do vault?`)) return;
        try {
          await fetch("/api/vault/knowledge", {
            method: "DELETE",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ path: item.path, agent_id: agentId }),
          });
          card.remove();
          this.showToast("🗑️ Arquivo excluído do vault");
        } catch {
          this.showToast("❌ Erro ao excluir arquivo");
        }
      });
      listEl.appendChild(card);
    }
  }

  // ── Utilities ───────────────────────────────────────────────────────────────

  private makeField(label: string, type: string, id: string, defaultVal: string, rows = 4): HTMLElement {
    const g = document.createElement("div");
    g.className = "form-group";
    if (type === "textarea") {
      g.innerHTML = `<label>${label}</label><textarea id="${id}" class="form-textarea" rows="${rows}"></textarea>`;
      (g.querySelector("textarea") as HTMLTextAreaElement).value = defaultVal;
    } else {
      g.innerHTML = `<label>${label}</label><input type="${type}" id="${id}" class="form-input" />`;
      (g.querySelector("input") as HTMLInputElement).value = defaultVal;
    }
    return g;
  }

  private makeToggle(label: string, id: string): HTMLElement {
    const g = document.createElement("div");
    g.className = "form-group form-toggle";
    g.innerHTML = `<label><input type="checkbox" id="${id}" /> ${label}</label>`;
    return g;
  }

  private previewImage(file: File, thumb: HTMLImageElement, preview: HTMLElement, dropZone: HTMLElement): void {
    const reader = new FileReader();
    reader.onload = (e) => {
      thumb.src              = e.target!.result as string;
      preview.style.display  = "block";
      dropZone.style.display = "none";
    };
    reader.readAsDataURL(file);
  }

  private async fileToBase64(file: File): Promise<{ b64: string; filename: string }> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload  = (e) => resolve({ b64: (e.target!.result as string).split(",")[1], filename: file.name });
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  private showToast(msg: string): void {
    const container = document.getElementById("agent-toasts")!;
    const toast     = document.createElement("div");
    toast.className = "agent-toast toast-info";
    toast.textContent = msg;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
  }

  private esc(s: string): string {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add src/ui/AgentsPanel.ts
git commit -m "feat: add AgentsPanel UI component with 3-view navigation and training panel"
```

---

## Task 5: Wire up AgentsPanel in main.ts

**Files:**
- Modify: `src/main.ts`

- [ ] **Step 1: Import and instantiate AgentsPanel**

Add import at the top of `src/main.ts` alongside the other UI imports:
```typescript
import { AgentsPanel } from "./ui/AgentsPanel";
```

Add instantiation right after `const tasksPanel = new TasksPanel();`:
```typescript
  new AgentsPanel();
```

The final bootstrap function beginning should look like:
```typescript
async function bootstrap() {
  const identity = await NicknameModal.getOrPrompt();
  const toast = new AgentToast();
  const tasksPanel = new TasksPanel();
  new AgentsPanel();
  connectEventStream(toast, tasksPanel);
  // ... rest unchanged
```

- [ ] **Step 2: Commit**

```bash
git add src/main.ts
git commit -m "feat: wire up AgentsPanel in bootstrap"
```

---

## Verification

After all tasks, start the servers and verify manually:

```bash
# Terminal 1 — backend
python -m uvicorn server.api:app --port 8000 --reload

# Terminal 2 — frontend
npm run dev
```

Open `http://localhost:5173` and check:

1. **FAB** — "👥 Agentes" button visible bottom-right
2. **Agent List** — clicking FAB opens right drawer with 4 agent cards
3. **Profile** — clicking an agent shows role, editable Goal/Backstory; blur saves to Supabase
4. **Training opens** — "Treinar" button enters training view with 3 tabs
5. **Quick-Add** — each of 6 category cards expands a form; submit creates `.md` in vault and shows "✅ Salvo e indexado!"
6. **Novo Doc** — form with image drop zone; submit works end-to-end
7. **Conhecimento** — lists vault files with `agent: <id>` frontmatter; delete removes file and shows toast; Re-indexar returns chunk count
8. **Vault files** — open `C:\Users\v27me\OneDrive\Desktop\Ideaverse` in Obsidian and confirm new `.md` files appear with correct frontmatter
