import { Container, Sprite, Texture, Assets } from "pixi.js";
import { ASSETS, PLAYER_SPEED } from "./constants";
import { clampToRoom, isoToScreen } from "./iso";

type Dir = "front" | "back" | "left" | "right";

export class Player extends Container {
  private sprite!: Sprite;
  private shadow!: Sprite;
  private textures: Record<string, Texture> = {};
  private dir: Dir = "front";

  // World position in iso tile coordinates (col, row), can be fractional
  worldCol = 5;
  worldRow = 5;

  private keys: Record<string, boolean> = {};

  static async load(): Promise<Player> {
    const p = new Player();
    p.textures.frontIdle = await Assets.load(ASSETS.avatarFrontIdle);
    p.textures.frontWalk = await Assets.load(ASSETS.avatarFrontWalk);
    p.textures.backIdle = await Assets.load(ASSETS.avatarBackIdle);
    p.textures.backWalk = await Assets.load(ASSETS.avatarBackWalk);
    p.textures.sideIdle = await Assets.load(ASSETS.avatarSideIdle);
    p.textures.sideWalk = await Assets.load(ASSETS.avatarSideWalk);
    const shadowTex = await Assets.load(ASSETS.shadow);

    p.shadow = new Sprite(shadowTex);
    p.shadow.anchor.set(0.5, 0.5);
    p.shadow.alpha = 0.45;
    p.shadow.y = 4;
    p.shadow.scale.set(0.9, 0.6);
    p.addChild(p.shadow);

    p.sprite = new Sprite(p.textures.frontIdle);
    p.sprite.anchor.set(0.5, 1);
    p.sprite.scale.set(1.6);
    p.addChild(p.sprite);

    p.bindInput();
    p.syncScreen();
    return p;
  }

  private bindInput() {
    window.addEventListener("keydown", (e) => {
      this.keys[e.key.toLowerCase()] = true;
    });
    window.addEventListener("keyup", (e) => {
      this.keys[e.key.toLowerCase()] = false;
    });
  }

  update(_dt: number) {
    let sx = 0; // screen-relative x
    let sy = 0; // screen-relative y

    if (this.keys["w"] || this.keys["arrowup"]) sy -= 1;
    if (this.keys["s"] || this.keys["arrowdown"]) sy += 1;
    if (this.keys["a"] || this.keys["arrowleft"]) sx -= 1;
    if (this.keys["d"] || this.keys["arrowright"]) sx += 1;

    const moving = sx !== 0 || sy !== 0;

    if (moving) {
      // Convert screen-direction to iso world direction
      // screen +x = (col-row), screen +y = (col+row)/2
      // so dCol = sy*2 + sx, dRow = sy*2 - sx (then normalize)
      let dCol = sy + sx * 0.5;
      let dRow = sy - sx * 0.5;
      const len = Math.hypot(dCol, dRow);
      dCol = (dCol / len) * (PLAYER_SPEED / 32);
      dRow = (dRow / len) * (PLAYER_SPEED / 32);

      const next = clampToRoom(this.worldCol + dCol, this.worldRow + dRow);
      this.worldCol = next.col;
      this.worldRow = next.row;

      // Direction for sprite
      if (Math.abs(sx) > Math.abs(sy)) {
        this.dir = sx > 0 ? "right" : "left";
      } else {
        this.dir = sy > 0 ? "front" : "back";
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
    let tex: Texture;
    let flip = 1;
    if (this.dir === "front") {
      tex = walking ? this.textures.frontWalk : this.textures.frontIdle;
    } else if (this.dir === "back") {
      tex = walking ? this.textures.backWalk : this.textures.backIdle;
    } else {
      tex = walking ? this.textures.sideWalk : this.textures.sideIdle;
      flip = this.dir === "left" ? -1 : 1;
    }
    this.sprite.texture = tex;
    this.sprite.scale.x = 1.6 * flip;
  }
}
