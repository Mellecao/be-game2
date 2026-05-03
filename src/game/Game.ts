import { Application, Container } from "pixi.js";
import { Room } from "./Room";
import { Player } from "./Player";
import { NPC } from "./NPC";
import { NitroFurniture } from "./NitroFurniture";
import { FurnitureEditor } from "./FurnitureEditor";
import { ASSETS } from "./constants";
import { ROOM_COLS, ROOM_ROWS, WALL_HEIGHT, isoToScreen } from "./iso";

export type NPCClickHandler = (npc: NPC) => void;

interface FurnitureConfig {
  id: string;
  url: string;
  defaultCol: number;
  defaultRow: number;
  defaultDir: number;
  validDirs: number[];
  includeShadow?: boolean;
  yOffset?: number;
}

interface SavedPlacement {
  col: number;
  row: number;
  direction: number;
  removed?: boolean;
}

const FURNITURE_CONFIG: FurnitureConfig[] = [
  {
    id: "window",
    url: ASSETS.nitroWindow,
    defaultCol: 6,
    defaultRow: 0,
    defaultDir: 4,
    validDirs: [2, 4],
    includeShadow: false,
    yOffset: 30,
  },
  {
    id: "sofa",
    url: ASSETS.nitroSofa,
    defaultCol: 4,
    defaultRow: 6,
    defaultDir: 2,
    validDirs: [0, 2, 4, 6],
  },
  {
    id: "chair",
    url: ASSETS.nitroChair,
    defaultCol: 8,
    defaultRow: 3,
    defaultDir: 4,
    validDirs: [0, 2, 4, 6],
  },
  {
    id: "desk",
    url: ASSETS.nitroDeskTable,
    defaultCol: 8,
    defaultRow: 2,
    defaultDir: 4,
    validDirs: [2, 4],
  },
];

export class Game {
  app: Application;
  world!: Container;
  room!: Room;
  player!: Player;
  npcs: NPC[] = [];
  furniture: NitroFurniture[] = [];
  private editor!: FurnitureEditor;
  private onNpcClick: NPCClickHandler | null = null;

  constructor(app: Application) {
    this.app = app;
  }

  async init(container: HTMLElement) {
    container.appendChild(this.app.canvas);

    this.world = new Container();
    this.app.stage.addChild(this.world);

    this.room = await Room.load();
    this.world.addChild(this.room);

    const savedMap = await this.fetchSavedPositions();

    this.editor = new FurnitureEditor(this.app, this.world);

    // Back-right wall panels: id = "wall_r_{col}"
    for (let col = 0; col < ROOM_COLS - 1; col += 2) {
      const id = `wall_r_${col}`;
      const saved = savedMap.get(id);
      if (saved?.removed) continue;

      const panel = await NitroFurniture.load(ASSETS.nitroWallPanel, {
        col: saved?.col ?? col,
        row: saved?.row ?? 0,
        direction: saved?.direction ?? 0,
        includeShadow: false,
        yOffset: 40,
      });
      panel.id = id;
      panel.validDirections = [0, 2];
      this.world.addChild(panel);
      this.furniture.push(panel);
      this.editor.register(panel, true);
    }

    // Back-left wall panels: id = "wall_l_{row}"
    for (let row = 0; row < ROOM_ROWS - 1; row += 2) {
      if (row === 4) continue; // door opening
      const id = `wall_l_${row}`;
      const saved = savedMap.get(id);
      if (saved?.removed) continue;

      const panel = await NitroFurniture.load(ASSETS.nitroWallPanel, {
        col: saved?.col ?? 0,
        row: saved?.row ?? row,
        direction: saved?.direction ?? 2,
        includeShadow: false,
        yOffset: 40,
      });
      panel.id = id;
      panel.validDirections = [0, 2];
      this.world.addChild(panel);
      this.furniture.push(panel);
      this.editor.register(panel, true);
    }

    // Editable furniture
    for (const cfg of FURNITURE_CONFIG) {
      const saved = savedMap.get(cfg.id);
      if (saved?.removed) continue;

      const item = await NitroFurniture.load(cfg.url, {
        col: saved?.col ?? cfg.defaultCol,
        row: saved?.row ?? cfg.defaultRow,
        direction: saved?.direction ?? cfg.defaultDir,
        includeShadow: cfg.includeShadow,
        yOffset: cfg.yOffset,
      });
      item.id = cfg.id;
      item.validDirections = cfg.validDirs;
      this.world.addChild(item);
      this.furniture.push(item);
      this.editor.register(item);
    }

    this.player = await Player.load();
    this.world.addChild(this.player);

    const copywriter = await NPC.create("copywriter", "Copywriter", 7, 3);
    copywriter.on("pointerdown", () => {
      if (this.onNpcClick) this.onNpcClick(copywriter);
    });
    this.world.addChild(copywriter);
    this.npcs.push(copywriter);

    this.handleResize();
    window.addEventListener("resize", () => this.handleResize());
    this.app.ticker.add((ticker) => this.update(ticker.deltaTime));
  }

  setBuilding(active: boolean) {
    this.editor.setActive(active);
  }

  setRemoveWalls(on: boolean) {
    this.editor.setRemoveWallsMode(on);
  }

  async saveLayout(): Promise<void> {
    const layout = this.editor.getLayout();
    const res = await fetch("/api/furniture/save-all", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(layout),
    });
    if (!res.ok) throw new Error(`Save failed: ${res.status}`);
  }

  private async fetchSavedPositions(): Promise<Map<string, SavedPlacement>> {
    try {
      const res = await fetch("/api/furniture");
      if (!res.ok) return new Map();
      const data = (await res.json()) as Array<
        { id: string } & SavedPlacement
      >;
      return new Map(data.map((d) => [d.id, d]));
    } catch {
      return new Map();
    }
  }

  private handleResize() {
    this.app.renderer.resize(window.innerWidth, window.innerHeight);

    const tl = isoToScreen(0, 0);
    const tr = isoToScreen(ROOM_COLS, 0);
    const bl = isoToScreen(0, ROOM_ROWS);
    const br = isoToScreen(ROOM_COLS, ROOM_ROWS);

    const minX = Math.min(tl.x, tr.x, bl.x, br.x);
    const maxX = Math.max(tl.x, tr.x, bl.x, br.x);
    const minY = Math.min(tl.y, tr.y, bl.y, br.y) - WALL_HEIGHT;
    const maxY = Math.max(tl.y, tr.y, bl.y, br.y);

    const roomW = maxX - minX;
    const roomH = maxY - minY;

    this.world.x = (this.app.screen.width - roomW) / 2 - minX;
    this.world.y = (this.app.screen.height - roomH) / 2 - minY;
  }

  private update(dt: number) {
    this.player.update(dt);
    for (const npc of this.npcs) npc.update(dt);
    this.sortDepth();
  }

  private sortDepth() {
    const items: { obj: Container; y: number }[] = [
      { obj: this.player, y: this.player.y },
      ...this.npcs.map((n) => ({ obj: n as Container, y: n.y })),
      ...this.furniture.map((f) => ({ obj: f as Container, y: f.y })),
    ];
    items.sort((a, b) => a.y - b.y);
    items.forEach((item, idx) => {
      this.world.setChildIndex(
        item.obj,
        this.world.children.length - items.length + idx
      );
    });
    this.editor.bringToFront();
  }

  setNpcClickHandler(handler: NPCClickHandler) {
    this.onNpcClick = handler;
  }
}
