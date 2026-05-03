export const ISO_TILE_W = 64;
export const ISO_TILE_H = 32;
export const ROOM_COLS = 11;
export const ROOM_ROWS = 9;
export const WALL_HEIGHT = 127;

export interface IsoPoint {
  x: number;
  y: number;
}

export function isoToScreen(col: number, row: number): IsoPoint {
  return {
    x: (col - row) * (ISO_TILE_W / 2),
    y: (col + row) * (ISO_TILE_H / 2),
  };
}

export function screenToIso(x: number, y: number): { col: number; row: number } {
  const col = (x / (ISO_TILE_W / 2) + y / (ISO_TILE_H / 2)) / 2;
  const row = (y / (ISO_TILE_H / 2) - x / (ISO_TILE_W / 2)) / 2;
  return { col, row };
}

export function clampToRoom(col: number, row: number, margin = 0.1): { col: number; row: number } {
  return {
    col: Math.max(margin, Math.min(ROOM_COLS - 1 - margin, col)),
    row: Math.max(margin, Math.min(ROOM_ROWS - 1 - margin, row)),
  };
}
