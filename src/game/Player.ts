import { Container, Sprite, Texture, Assets } from "pixi.js";
import { ASSETS, PLAYER_SPEED } from "./constants";
import { clampToRoom, isoToScreen } from "./iso";
import { CollisionMap } from "./CollisionMap";

type Dir = "front" | "back" | "left" | "right";
type DirKey = "front" | "back" | "side";

const WALK_FPS = 8;
const IDLE_FPS = 4;

const DIRS: DirKey[] = ["front", "back", "side"];

export class Player extends Container {
  private sprite!: Sprite;
  private shadow!: Sprite;

  private idleTextures: Record<DirKey, Texture[]> = { front: [], back: [], side: [] };
  private walkTextures: Record<DirKey, Texture[]> = { front: [], back: [], side: [] };

  private dir: Dir = "front";

  get currentDir(): string {
    return this.dir;
  }

  // Each direction key has its own independent frame counter
  private idleFrame:  Record<DirKey, number> = { front: 0, back: 0, side: 0 };
  private idleTimer:  Record<DirKey, number> = { front: 0, back: 0, side: 0 };
  private walkFrame:  Record<DirKey, number> = { front: 0, back: 0, side: 0 };
  private walkTimer:  Record<DirKey, number> = { front: 0, back: 0, side: 0 };

  worldCol = 0.5;
  worldRow = 4.5;

  private keys: Record<string, boolean> = {};
  collisionMap: CollisionMap | null = null;

  static async load(): Promise<Player> {
    const p = new Player();

    const all = await Promise.all([
      Assets.load(ASSETS.shadow),
      ...[1, 2, 3, 4, 5].map((i) => Assets.load(`/avatar/front_${i}_iddle.png`)),
      ...[1, 2, 3, 4, 5].map((i) => Assets.load(`/avatar/back_${i}_iddle.png`)),
      ...[1, 2, 3, 4, 5].map((i) => Assets.load(`/avatar/side_${i}_iddle.png`)),
      ...[1, 2, 3, 4, 5].map((i) => Assets.load(`/avatar/front_${i}_walking.png`)),
      ...[1, 2, 3, 4, 5].map((i) => Assets.load(`/avatar/back_${i}_walking.png`)),
      ...[1, 2, 3, 4, 5].map((i) => Assets.load(`/avatar/side_${i}_walking.png`)),
    ]);

    const [shadowTex, ...rest] = all;
    p.idleTextures.front = rest.slice(0,  5);
    p.idleTextures.back  = rest.slice(5,  10);
    p.idleTextures.side  = rest.slice(10, 15);
    p.walkTextures.front = rest.slice(15, 20);
    p.walkTextures.back  = rest.slice(20, 25);
    p.walkTextures.side  = rest.slice(25, 30);

    p.shadow = new Sprite(shadowTex);
    p.shadow.anchor.set(0.5, 0.5);
    p.shadow.alpha = 0.45;
    p.shadow.y = 4;
    p.shadow.scale.set(1.1, 0.75);
    p.addChild(p.shadow);

    p.sprite = new Sprite(p.idleTextures.front[0]);
    p.sprite.anchor.set(0.5, 1);
    p.sprite.scale.set(2.64);
    p.addChild(p.sprite);

    p.bindInput();
    p.syncScreen();
    return p;
  }

  private bindInput() {
    window.addEventListener("keydown", (e) => { this.keys[e.key.toLowerCase()] = true; });
    window.addEventListener("keyup",   (e) => { this.keys[e.key.toLowerCase()] = false; });
  }

  update(dt: number) {
    let sx = 0;
    let sy = 0;

    if (this.keys["w"] || this.keys["arrowup"])   sy -= 1;
    if (this.keys["s"] || this.keys["arrowdown"])  sy += 1;
    if (this.keys["a"] || this.keys["arrowleft"])  sx -= 1;
    if (this.keys["d"] || this.keys["arrowright"]) sx += 1;

    const moving = sx !== 0 || sy !== 0;

    if (moving) {
      let dCol = sy + sx * 0.5;
      let dRow = sy - sx * 0.5;
      const len = Math.hypot(dCol, dRow);
      dCol = (dCol / len) * (PLAYER_SPEED / 32);
      dRow = (dRow / len) * (PLAYER_SPEED / 32);

      const next = clampToRoom(this.worldCol + dCol, this.worldRow + dRow);
      const tileCol = Math.round(next.col);
      const tileRow = Math.round(next.row);
      if (!this.collisionMap || !this.collisionMap.isBlocked(tileCol, tileRow)) {
        this.worldCol = next.col;
        this.worldRow = next.row;
      }

      if (Math.abs(sx) > Math.abs(sy)) {
        this.dir = sx > 0 ? "right" : "left";
      } else {
        this.dir = sy > 0 ? "front" : "back";
      }
    }

    // Advance all direction counters independently every frame
    const idleTicks = 60 / IDLE_FPS;
    const walkTicks = 60 / WALK_FPS;
    for (const k of DIRS) {
      this.idleTimer[k] += dt;
      if (this.idleTimer[k] >= idleTicks) {
        this.idleTimer[k] -= idleTicks;
        this.idleFrame[k] = (this.idleFrame[k] + 1) % 5;
      }
      this.walkTimer[k] += dt;
      if (this.walkTimer[k] >= walkTicks) {
        this.walkTimer[k] -= walkTicks;
        this.walkFrame[k] = (this.walkFrame[k] + 1) % 5;
      }
    }

    this.updateSprite(moving);
    this.syncScreen();
  }

  private syncScreen() {
    const p = isoToScreen(this.worldCol, this.worldRow);
    this.x = p.x;
    this.y = p.y;
  }

  private updateSprite(walking: boolean) {
    const dirKey = this.dir === "left" || this.dir === "right" ? "side" : this.dir;
    const flip   = this.dir === "left" ? -1 : 1;

    this.sprite.texture = walking
      ? this.walkTextures[dirKey][this.walkFrame[dirKey]]
      : this.idleTextures[dirKey][this.idleFrame[dirKey]];

    this.sprite.scale.x = 2.64 * flip;
  }
}
