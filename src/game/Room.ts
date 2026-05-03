import { Container, Graphics, Sprite } from "pixi.js";
import { ASSETS } from "./constants";
import {
  ISO_TILE_H,
  ISO_TILE_W,
  ROOM_COLS,
  ROOM_ROWS,
  WALL_HEIGHT,
  isoToScreen,
} from "./iso";
import { loadNitro, resolveAsset } from "./nitro";

const FLOOR_EDGE = 0x4a3a26;
const TILE_DOOR_COLOR = 0x4a3020;

// Habbo "classic" wall palette — derived from a typical wood-panel wall to
// complement the wood floor. We keep walls procedural for now since no wall
// .nitro is provided.
const WALL_BACK = 0xdcd1a8;
const WALL_TOP = 0xefe6c0;
const WALL_TRIM = 0x6e5832;

export class Room extends Container {
  static async load(): Promise<Room> {
    const r = new Room();
    await r.drawFloor();
    r.drawWalls();
    r.drawDoor();
    return r;
  }

  private async drawFloor() {
    // Use the 1x1 floor tile sprite from classic6_woodfloor.nitro
    // (asset key `_64_b_0_0`, ~63x34 — exactly an iso tile).
    const bundle = await loadNitro(ASSETS.nitroFloor);
    const tileAsset = `${bundle.manifest.name}_64_b_0_0`;
    const resolved = resolveAsset(bundle.manifest, bundle.spritesheet, tileAsset);
    if (!resolved) {
      throw new Error(`Floor tile asset not found in ${ASSETS.nitroFloor}`);
    }

    const tilesLayer = new Container();
    for (let row = 0; row < ROOM_ROWS; row++) {
      for (let col = 0; col < ROOM_COLS; col++) {
        const c = isoToScreen(col, row);
        const sp = new Sprite(resolved.texture);
        // Override the JSON pivot (0.5/0.5) — we anchor by top-left so the
        // Habbo offsets work out correctly.
        sp.anchor.set(0, 0);
        // Offsets are from the tile's east corner, not its center.
        sp.x = c.x + ISO_TILE_W / 2 - resolved.offsetX;
        sp.y = c.y - resolved.offsetY;
        tilesLayer.addChild(sp);
      }
    }
    this.addChild(tilesLayer);

    // Per-tile borders for the iconic Habbo grid look.
    const borders = new Graphics();
    const halfW = ISO_TILE_W / 2;
    const halfH = ISO_TILE_H / 2;
    for (let row = 0; row < ROOM_ROWS; row++) {
      for (let col = 0; col < ROOM_COLS; col++) {
        const c = isoToScreen(col, row);
        borders.poly([
          c.x, c.y - halfH,
          c.x + halfW, c.y,
          c.x, c.y + halfH,
          c.x - halfW, c.y,
        ]).stroke({ color: FLOOR_EDGE, width: 1, alpha: 0.3 });
      }
    }
    this.addChild(borders);
  }

  private drawWalls() {
    const wallH = WALL_HEIGHT;

    // BACK-LEFT wall: solid color with a trim line at the bottom.
    {
      const a = isoToScreen(0, 0);
      const b = isoToScreen(0, ROOM_ROWS);
      const wall = new Graphics();
      wall.poly([
        a.x, a.y - wallH,
        b.x, b.y - wallH,
        b.x, b.y,
        a.x, a.y,
      ]).fill(WALL_BACK);
      // Top edge highlight (suggests a 3D wall thickness).
      wall.poly([
        a.x, a.y - wallH,
        b.x, b.y - wallH,
        b.x - 4, b.y - wallH + 4,
        a.x - 4, a.y - wallH + 4,
      ]).fill(WALL_TOP);
      // Bottom trim (skirting board).
      wall.poly([
        a.x, a.y - 6,
        b.x, b.y - 6,
        b.x, b.y,
        a.x, a.y,
      ]).fill(WALL_TRIM);
      this.addChild(wall);
    }

    // BACK-RIGHT wall.
    {
      const a = isoToScreen(0, 0);
      const b = isoToScreen(ROOM_COLS, 0);
      const wall = new Graphics();
      wall.poly([
        a.x, a.y - wallH,
        b.x, b.y - wallH,
        b.x, b.y,
        a.x, a.y,
      ]).fill(WALL_BACK);
      wall.poly([
        a.x, a.y - wallH,
        b.x, b.y - wallH,
        b.x + 4, b.y - wallH + 4,
        a.x + 4, a.y - wallH + 4,
      ]).fill(WALL_TOP);
      wall.poly([
        a.x, a.y - 6,
        b.x, b.y - 6,
        b.x, b.y,
        a.x, a.y,
      ]).fill(WALL_TRIM);
      this.addChild(wall);
    }
  }

  private drawDoor() {
    const g = new Graphics();
    const doorBottom = isoToScreen(0, 5);
    const doorH = 78;
    const doorW = 28;
    g.poly([
      doorBottom.x - doorW, doorBottom.y - 14 - doorH,
      doorBottom.x - doorW, doorBottom.y - 14,
      doorBottom.x, doorBottom.y - 14 + 14,
      doorBottom.x, doorBottom.y - 14 - doorH + 14,
    ]).fill(TILE_DOOR_COLOR);
    g.circle(doorBottom.x - 5, doorBottom.y - 14 - doorH / 2 + 6, 1.5).fill(0xffd700);
    this.addChild(g);
  }
}
