import { Application, Container, Graphics, FederatedPointerEvent } from "pixi.js";
import { NPC } from "./NPC";
import { ISO_TILE_W, ISO_TILE_H, ROOM_COLS, ROOM_ROWS, isoToScreen, screenToIso } from "./iso";

export class AgentEditor {
  private active = false;
  private npcs: NPC[] = [];
  private selected: NPC | null = null;
  private dragActive = false;
  private dragMoved = false;
  private ghost: Graphics;
  onSelect: ((npc: NPC) => void) | null = null;

  constructor(private app: Application, private world: Container) {
    this.ghost = new Graphics();
    this.ghost.visible = false;
    world.addChild(this.ghost);

    app.stage.on("pointermove", this.onGlobalMove, this);
    app.stage.on("pointerup", this.onGlobalUp, this);
  }

  register(npc: NPC) {
    this.npcs.push(npc);
    npc.on("pointerdown", (e: FederatedPointerEvent) => {
      e.stopPropagation();
      if (!this.active) return;
      this.select(npc);
      this.dragActive = true;
      this.dragMoved = false;
    });
  }

  setActive(active: boolean) {
    this.active = active;
    for (const npc of this.npcs) {
      npc.eventMode = active ? "static" : "none";
    }
    if (!active) this.deselect();
  }

  private select(npc: NPC) {
    if (this.selected && this.selected !== npc) this.selected.tint = 0xffffff;
    this.selected = npc;
    npc.tint = 0xffdd55;
  }

  private deselect() {
    if (this.selected) this.selected.tint = 0xffffff;
    this.selected = null;
    this.dragActive = false;
    this.ghost.visible = false;
  }

  private tileAt(gx: number, gy: number): { col: number; row: number } {
    const wx = gx - this.world.x;
    const wy = gy - this.world.y;
    const { col, row } = screenToIso(wx, wy);
    return {
      col: Math.max(0, Math.min(ROOM_COLS - 1, Math.round(col))),
      row: Math.max(0, Math.min(ROOM_ROWS - 1, Math.round(row))),
    };
  }

  private onGlobalMove(e: FederatedPointerEvent) {
    if (!this.active || !this.dragActive || !this.selected) return;
    this.dragMoved = true;
    const { col, row } = this.tileAt(e.globalX, e.globalY);
    this.drawGhost(col, row);
  }

  private onGlobalUp(e: FederatedPointerEvent) {
    if (!this.active || !this.dragActive || !this.selected) return;

    if (!this.dragMoved) {
      // Click without drag — open config
      const npc = this.selected;
      this.deselect();
      if (this.onSelect) this.onSelect(npc);
      return;
    }

    const { col, row } = this.tileAt(e.globalX, e.globalY);
    this.selected.worldCol = col;
    this.selected.worldRow = row;
    this.selected.syncScreen();

    const id = this.selected.id;
    fetch(`/api/agents/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ col, row }),
    }).catch((err) => console.error("[AgentEditor] save position failed", err));

    this.deselect();
  }

  private drawGhost(col: number, row: number) {
    const p = isoToScreen(col, row);
    const hw = ISO_TILE_W / 2;
    const hh = ISO_TILE_H / 2;
    this.ghost.clear();
    this.ghost
      .poly([p.x, p.y - hh, p.x + hw, p.y, p.x, p.y + hh, p.x - hw, p.y])
      .fill({ color: 0x55aaff, alpha: 0.3 })
      .stroke({ color: 0x55aaff, width: 2 });
    this.ghost.visible = true;
  }

  bringToFront() {
    this.world.setChildIndex(this.ghost, this.world.children.length - 1);
  }
}
