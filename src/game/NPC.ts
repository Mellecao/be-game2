import { Container, Sprite, Text, Assets, Graphics } from "pixi.js";
import { ASSETS } from "./constants";
import { isoToScreen } from "./iso";

export class NPC extends Container {
  public id: string;
  public displayName: string;
  public worldCol: number;
  public worldRow: number;

  private indicator!: Graphics;
  private indicatorBaseY = 0;
  private time = 0;

  private constructor(id: string, name: string, col: number, row: number) {
    super();
    this.id = id;
    this.displayName = name;
    this.worldCol = col;
    this.worldRow = row;
  }

  static async create(
    id: string,
    name: string,
    col: number,
    row: number
  ): Promise<NPC> {
    const n = new NPC(id, name, col, row);
    const tex = await Assets.load(ASSETS.npcFrontIdle);
    const shadowTex = await Assets.load(ASSETS.shadow);

    const shadow = new Sprite(shadowTex);
    shadow.anchor.set(0.5, 0.5);
    shadow.alpha = 0.45;
    shadow.y = 4;
    shadow.scale.set(1.1, 0.75);
    n.addChild(shadow);

    const sprite = new Sprite(tex);
    sprite.anchor.set(0.5, 1);
    sprite.scale.set(2.4);
    n.addChild(sprite);

    const label = new Text({
      text: name,
      style: {
        fontFamily: "Segoe UI",
        fontSize: 11,
        fill: 0xffffff,
        stroke: { color: 0x000000, width: 3 },
        fontWeight: "bold",
      },
    });
    label.anchor.set(0.5, 1);
    label.y = -sprite.height - 22;
    n.addChild(label);

    const indicator = new Graphics();
    indicator.circle(0, 0, 6).fill(0xffd700);
    indicator.circle(0, 0, 6).stroke({ color: 0x8b6f00, width: 1 });
    indicator.y = -sprite.height - 8;
    n.indicator = indicator;
    n.indicatorBaseY = indicator.y;
    n.addChild(indicator);

    n.eventMode = "static";
    n.cursor = "pointer";
    sprite.eventMode = "static";
    sprite.cursor = "pointer";

    n.syncScreen();
    return n;
  }

  update(dt: number) {
    this.time += dt * 0.05;
    this.indicator.y = this.indicatorBaseY + Math.sin(this.time) * 3;
  }

  syncScreen() {
    const p = isoToScreen(this.worldCol, this.worldRow);
    this.x = p.x;
    this.y = p.y;
  }
}
