import { Application, Container, Graphics, FederatedPointerEvent } from "pixi.js";
import { NitroFurniture } from "./NitroFurniture";
import {
  ROOM_COLS,
  ROOM_ROWS,
  ISO_TILE_W,
  ISO_TILE_H,
  isoToScreen,
  screenToIso,
} from "./iso";
import { CollisionMap } from "./CollisionMap";

export interface FurnitureLayoutEntry {
  id: string;
  col: number;
  row: number;
  direction: number;
  removed: boolean;
}

export class FurnitureEditor {
  private world: Container;
  private active = false;
  private removeWallsMode = false;

  private items: NitroFurniture[] = [];
  private wallItems = new Set<NitroFurniture>();
  private removedItems = new Set<NitroFurniture>();

  private selected: NitroFurniture | null = null;
  private dragActive = false;
  private ghost: Graphics;

  constructor(app: Application, world: Container, private collision: CollisionMap) {
    this.world = world;

    this.ghost = new Graphics();
    this.ghost.visible = false;
    world.addChild(this.ghost);

    app.stage.eventMode = "static";
    app.stage.on("pointermove", this.onGlobalMove, this);
    app.stage.on("pointerup", this.onGlobalUp, this);
    app.stage.on("pointerdown", this.onStageDown, this);

    window.addEventListener("keydown", this.onKey.bind(this));
  }

  register(item: NitroFurniture, isWall = false) {
    this.items.push(item);
    if (isWall) this.wallItems.add(item);
    this.collision.block(item.worldCol, item.worldRow);

    item.eventMode = "none";
    item.on("pointerdown", (e: FederatedPointerEvent) => {
      e.stopPropagation();
      if (!this.active) return;

      if (this.removeWallsMode && this.wallItems.has(item)) {
        item.visible = false;
        this.removedItems.add(item);
        this.collision.unblock(item.worldCol, item.worldRow);
        return;
      }

      this.select(item);
      this.dragActive = true;
    });
  }

  setActive(active: boolean) {
    this.active = active;
    for (const item of this.items) {
      item.eventMode = active ? "static" : "none";
    }
    if (!active) {
      this.deselect();
      this.removeWallsMode = false;
    }
  }

  setRemoveWallsMode(on: boolean) {
    this.removeWallsMode = on;
    if (!on) this.deselect();
  }

  getLayout(): FurnitureLayoutEntry[] {
    return this.items
      .filter((i) => i.id !== "")
      .map((i) => ({
        id: i.id,
        col: i.worldCol,
        row: i.worldRow,
        direction: i.currentDirection,
        removed: this.removedItems.has(i),
      }));
  }

  bringToFront() {
    this.world.setChildIndex(this.ghost, this.world.children.length - 1);
  }

  private select(item: NitroFurniture) {
    if (this.selected && this.selected !== item) {
      this.selected.tint = 0xffffff;
    }
    this.selected = item;
    item.tint = 0xffdd55;
  }

  private deselect() {
    if (this.selected) this.selected.tint = 0xffffff;
    this.selected = null;
    this.dragActive = false;
    this.ghost.visible = false;
  }

  private onStageDown() {
    if (this.active) this.deselect();
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
    const { col, row } = this.tileAt(e.globalX, e.globalY);
    this.drawGhost(col, row);
  }

  private onGlobalUp(e: FederatedPointerEvent) {
    if (!this.active || !this.dragActive || !this.selected) return;
    const { col, row } = this.tileAt(e.globalX, e.globalY);
    this.collision.unblock(this.selected.worldCol, this.selected.worldRow);
    this.selected.moveTo(col, row);
    this.collision.block(col, row);
    this.dragActive = false;
    this.ghost.visible = false;
  }

  private onKey(e: KeyboardEvent) {
    if (!this.active || !this.selected) return;
    if (e.key === "r" || e.key === "R") {
      this.selected.rotate();
    }
    if (e.key === "Escape") this.deselect();
  }

  private drawGhost(col: number, row: number) {
    const p = isoToScreen(col, row);
    const hw = ISO_TILE_W / 2;
    const hh = ISO_TILE_H / 2;
    this.ghost.clear();
    this.ghost
      .poly([p.x, p.y - hh, p.x + hw, p.y, p.x, p.y + hh, p.x - hw, p.y])
      .fill({ color: 0x00ff88, alpha: 0.3 })
      .stroke({ color: 0x00ff88, width: 2 });
    this.ghost.visible = true;
  }
}
