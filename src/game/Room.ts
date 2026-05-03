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
    r.drawDoorframe();
    return r;
  }

  private drawFloor() {
    const halfW = ISO_TILE_W / 2;
    const halfH = ISO_TILE_H / 2;
    const g = new Graphics();

    for (let row = 0; row < ROOM_ROWS; row++) {
      for (let col = 0; col < ROOM_COLS; col++) {
        const c = isoToScreen(col + 0.5, row + 0.5);
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
        const c = isoToScreen(col + 0.5, row + 0.5);
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
    const g = new Graphics();

    // Inner corridor tiles (rows 4 and 5, col -1) — dark entrance
    for (const row of [4, 5]) {
      const c = isoToScreen(-0.5, row + 0.5);
      g.poly([
        c.x,         c.y - halfH,
        c.x + halfW, c.y,
        c.x,         c.y + halfH,
        c.x - halfW, c.y,
      ]).fill(0x1a1a22);
    }

    // Outer corridor tiles (col -2) — deeper dark
    for (const row of [4, 5]) {
      const c = isoToScreen(-1.5, row + 0.5);
      g.poly([
        c.x,         c.y - halfH,
        c.x + halfW, c.y,
        c.x,         c.y + halfH,
        c.x - halfW, c.y,
      ]).fill(0x111118);
    }

    this.addChild(g);
  }

  private drawDoorframe() {
    const wallH = WALL_HEIGHT;
    const lintelH = 40;

    const a = isoToScreen(0, 4);
    const b = isoToScreen(0, 5);
    const w = new Graphics();

    // Lintel face
    w.poly([
      a.x, a.y - wallH,
      b.x, b.y - wallH,
      b.x, b.y - wallH + lintelH,
      a.x, a.y - wallH + lintelH,
    ]).fill(WALL_BACK);

    // Top edge highlight
    w.poly([
      a.x, a.y - wallH,
      b.x, b.y - wallH,
      b.x - 4, b.y - wallH + 4,
      a.x - 4, a.y - wallH + 4,
    ]).fill(WALL_TOP);

    this.addChild(w);
  }
}
