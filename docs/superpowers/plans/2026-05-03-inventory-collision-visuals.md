# Inventory, Collision & Visuals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add furniture inventory panel, tile-based collision, procedural floor with extrusion, corridor entrance, +15% wall height, +25% character scale.

**Architecture:** New `CollisionMap` class manages blocked tiles; `FurnitureEditor` writes to it on move/remove; `Player` reads from it before moving. `InventoryPanel` is an HTML overlay that counts active furniture and spawns new items via a `Game.spawnFurniture()` callback. Visual changes are isolated to `Room.ts`, `iso.ts`, `Player.ts`, and `NPC.ts`.

**Tech Stack:** TypeScript, PixiJS 8, FastAPI, Supabase (postgrest-js)

---

## Task 1: Wall height +15% and character scale +25%

**Files:**
- Modify: `src/game/iso.ts`
- Modify: `src/game/Player.ts`
- Modify: `src/game/NPC.ts`

- [ ] **Step 1: Update WALL_HEIGHT in iso.ts**

In `src/game/iso.ts`, change line 5:
```typescript
export const WALL_HEIGHT = 127;
```

- [ ] **Step 2: Update Player sprite scale**

In `src/game/Player.ts`, change the two scale references:

Line 38 (in `load()`):
```typescript
p.sprite.scale.set(2.0);
```

Line 110 (in `updateSprite()`):
```typescript
this.sprite.scale.x = 2.0 * flip;
```

Line 33 (shadow scale):
```typescript
p.shadow.scale.set(1.1, 0.75);
```

- [ ] **Step 3: Update NPC sprite scale**

In `src/game/NPC.ts`, change:

Line 37 (shadow scale):
```typescript
shadow.scale.set(1.1, 0.75);
```

Line 42 (sprite scale):
```typescript
sprite.scale.set(2.0);
```

- [ ] **Step 4: Verify visually**

Run `npm run dev`, open browser. Confirm characters are visibly larger and walls are slightly taller. No console errors.

- [ ] **Step 5: Commit**
```
git add src/game/iso.ts src/game/Player.ts src/game/NPC.ts
git commit -m "feat: wall height +15%, character scale +25%"
```

---

## Task 2: Procedural floor + corridor entrance

**Files:**
- Modify: `src/game/Room.ts`

- [ ] **Step 1: Replace Room.ts with new implementation**

Full replacement of `src/game/Room.ts`:

```typescript
import { Container, Graphics } from "pixi.js";
import {
  ISO_TILE_H,
  ISO_TILE_W,
  ROOM_COLS,
  ROOM_ROWS,
  WALL_HEIGHT,
  isoToScreen,
} from "./iso";

const WALL_BACK = 0xdcd1a8;
const WALL_TOP  = 0xefe6c0;
const WALL_TRIM = 0x6e5832;

const FLOOR_TOP   = 0xb0a898;
const FLOOR_LEFT  = 0x8a8078;
const FLOOR_RIGHT = 0x787068;
const FLOOR_GRID  = 0x787068;
const FLOOR_EXT   = 4;

export class Room extends Container {
  static async load(): Promise<Room> {
    const r = new Room();
    r.drawCorridor();
    r.drawFloor();
    r.drawWalls();
    return r;
  }

  private drawFloor() {
    const halfW = ISO_TILE_W / 2;
    const halfH = ISO_TILE_H / 2;
    const g = new Graphics();

    for (let row = 0; row < ROOM_ROWS; row++) {
      for (let col = 0; col < ROOM_COLS; col++) {
        const c = isoToScreen(col, row);
        const top   = { x: c.x,         y: c.y - halfH };
        const right = { x: c.x + halfW,  y: c.y };
        const bot   = { x: c.x,         y: c.y + halfH };
        const left  = { x: c.x - halfW,  y: c.y };

        // Left extrusion face
        g.poly([
          left.x,  left.y,
          bot.x,   bot.y,
          bot.x,   bot.y  + FLOOR_EXT,
          left.x,  left.y + FLOOR_EXT,
        ]).fill(FLOOR_LEFT);

        // Right extrusion face
        g.poly([
          bot.x,   bot.y,
          right.x, right.y,
          right.x, right.y + FLOOR_EXT,
          bot.x,   bot.y   + FLOOR_EXT,
        ]).fill(FLOOR_RIGHT);

        // Top face
        g.poly([top.x, top.y, right.x, right.y, bot.x, bot.y, left.x, left.y])
          .fill(FLOOR_TOP);
      }
    }

    // Grid lines drawn on top of faces
    for (let row = 0; row < ROOM_ROWS; row++) {
      for (let col = 0; col < ROOM_COLS; col++) {
        const c = isoToScreen(col, row);
        g.poly([
          c.x,           c.y - halfH,
          c.x + halfW,   c.y,
          c.x,           c.y + halfH,
          c.x - halfW,   c.y,
        ]).stroke({ color: FLOOR_GRID, width: 1, alpha: 0.35 });
      }
    }

    this.addChild(g);
  }

  private drawWalls() {
    const wallH = WALL_HEIGHT;

    // BACK-LEFT wall — two segments leaving gap at row 4..5 for corridor
    const drawLeftSeg = (fromRow: number, toRow: number) => {
      const a = isoToScreen(0, fromRow);
      const b = isoToScreen(0, toRow);
      const w = new Graphics();
      w.poly([a.x, a.y - wallH, b.x, b.y - wallH, b.x, b.y, a.x, a.y]).fill(WALL_BACK);
      w.poly([a.x, a.y - wallH, b.x, b.y - wallH, b.x - 4, b.y - wallH + 4, a.x - 4, a.y - wallH + 4]).fill(WALL_TOP);
      w.poly([a.x, a.y - 6,     b.x, b.y - 6,     b.x, b.y, a.x, a.y]).fill(WALL_TRIM);
      this.addChild(w);
    };

    drawLeftSeg(0, 4);
    drawLeftSeg(5, ROOM_ROWS);

    // BACK-RIGHT wall (full, no gap)
    {
      const a = isoToScreen(0, 0);
      const b = isoToScreen(ROOM_COLS, 0);
      const w = new Graphics();
      w.poly([a.x, a.y - wallH, b.x, b.y - wallH, b.x, b.y, a.x, a.y]).fill(WALL_BACK);
      w.poly([a.x, a.y - wallH, b.x, b.y - wallH, b.x + 4, b.y - wallH + 4, a.x + 4, a.y - wallH + 4]).fill(WALL_TOP);
      w.poly([a.x, a.y - 6,     b.x, b.y - 6,     b.x, b.y, a.x, a.y]).fill(WALL_TRIM);
      this.addChild(w);
    }
  }

  private drawCorridor() {
    const halfW = ISO_TILE_W / 2;
    const halfH = ISO_TILE_H / 2;
    const c = isoToScreen(-1, 4);
    const g = new Graphics();
    g.poly([
      c.x,        c.y - halfH,
      c.x + halfW, c.y,
      c.x,        c.y + halfH,
      c.x - halfW, c.y,
    ]).fill(0x1a1a22);
    this.addChild(g);
  }
}
```

- [ ] **Step 2: Verify visually**

Reload browser. Confirm:
- Floor is grey/concrete with visible grid and slight 3D edge
- Door rectangle is gone
- A dark tile appears at the left wall opening (rows 4-5)

- [ ] **Step 3: Commit**
```
git add src/game/Room.ts
git commit -m "feat: procedural floor with extrusion, corridor entrance replaces door"
```

---

## Task 3: CollisionMap

**Files:**
- Create: `src/game/CollisionMap.ts`

- [ ] **Step 1: Create CollisionMap.ts**

```typescript
import { ROOM_COLS, ROOM_ROWS } from "./iso";

export class CollisionMap {
  private grid: boolean[][];

  constructor() {
    this.grid = Array.from({ length: ROOM_ROWS }, () =>
      new Array(ROOM_COLS).fill(false)
    );
  }

  block(col: number, row: number): void {
    if (this.inBounds(col, row)) this.grid[row][col] = true;
  }

  unblock(col: number, row: number): void {
    if (this.inBounds(col, row)) this.grid[row][col] = false;
  }

  isBlocked(col: number, row: number): boolean {
    if (!this.inBounds(col, row)) return true;
    return this.grid[row][col];
  }

  private inBounds(col: number, row: number): boolean {
    return col >= 0 && col < ROOM_COLS && row >= 0 && row < ROOM_ROWS;
  }
}
```

- [ ] **Step 2: Commit**
```
git add src/game/CollisionMap.ts
git commit -m "feat: add CollisionMap for tile-based furniture collision"
```

---

## Task 4: FurnitureEditor — CollisionMap integration

**Files:**
- Modify: `src/game/FurnitureEditor.ts`

- [ ] **Step 1: Add CollisionMap import and constructor param**

Add import at top of `src/game/FurnitureEditor.ts`:
```typescript
import { CollisionMap } from "./CollisionMap";
```

Change constructor signature (line 33):
```typescript
constructor(app: Application, world: Container, private collision: CollisionMap) {
```

- [ ] **Step 2: Block initial position in register()**

In `register()`, add after `this.items.push(item)` (line 50):
```typescript
this.collision.block(item.worldCol, item.worldRow);
```

Also, inside the `pointerdown` handler for removal (line 57-61):
```typescript
if (this.removeWallsMode && this.wallItems.has(item)) {
  item.visible = false;
  this.removedItems.add(item);
  this.collision.unblock(item.worldCol, item.worldRow);
  return;
}
```

- [ ] **Step 3: Unblock/block on drag-drop in onGlobalUp()**

Replace `onGlobalUp` (lines 135-141):
```typescript
private onGlobalUp(e: FederatedPointerEvent) {
  if (!this.active || !this.dragActive || !this.selected) return;
  const { col, row } = this.tileAt(e.globalX, e.globalY);
  this.collision.unblock(this.selected.worldCol, this.selected.worldRow);
  this.selected.moveTo(col, row);
  this.collision.block(col, row);
  this.dragActive = false;
  this.ghost.visible = false;
}
```

- [ ] **Step 4: Commit**
```
git add src/game/FurnitureEditor.ts
git commit -m "feat: FurnitureEditor writes to CollisionMap on move and remove"
```

---

## Task 5: Player — collision check

**Files:**
- Modify: `src/game/Player.ts`

- [ ] **Step 1: Add collisionMap property**

Add import at top of `src/game/Player.ts`:
```typescript
import { CollisionMap } from "./CollisionMap";
```

Add public property to the class (after `private keys` line):
```typescript
collisionMap: CollisionMap | null = null;
```

- [ ] **Step 2: Check collision before applying movement**

Replace lines 76-78 in `update()`:
```typescript
// was:
// const next = clampToRoom(this.worldCol + dCol, this.worldRow + dRow);
// this.worldCol = next.col;
// this.worldRow = next.row;

// replace with:
const next = clampToRoom(this.worldCol + dCol, this.worldRow + dRow);
const tileCol = Math.round(next.col);
const tileRow = Math.round(next.row);
if (!this.collisionMap || !this.collisionMap.isBlocked(tileCol, tileRow)) {
  this.worldCol = next.col;
  this.worldRow = next.row;
}
```

- [ ] **Step 3: Commit**
```
git add src/game/Player.ts
git commit -m "feat: Player checks CollisionMap before moving"
```

---

## Task 6: Game.ts — wire CollisionMap, add table, add spawnFurniture

**Files:**
- Modify: `src/game/Game.ts`
- Modify: `src/game/constants.ts`

- [ ] **Step 1: Add nitroTable to constants.ts ASSETS (already present — verify)**

Open `src/game/constants.ts`. Confirm line:
```typescript
nitroTable: "/table1/cubie_table.nitro",
```
is present. If not, add it inside the `ASSETS` object.

- [ ] **Step 2: Add imports and CollisionMap to Game.ts**

Add import at top of `src/game/Game.ts`:
```typescript
import { CollisionMap } from "./CollisionMap";
```

Add field to the `Game` class:
```typescript
collision!: CollisionMap;
```

- [ ] **Step 3: Add table to FURNITURE_CONFIG in Game.ts**

After the `desk` entry in `FURNITURE_CONFIG` (before the closing `]`):
```typescript
  {
    id: "table",
    url: ASSETS.nitroTable,
    defaultCol: 5,
    defaultRow: 4,
    defaultDir: 2,
    validDirs: [0, 2, 4, 6],
  },
```

- [ ] **Step 4: Instantiate CollisionMap and pass to FurnitureEditor**

In `Game.init()`, before the `this.editor = new FurnitureEditor(...)` line:
```typescript
this.collision = new CollisionMap();
```

Change the FurnitureEditor instantiation line:
```typescript
this.editor = new FurnitureEditor(this.app, this.world, this.collision);
```

- [ ] **Step 5: Set collisionMap on Player after load**

In `Game.init()`, after `this.player = await Player.load()`:
```typescript
this.player.collisionMap = this.collision;
```

- [ ] **Step 6: Add getFurnitureList and spawnFurniture methods**

Add these two methods to the `Game` class (after `setRemoveWalls`):

```typescript
getFurnitureList(): NitroFurniture[] {
  return this.furniture;
}

async spawnFurniture(baseId: string): Promise<void> {
  const cfg = FURNITURE_CONFIG.find((c) => c.id === baseId);
  if (!cfg) return;

  const active = this.furniture.filter(
    (f) => (f.id === baseId || f.id.startsWith(baseId + "_")) && f.visible
  );
  if (active.length >= 4) return;

  const idx = active.length + 1;
  const newId = idx === 1 ? baseId : `${baseId}_${idx}`;
  const col = Math.floor(ROOM_COLS / 2);
  const row = Math.floor(ROOM_ROWS / 2);

  const item = await NitroFurniture.load(cfg.url, {
    col,
    row,
    direction: cfg.defaultDir,
    includeShadow: cfg.includeShadow,
    yOffset: cfg.yOffset,
  });
  item.id = newId;
  item.validDirections = cfg.validDirs;
  this.world.addChild(item);
  this.furniture.push(item);
  this.editor.register(item);
  this.sortDepth();
}
```

- [ ] **Step 7: Verify — run dev server, walk into furniture**

Run `npm run dev`. Enter building mode, move furniture, then exit building mode and walk toward a piece of furniture. The player should stop at the furniture tile. Table should appear in FURNITURE_CONFIG (verifiable by opening DevTools and checking no load errors).

- [ ] **Step 8: Commit**
```
git add src/game/Game.ts src/game/constants.ts
git commit -m "feat: Game wires CollisionMap, adds table to config, exposes spawnFurniture"
```

---

## Task 7: Inventory API endpoints

**Files:**
- Modify: `server/api.py`

- [ ] **Step 1: Add InventoryItem model and endpoints**

Add after the `FurnitureItem` model and before `@app.get("/api/furniture")` in `server/api.py`:

```python
class InventoryAction(BaseModel):
    item_id: str
    owner_id: str | None = None

INVENTORY_DEFAULTS = ["sofa", "chair", "desk", "table", "window"]

def _ensure_seed(db):
    result = db.table("inventory_items").select("id").limit(1).execute()
    if not result.data:
        db.table("inventory_items").insert([
            {"item_id": item_id, "quantity": 1, "owner_id": None}
            for item_id in INVENTORY_DEFAULTS
        ]).execute()


@app.get("/api/inventory")
def get_inventory():
    db = get_supabase()
    _ensure_seed(db)
    result = db.table("inventory_items").select("item_id,quantity").is_("owner_id", "null").execute()
    return result.data


@app.post("/api/inventory/add")
def add_inventory(action: InventoryAction):
    db = get_supabase()
    existing = (
        db.table("inventory_items")
        .select("id,quantity")
        .eq("item_id", action.item_id)
        .is_("owner_id", "null")
        .execute()
    )
    if existing.data:
        current = existing.data[0]["quantity"]
        if current >= 4:
            raise HTTPException(status_code=400, detail="Limite de 4 atingido")
        db.table("inventory_items").update({"quantity": current + 1}).eq("id", existing.data[0]["id"]).execute()
    else:
        db.table("inventory_items").insert({"item_id": action.item_id, "quantity": 1, "owner_id": None}).execute()
    return {"ok": True}


@app.post("/api/inventory/remove")
def remove_inventory(action: InventoryAction):
    db = get_supabase()
    existing = (
        db.table("inventory_items")
        .select("id,quantity")
        .eq("item_id", action.item_id)
        .is_("owner_id", "null")
        .execute()
    )
    if not existing.data or existing.data[0]["quantity"] <= 0:
        raise HTTPException(status_code=400, detail="Sem estoque")
    current = existing.data[0]["quantity"]
    db.table("inventory_items").update({"quantity": current - 1}).eq("id", existing.data[0]["id"]).execute()
    return {"ok": True}
```

- [ ] **Step 2: Verify endpoint**

With uvicorn running, open browser at `http://localhost:8000/api/inventory`. Should return JSON array of items with quantities (seeded automatically on first call).

- [ ] **Step 3: Commit**
```
git add server/api.py
git commit -m "feat: inventory API endpoints with auto-seed"
```

---

## Task 8: InventoryPanel UI

**Files:**
- Create: `src/ui/InventoryPanel.ts`

- [ ] **Step 1: Create InventoryPanel.ts**

```typescript
import { NitroFurniture } from "../game/NitroFurniture";

const MAX_PER_ITEM = 4;

const ITEMS = [
  { id: "sofa",   label: "Sofá" },
  { id: "chair",  label: "Cadeira" },
  { id: "desk",   label: "Mesa Gamer" },
  { id: "table",  label: "Mesa" },
  { id: "window", label: "Janela" },
];

export class InventoryPanel {
  private wrap: HTMLElement;
  private cards = new Map<string, { counter: HTMLElement; btn: HTMLButtonElement }>();

  constructor(
    private getFurniture: () => NitroFurniture[],
    private onSpawn: (itemId: string) => void
  ) {
    this.injectStyles();
    this.wrap = document.createElement("div");
    this.wrap.id = "inventory-panel";

    const title = document.createElement("div");
    title.className = "inv-title";
    title.textContent = "Inventário";
    this.wrap.appendChild(title);

    for (const item of ITEMS) {
      const card = document.createElement("div");
      card.className = "inv-card";

      const label = document.createElement("span");
      label.className = "inv-label";
      label.textContent = item.label;

      const counter = document.createElement("span");
      counter.className = "inv-count";
      counter.textContent = `0/${MAX_PER_ITEM}`;

      const btn = document.createElement("button");
      btn.className = "inv-btn";
      btn.textContent = "+";
      btn.addEventListener("click", () => {
        this.onSpawn(item.id);
        setTimeout(() => this.refresh(), 300);
      });

      card.appendChild(label);
      card.appendChild(counter);
      card.appendChild(btn);
      this.wrap.appendChild(card);
      this.cards.set(item.id, { counter, btn });
    }

    document.body.appendChild(this.wrap);
    this.hide();
  }

  show() {
    this.wrap.classList.remove("inv-hidden");
    this.refresh();
  }

  hide() {
    this.wrap.classList.add("inv-hidden");
  }

  refresh() {
    const list = this.getFurniture();
    for (const item of ITEMS) {
      const count = list.filter(
        (f) => (f.id === item.id || f.id.startsWith(item.id + "_")) && f.visible
      ).length;
      const refs = this.cards.get(item.id)!;
      refs.counter.textContent = `${count}/${MAX_PER_ITEM}`;
      refs.btn.disabled = count >= MAX_PER_ITEM;
    }
  }

  private injectStyles() {
    if (document.getElementById("inv-styles")) return;
    const style = document.createElement("style");
    style.id = "inv-styles";
    style.textContent = `
      #inventory-panel {
        position: fixed;
        top: 50%;
        right: 16px;
        transform: translateY(-50%);
        background: rgba(20,20,30,0.92);
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 8px;
        padding: 12px 10px;
        display: flex;
        flex-direction: column;
        gap: 8px;
        min-width: 160px;
        z-index: 100;
        font-family: "Segoe UI", sans-serif;
        color: #fff;
      }
      #inventory-panel.inv-hidden { display: none; }
      .inv-title {
        font-size: 13px;
        font-weight: bold;
        text-align: center;
        margin-bottom: 4px;
        color: #ffd700;
      }
      .inv-card {
        display: flex;
        align-items: center;
        gap: 8px;
        background: rgba(255,255,255,0.05);
        border-radius: 4px;
        padding: 6px 8px;
      }
      .inv-label { flex: 1; font-size: 12px; }
      .inv-count { font-size: 11px; color: #aaa; min-width: 28px; text-align: right; }
      .inv-btn {
        background: #3a8a3a;
        border: none;
        border-radius: 4px;
        color: #fff;
        font-size: 16px;
        width: 24px;
        height: 24px;
        cursor: pointer;
        line-height: 1;
        padding: 0;
      }
      .inv-btn:disabled { background: #555; cursor: not-allowed; }
      .inv-btn:not(:disabled):hover { background: #4caf50; }
    `;
    document.head.appendChild(style);
  }
}
```

- [ ] **Step 2: Commit**
```
git add src/ui/InventoryPanel.ts
git commit -m "feat: InventoryPanel HTML overlay for furniture placement"
```

---

## Task 9: Wire InventoryPanel in main.ts

**Files:**
- Modify: `src/main.ts`

- [ ] **Step 1: Import and instantiate InventoryPanel**

Add import at top of `src/main.ts`:
```typescript
import { InventoryPanel } from "./ui/InventoryPanel";
```

After `new BuildingPanel(...)`, add:
```typescript
const inventory = new InventoryPanel(
  () => game.getFurnitureList(),
  (itemId) => game.spawnFurniture(itemId)
);
```

Change the `BuildingPanel` call to show/hide inventory on toggle:
```typescript
new BuildingPanel(
  (active) => {
    game.setBuilding(active);
    active ? inventory.show() : inventory.hide();
  },
  () => game.saveLayout(),
  (on) => game.setRemoveWalls(on)
);
```

- [ ] **Step 2: Full verification**

Run `npm run dev`. Test:
1. Click "🔨 Building" — inventory panel appears on right side
2. Click "+" next to "Sofá" — sofa appears in center of room, counter updates to "1/4"
3. Click "+" 3 more times — counter reaches "4/4", button disables
4. Click "+" when disabled — nothing happens
5. Deactivate building mode — panel disappears
6. Walk toward a sofa — player stops at the tile

- [ ] **Step 3: Commit**
```
git add src/main.ts
git commit -m "feat: wire InventoryPanel to BuildingPanel toggle and Game.spawnFurniture"
```
