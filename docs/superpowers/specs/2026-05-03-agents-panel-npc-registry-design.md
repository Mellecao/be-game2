# Agents Panel + NPC Registry Design

**Date:** 2026-05-03
**Scope:** Subsystem A (visual/UI) + Subsystem B (new NPCs) — Trello/CrewAI orchestration is a separate spec.

---

## Goal

Replace hardcoded NPC spawning with a Supabase-backed agent registry. Add an "Agentes" mode that lets the user drag NPCs around the room and configure their CrewAI parameters (role, goal, backstory) via a click-to-edit modal. Add vendedor, programador, and planner as new agents. Fix the corridor entrance with a doorframe and extend it 1 tile outward; spawn the player there.

---

## 1. Data Model

**Supabase table: `agents`**

| column | type | notes |
|---|---|---|
| `id` | `text` PK | slug: `"copywriter"`, `"vendedor"`, etc. |
| `display_name` | `text` | shown in game above NPC |
| `role` | `text` | CrewAI Agent role |
| `goal` | `text` | CrewAI Agent goal |
| `backstory` | `text` | CrewAI Agent backstory |
| `col` | `float` | isometric column position |
| `row` | `float` | isometric row position |
| `sprite_char` | `int` | avatar sprite number (1–5) |

**Seed data** (inserted on first `GET /api/agents` if table is empty):

| id | display_name | col | row | sprite_char |
|---|---|---|---|---|
| copywriter | Copywriter | 7 | 3 | 3 |
| vendedor | Vendedor | 3 | 3 | 2 |
| programador | Programador | 5 | 6 | 2 |
| planner | Planner | 8 | 6 | 2 |

Role/goal/backstory seeded with sensible defaults per agent (PT-BR).

---

## 2. Backend API

**File:** `server/api.py`

### `GET /api/agents`
- Calls `_ensure_agents_seed(db)` — inserts seed rows if table is empty
- Returns all rows from `agents` table

### `PUT /api/agents/{agent_id}`
- Accepts `AgentUpdate` Pydantic model with all fields optional
- Uses `model_dump(exclude_unset=True)` to only update provided fields
- Returns `{"ok": True}`

No DELETE — agents are never removed via UI in this spec.

---

## 3. Frontend Components

### `src/game/AgentEditor.ts` *(new)*
Mirrors `FurnitureEditor`. Responsibilities:
- `register(npc: NPC)` — attach pointer events to NPC
- `setActive(bool)` — toggle drag mode; sets NPC `eventMode`
- On drag end: `PUT /api/agents/{id}` with new `{col, row}`
- On click (no drag): fires `onSelect(npc)` callback → opens modal
- Ghost tile feedback during drag (same green diamond as FurnitureEditor)

### `src/ui/AgentPanel.ts` *(new)*
Mirrors `BuildingPanel`. Single "🧑‍💼 Agentes" floating button. Toggle calls `game.setAgentMode(active)`.

### `src/ui/AgentConfigModal.ts` *(new)*
HTML modal overlay. Opens when user clicks an NPC in agent mode.
- Fields: Display Name, Role, Goal (textarea), Backstory (textarea)
- "Salvar" → `PUT /api/agents/{id}` → updates NPC display name in scene → closes
- "Fechar" → discards changes
- Styled dark overlay consistent with existing UI

### Changes to existing files

**`src/game/NPC.ts`**
- Store `agentId: string`, `role`, `goal`, `backstory` on instance
- `NPC.fromAgentData(data)` static factory replaces `NPC.create()`
- Sprite char driven by `data.sprite_char` (loads `/avatar/front_{n}_iddle.png`)

**`src/game/Game.ts`**
- `init()` fetches `GET /api/agents`, calls `NPC.fromAgentData()` for each
- Adds `AgentEditor` field; `setAgentMode(active: boolean)`
- Removes hardcoded `copywriter` NPC spawn

**`src/main.ts`**
- Instantiates `AgentPanel` and `AgentConfigModal`
- Wires `AgentPanel` toggle → `game.setAgentMode()`
- Wires `AgentEditor.onSelect` → `AgentConfigModal.open(npc)`

---

## 4. Visual: Doorframe + Corridor Extension

**File:** `src/game/Room.ts`

### Doorframe
Above the wall gap (rows 4–5), draw a horizontal bridge panel connecting the two left-wall segments. This panel is at wall top height and is `~40px` tall — the same `WALL_BACK` / `WALL_TOP` / `WALL_TRIM` palette. It creates the visual of an architrave over the entrance.

### Corridor extension (1 tile outward)
Currently `drawCorridor()` draws 1 dark tile at `(-1, 4)`. Extend to cover both rows of the opening and 1 tile outward:
- Dark tiles at `(-1, 4)` and `(-1, 5)` — fills the full 2-row opening
- Additional tile at `(-2, 4)` and `(-2, 5)` — the "outside" visible extension

The outside tiles use a slightly different dark tone (`0x111118`) to suggest depth beyond the room.

### Player spawn point
Change `Player.worldCol / worldRow` initial values from `(5, 5)` to `(-1, 4.5)` — center of the corridor entrance. Player "enters" the room from the doorframe.

---

## 5. Data Flow Summary

```
App start
  → GET /api/agents
  → NPC.fromAgentData() × N
  → AgentEditor.register() × N
  → NPCs visible in scene

User clicks "Agentes"
  → AgentMode active
  → NPCs become draggable

User drags NPC
  → PUT /api/agents/{id} {col, row}

User clicks NPC (no drag)
  → AgentConfigModal.open(npc)
  → User edits fields
  → PUT /api/agents/{id} {display_name, role, goal, backstory}
  → NPC display name updates in scene
```

---

## 6. Out of Scope (this spec)

- NPC walking animations (NPCs remain static idle sprites)
- Creating or deleting agents via UI
- CrewAI agent execution (Subsystem C)
- Trello integration (Subsystem C)
