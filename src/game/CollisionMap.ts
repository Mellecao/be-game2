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
