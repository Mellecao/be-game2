# Agent Training Panel — Design Spec

**Date:** 2026-05-05
**Branch:** PlannerAgent
**Status:** Approved

---

## Overview

Add a floating "Agentes" button to the BE-Game UI that opens a right-side drawer panel. The panel provides three stacked views: agent list, agent profile (with editable CrewAI definitions), and a training panel for feeding Obsidian vault knowledge to each agent. All knowledge changes write `.md` files directly to the vault and re-index into Qdrant.

---

## Architecture

```
Frontend (TypeScript)          Backend (FastAPI)              Vault (Obsidian)
─────────────────────          ─────────────────              ────────────────
src/ui/AgentsPanel.ts          GET  /api/agents               Atlas/Notes/Agentes/[Name]/*.md
                               GET  /api/vault/knowledge/{id} Calendar/*.md
                               POST /api/vault/knowledge      Efforts/On|Ongoing|Simmering/*.md
                               DELETE /api/vault/knowledge    Atlas/Utilities/Images/*.png|jpg
                               POST /api/vault/image
                               POST /api/vault/reindex/{id}
```

**Agent ownership in vault:** frontmatter field `agent: {agent_id}` (e.g. `agent: copywriter`) on every file created via the training panel. Used to filter knowledge per agent.

**Re-indexing strategy:** incremental — index only the affected file on create/update; delete chunks by `source` path on delete; full agent re-index available via button.

---

## Frontend

### File
`src/ui/AgentsPanel.ts` — single file, follows the same class pattern as `TasksPanel.ts`.

### FAB Button
- Position: bottom-right, 16px above the ChatPanel FAB
- Label: "Agentes" + people icon
- Toggles the panel open/closed

### Panel
- Right-side drawer, 420px wide
- Slides in from right (CSS transform, same pattern as TasksPanel)
- Z-index above game canvas, below ChatPanel

### View 1 — Agent List
- Header: "Agentes" + close (×) button
- Grid of agent cards: sprite avatar thumbnail | display_name | role
- Click → View 2

### View 2 — Agent Profile
- Header: ← back + agent display_name
- Avatar + name + role
- Section "Definições CrewAI":
  - **Role** — read-only label
  - **Goal** — inline editable textarea → `PUT /api/agents/{id}` on blur
  - **Backstory** — inline editable textarea → `PUT /api/agents/{id}` on blur
- Button **"Treinar"** (full-width, highlighted) → View 3

### View 3 — Training Panel
- Header: ← back + "Treinar: {display_name}"
- Three tabs: **Quick-Add ACE** | **Novo Documento** | **Conhecimento Atual**

#### Tab: Quick-Add ACE
Three clickable cards (Atlas, Calendar, Efforts). Clicking a card expands an inline form:

| Card | Fields | Destination path |
|------|--------|-----------------|
| Atlas | título, conteúdo (markdown), tags | `Atlas/Notes/Agentes/[Name]/[título].md` |
| Calendar | data (default hoje), título, conteúdo | `Calendar/[YYYY-MM-DD]-[título].md` |
| Efforts | título, status (On/Ongoing/Simmering), rank (1–10), conteúdo | `Efforts/[status]/[título] (E).md` or `(OE).md` |

Submit → `POST /api/vault/knowledge` → file created → re-indexed → success toast.

#### Tab: Novo Documento
- Título (text input)
- Pasta destino (dropdown): Atlas/Notes/Agentes, Calendar, Efforts/On, Efforts/Ongoing, Efforts/Simmering
- Tags (chip input, comma-separated)
- Conteúdo (textarea, markdown)
- Upload de imagem: drag-and-drop zone + file picker button
  - Accepts: png, jpg, gif, webp
  - Shows thumbnail preview after selection
  - On submit: image POSTed to `/api/vault/image`, markdown link `![[filename]]` appended to conteúdo
- Button "Salvar e Indexar" → `POST /api/vault/knowledge`

#### Tab: Conhecimento Atual
- Search input (client-side filter on titles)
- Fetches `GET /api/vault/knowledge/{agent_id}` on tab open
- List of file cards:
  - File name (bold)
  - Relative vault path (muted)
  - Preview: first 200 chars of content
  - 🗑️ delete button → `DELETE /api/vault/knowledge` → removes file + Qdrant chunks → refreshes list
- Button "Re-indexar tudo" → `POST /api/vault/reindex/{agent_id}` → shows indexed count in toast

---

## Backend

### New endpoints in `server/api.py`

#### `GET /api/vault/knowledge/{agent_id}`
Scans vault for `.md` files with `agent: {agent_id}` in frontmatter.
```json
[{ "path": "Atlas/Notes/Agentes/Copywriter/Tom e Voz.md",
   "title": "Tom e Voz",
   "preview": "Primeiras 200 chars...",
   "tags": ["agente", "copywriter"],
   "created": "2026-05-05" }]
```

#### `POST /api/vault/knowledge`
```json
{
  "agent_id": "copywriter",
  "title": "Tom e Voz Atualizado",
  "content": "Conteúdo markdown...",
  "ace_type": "atlas",
  "ace_subtype": "notes",
  "tags": ["copywriter", "tom-e-voz"],
  "rank": null,
  "effort_status": null,
  "date": null,
  "image_base64": null,
  "image_filename": null
}
```
- Builds frontmatter with `agent`, `up`, `tags`, `created`
- Saves image to `Atlas/Utilities/Images/` if provided
- Writes `.md` file
- Calls `index_single_file(path)` on indexer
- Returns `{ "path": "...", "indexed": true }`

#### `DELETE /api/vault/knowledge`
```json
{ "path": "Atlas/Notes/Agentes/Copywriter/Tom e Voz.md", "agent_id": "copywriter" }
```
- Deletes file from vault
- Deletes Qdrant points where `source == path`
- Returns `{ "deleted": true }`

#### `POST /api/vault/image`
- Multipart upload (field: `file`)
- Saves to `{VAULT_PATH}/Atlas/Utilities/Images/{filename}`
- Returns `{ "vault_path": "Atlas/Utilities/Images/img.png", "markdown_link": "![[img.png]]" }`

#### `POST /api/vault/reindex/{agent_id}`
- Finds all vault files with `agent: {agent_id}`
- Re-indexes each via indexer
- Returns `{ "indexed_count": 6 }`

### Changes to `server/obsidian_indexer.py`
- Add `index_single_file(file_path: str)` — indexes one file, upserts its chunks into Qdrant
- Add `delete_file_chunks(file_path: str)` — deletes Qdrant points by `source` payload field
- Add `get_agent_files(agent_id: str) -> list[dict]` — scans vault for files with `agent:` frontmatter field

---

## Vault File Template

```markdown
---
up:
  - "[[Black Elephant MOC]]"
agent: copywriter
tags: [agente, copywriter]
created: 2026-05-05
---

# Título

Conteúdo...

![[imagem.png]]
```

**Effort variant:**
```markdown
---
up:
  - "[[Efforts]]"
agent: copywriter
tags: [effort, copywriter]
rank: 7
created: 2026-05-05
---
```

---

## Path Conventions

| ACE Type | Subtype | Path Pattern |
|----------|---------|-------------|
| Atlas | notes | `Atlas/Notes/Agentes/[AgentName]/[título].md` |
| Calendar | daily | `Calendar/[YYYY-MM-DD]-[título].md` |
| Efforts | On | `Efforts/On/[título] (E).md` |
| Efforts | Ongoing | `Efforts/Ongoing/[título] (OE).md` |
| Efforts | Simmering | `Efforts/Simmering/[título] (E).md` |
| Novo Documento | (user choice) | `[chosen_folder]/[título].md` |
| Images | — | `Atlas/Utilities/Images/[filename]` |

---

## Error Handling

- Vault path not found → 500 with clear message
- Qdrant unavailable → file still saved, response includes `"indexed": false`
- Duplicate file name → append timestamp suffix
- Image too large (>10MB) → 400 validation error
- Agent not found → 404

---

## Out of Scope

- Editing existing vault files (only create + delete in v1)
- Full-text search across vault (Qdrant semantic search already handles this via chat)
- Bulk import
- Markdown preview renderer in the panel
