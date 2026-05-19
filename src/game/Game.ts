import { Application, Container } from "pixi.js";
import { Room } from "./Room";
import { Player } from "./Player";
import { NPC } from "./NPC";
import { AgentEditor } from "./AgentEditor";
import { AgentData } from "./NPC";
import { NitroFurniture } from "./NitroFurniture";
import { FurnitureEditor } from "./FurnitureEditor";
import { ASSETS } from "./constants";
import { CollisionMap } from "./CollisionMap";
import { ROOM_COLS, ROOM_ROWS, WALL_HEIGHT, isoToScreen } from "./iso";
import { MultiplayerService } from '../multiplayer/MultiplayerService'
import { RemotePlayer } from '../multiplayer/RemotePlayer'

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
  {
    id: "table",
    url: ASSETS.nitroTable,
    defaultCol: 5,
    defaultRow: 4,
    defaultDir: 2,
    validDirs: [0, 2, 4, 6],
  },
  {
    id: "plant",
    url: ASSETS.nitroPlant,
    defaultCol: 3,
    defaultRow: 2,
    defaultDir: 0,
    validDirs: [0, 2, 4, 6],
  },

  // --- novos assets ---
  { id: "deskcomp",       url: ASSETS.nitroDeskComp,       defaultCol: 7, defaultRow: 2, defaultDir: 4, validDirs: [2, 4] },
  { id: "leatherchr",     url: ASSETS.nitroLeatherChr,     defaultCol: 6, defaultRow: 4, defaultDir: 2, validDirs: [0, 2, 4, 6] },
  { id: "officetent",     url: ASSETS.nitroOfficeTent,     defaultCol: 5, defaultRow: 5, defaultDir: 2, validDirs: [2, 4] },
  { id: "armyplant",      url: ASSETS.nitroArmyPlant,      defaultCol: 2, defaultRow: 2, defaultDir: 0, validDirs: [0, 2, 4, 6] },
  { id: "tie",            url: ASSETS.nitroTie,            defaultCol: 5, defaultRow: 3, defaultDir: 0, validDirs: [0, 2, 4, 6] },
  { id: "flatscreen",     url: ASSETS.nitroFlatscreen,     defaultCol: 8, defaultRow: 1, defaultDir: 4, validDirs: [2, 4] },
  { id: "laptop",         url: ASSETS.nitroLaptop,         defaultCol: 7, defaultRow: 3, defaultDir: 2, validDirs: [0, 2, 4, 6] },
  { id: "oldcomputer",    url: ASSETS.nitroOldComputer,    defaultCol: 8, defaultRow: 4, defaultDir: 4, validDirs: [2, 4] },
  { id: "eastertable",    url: ASSETS.nitroEasterTable,    defaultCol: 5, defaultRow: 5, defaultDir: 2, validDirs: [0, 2, 4, 6] },
  { id: "printer",        url: ASSETS.nitroPrinter,        defaultCol: 7, defaultRow: 5, defaultDir: 4, validDirs: [2, 4] },
  { id: "exewall",        url: ASSETS.nitroExeWall,        defaultCol: 4, defaultRow: 0, defaultDir: 4, validDirs: [2, 4], includeShadow: false, yOffset: 30 },
  { id: "drinkscabinet",  url: ASSETS.nitroDrinksCabinet,  defaultCol: 3, defaultRow: 5, defaultDir: 2, validDirs: [0, 2, 4, 6] },
  { id: "glassdivider",   url: ASSETS.nitroGlassDivider,   defaultCol: 6, defaultRow: 3, defaultDir: 2, validDirs: [2, 4] },
  { id: "globe",          url: ASSETS.nitroGlobe,          defaultCol: 5, defaultRow: 4, defaultDir: 0, validDirs: [0, 2, 4, 6] },
  { id: "exeplant",       url: ASSETS.nitroExePlant,       defaultCol: 2, defaultRow: 4, defaultDir: 0, validDirs: [0, 2, 4, 6] },
  { id: "rug",            url: ASSETS.nitroRug,            defaultCol: 5, defaultRow: 5, defaultDir: 0, validDirs: [0, 2, 4, 6] },
  { id: "exetable",       url: ASSETS.nitroExeTable,       defaultCol: 5, defaultRow: 4, defaultDir: 2, validDirs: [0, 2, 4, 6] },
  { id: "execchair",      url: ASSETS.nitroExeChair,       defaultCol: 7, defaultRow: 4, defaultDir: 2, validDirs: [0, 2, 4, 6] },
  { id: "execchair2",     url: ASSETS.nitroExeChair2,      defaultCol: 6, defaultRow: 5, defaultDir: 4, validDirs: [0, 2, 4, 6] },
  { id: "cubelight",      url: ASSETS.nitroCubeLight,      defaultCol: 3, defaultRow: 3, defaultDir: 0, validDirs: [0, 2, 4, 6] },
  { id: "elevator",       url: ASSETS.nitroElevator,       defaultCol: 1, defaultRow: 1, defaultDir: 2, validDirs: [2, 4] },
  { id: "hcglasdvdr",     url: ASSETS.nitroHcGlassDivider, defaultCol: 7, defaultRow: 3, defaultDir: 2, validDirs: [2, 4] },
  { id: "exelight",       url: ASSETS.nitroExeLight,       defaultCol: 4, defaultRow: 2, defaultDir: 0, validDirs: [0, 2, 4, 6] },
  { id: "exesmalltable",  url: ASSETS.nitroExeSmallTable,  defaultCol: 6, defaultRow: 4, defaultDir: 2, validDirs: [0, 2, 4, 6] },
  { id: "seccam",         url: ASSETS.nitroSecCam,         defaultCol: 2, defaultRow: 2, defaultDir: 4, validDirs: [0, 2, 4, 6] },
  { id: "exesofa",        url: ASSETS.nitroExeSofa,        defaultCol: 4, defaultRow: 6, defaultDir: 2, validDirs: [0, 2, 4, 6] },
  { id: "exebigtable",    url: ASSETS.nitroExeBigTable,    defaultCol: 5, defaultRow: 5, defaultDir: 2, validDirs: [0, 2, 4, 6] },
  { id: "waterfall",      url: ASSETS.nitroWaterfall,      defaultCol: 2, defaultRow: 2, defaultDir: 2, validDirs: [2, 4] },
  { id: "workdesk",       url: ASSETS.nitroWorkDesk,       defaultCol: 8, defaultRow: 2, defaultDir: 4, validDirs: [2, 4] },
  { id: "hc21",           url: ASSETS.nitroHc21,           defaultCol: 5, defaultRow: 5, defaultDir: 0, validDirs: [0, 2, 4, 6] },
  { id: "exenewsofa",     url: ASSETS.nitroExeNewSofa,     defaultCol: 4, defaultRow: 6, defaultDir: 2, validDirs: [0, 2, 4, 6] },
  { id: "labmachine",     url: ASSETS.nitroLabMachine,     defaultCol: 3, defaultRow: 4, defaultDir: 2, validDirs: [0, 2, 4, 6] },
  { id: "laptopdesk",     url: ASSETS.nitroLaptopDesk,     defaultCol: 7, defaultRow: 2, defaultDir: 4, validDirs: [2, 4] },
  { id: "newchair",       url: ASSETS.nitroNewChair,       defaultCol: 6, defaultRow: 4, defaultDir: 2, validDirs: [0, 2, 4, 6] },
  { id: "xmasdeskitems",  url: ASSETS.nitroXmasDeskItems,  defaultCol: 7, defaultRow: 3, defaultDir: 2, validDirs: [0, 2, 4, 6] },
];

export class Game {
  app: Application;
  world!: Container;
  room!: Room;
  player!: Player;
  npcs: NPC[] = [];
  furniture: NitroFurniture[] = [];
  private editor!: FurnitureEditor;
  agentEditor!: AgentEditor;
  collision!: CollisionMap;
  private onNpcClick: NPCClickHandler | null = null;
  private remotePlayers = new Map<string, RemotePlayer | null>()
  private mp: MultiplayerService | null = null

  constructor(app: Application) {
    this.app = app;
  }

  async init(container: HTMLElement, mp?: MultiplayerService) {
    container.appendChild(this.app.canvas);

    this.world = new Container();
    this.app.stage.addChild(this.world);

    this.room = await Room.load();
    this.world.addChild(this.room);

    const savedMap = await this.fetchSavedPositions();

    this.collision = new CollisionMap();
    this.editor = new FurnitureEditor(this.app, this.world, this.collision);
    this.editor.onMoved = () => this.sortDepth();

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

    // Editable furniture — only items explicitly saved in the DB are loaded.
    // Iterating savedMap (not FURNITURE_CONFIG) correctly handles multi-instance
    // IDs like "sofa_2", "sofa_3" that spawnFurniture creates over time.
    for (const [id, saved] of savedMap) {
      if (saved.removed) continue;
      if (id.startsWith("wall_")) continue; // walls already handled above

      const baseId = id.replace(/_\d+$/, "");
      const cfg = FURNITURE_CONFIG.find((c) => c.id === baseId);
      if (!cfg) continue;

      const item = await NitroFurniture.load(cfg.url, {
        col: saved.col,
        row: saved.row,
        direction: saved.direction,
        includeShadow: cfg.includeShadow,
        yOffset: cfg.yOffset,
      });
      item.id = id;
      item.validDirections = cfg.validDirs;
      this.world.addChild(item);
      this.furniture.push(item);
      this.editor.register(item);
    }

    this.player = await Player.load();
    this.player.collisionMap = this.collision;
    this.world.addChild(this.player);

    this.agentEditor = new AgentEditor(this.app, this.world);

    try {
      const res = await fetch("/api/agents");
      if (res.ok) {
        const agents = (await res.json()) as AgentData[];
        for (const data of agents) {
          const npc = await NPC.fromAgentData(data);
          this.agentEditor.register(npc);
          npc.on("pointerdown", () => {
            if (!this.agentEditor.isActive && this.onNpcClick) {
              this.onNpcClick(npc);
            }
          });
          this.world.addChild(npc);
          this.npcs.push(npc);
        }
      }
    } catch (err) {
      console.error("[Game] Failed to load agents:", err);
    }

    if (mp) {
      this.mp = mp

      mp.onPlayerJoined = async (data) => {
        try {
          this.remotePlayers.set(data.id, null)
          const rp = await RemotePlayer.load(data)
          if (!this.remotePlayers.has(data.id)) {
            rp.destroy()
            return
          }
          this.world.addChild(rp)
          this.remotePlayers.set(data.id, rp)
        } catch (err) {
          console.error('[Game] RemotePlayer.load failed for', data.id, err)
          this.remotePlayers.delete(data.id)
        }
      }

      mp.onPlayerLeft = (id) => {
        const rp = this.remotePlayers.get(id)
        this.remotePlayers.delete(id)
        if (rp) {
          this.world.removeChild(rp)
          rp.destroy()
        }
      }

      mp.onPlayerMoved = (id, col, row, dir) => {
        this.remotePlayers.get(id)?.setTarget(col, row, dir)
      }

      mp.announceExistingPlayers()
    }

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

  setAgentMode(active: boolean) {
    this.agentEditor.setActive(active);
  }

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

    const isWallDeco = cfg.id === "exewall";
    const spawnCol = isWallDeco ? cfg.defaultCol : col;
    const spawnRow = isWallDeco ? cfg.defaultRow : row;

    const item = await NitroFurniture.load(cfg.url, {
      col: spawnCol,
      row: spawnRow,
      direction: cfg.defaultDir,
      includeShadow: cfg.includeShadow,
      yOffset: cfg.yOffset,
    });
    item.id = newId;
    item.validDirections = cfg.validDirs;
    this.world.addChild(item);
    this.furniture.push(item);
    this.editor.register(item, isWallDeco);
    this.sortDepth();
  }

  removeFurniture(baseId: string): void {
    const active = this.furniture.filter(
      (f) => (f.id === baseId || f.id.startsWith(baseId + "_")) && f.visible
    );
    if (active.length === 0) return;
    const item = active[active.length - 1];
    item.visible = false;
    this.collision.unblock(item.worldCol, item.worldRow);
    this.editor.markRemoved(item);
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
    for (const rp of this.remotePlayers.values()) rp?.update(dt);
    this.mp?.sendPosition(this.player.worldCol, this.player.worldRow, this.player.currentDir);
    this.sortDepth();
  }

  private sortDepth() {
    // Wall panels have a yOffset that inflates f.y, causing them to sort as if
    // they are closer to camera than floor furniture at the same or lower row.
    // Fix: sort furniture by logical tile Y (no yOffset), with a small negative
    // bias for wall panels so they always render behind same-tile floor items.
    const furnitureY = (f: NitroFurniture) => {
      const tileY = isoToScreen(f.worldCol, f.worldRow).y;
      const isWall = f.id.startsWith("wall_") || /^exewall(_\d+)?$/.test(f.id);
      return isWall ? tileY - 1 : tileY;
    };

    const items: { obj: Container; y: number }[] = [
      { obj: this.player, y: this.player.y },
      ...[...this.remotePlayers.values()].flatMap((rp) => rp ? [{ obj: rp as Container, y: rp.y }] : []),
      ...this.npcs.map((n) => ({ obj: n as Container, y: n.y })),
      ...this.furniture.map((f) => ({ obj: f as Container, y: furnitureY(f) })),
    ];
    items.sort((a, b) => a.y - b.y);
    items.forEach((item, idx) => {
      this.world.setChildIndex(
        item.obj,
        this.world.children.length - items.length + idx
      );
    });
    this.editor.bringToFront();
    this.agentEditor.bringToFront();
  }

  setAgentWorking(agentId: string, active: boolean): void {
    const npc = this.npcs.find((n) => n.id === agentId);
    npc?.setWorking(active);
  }

  setNpcClickHandler(handler: NPCClickHandler) {
    this.onNpcClick = handler;
  }
}
