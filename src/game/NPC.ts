import { Container, Sprite, Assets, Graphics, Texture } from "pixi.js";
import { ASSETS } from "./constants";
import { isoToScreen } from "./iso";
import { BubbleStack } from "./BubbleStack";

export interface AgentData {
  id: string;
  display_name: string;
  role: string;
  goal: string;
  backstory: string;
  col: number;
  row: number;
  sprite_char: number;
}

export class NPC extends Container {
  public id: string;
  public displayName: string;
  public role: string;
  public goal: string;
  public backstory: string;
  public worldCol: number;
  public worldRow: number;
  public isWorking = false;
  public bubbles!: BubbleStack;

  private indicator!: Graphics;
  private indicatorBaseY = 0;
  private time = 0;

  private constructor(id: string, name: string, col: number, row: number) {
    super();
    this.id = id;
    this.displayName = name;
    this.role = "";
    this.goal = "";
    this.backstory = "";
    this.worldCol = col;
    this.worldRow = row;
  }

  static async fromAgentData(data: AgentData): Promise<NPC> {
    const n = new NPC(data.id, data.display_name, data.col, data.row);
    n.role = data.role;
    n.goal = data.goal;
    n.backstory = data.backstory;

    const [tex, shadowTex] = await Promise.all([
      Assets.load(`/avatar/front_${data.sprite_char}_iddle.png`),
      Assets.load(ASSETS.shadow),
    ]);

    const shadow = new Sprite(shadowTex);
    shadow.anchor.set(0.5, 0.5);
    shadow.alpha = 0.45;
    shadow.y = 4;
    shadow.scale.set(1.1, 0.75);
    n.addChild(shadow);

    const sprite = new Sprite(tex);
    sprite.anchor.set(0.5, 1);
    sprite.scale.set(2.64);
    n.addChild(sprite);

    const indicator = new Graphics();
    indicator.circle(0, 0, 6).fill(0xffd700);
    indicator.circle(0, 0, 6).stroke({ color: 0x8b6f00, width: 1 });
    indicator.y = -sprite.height - 8;
    n.indicator = indicator;
    n.indicatorBaseY = indicator.y;
    n.addChild(indicator);

    n.bubbles = new BubbleStack(n);

    n.eventMode = "static";
    n.cursor = "pointer";
    sprite.eventMode = "static";
    sprite.cursor = "pointer";

    n.syncScreen();
    return n;
  }

  setWorking(active: boolean): void {
    this.isWorking = active;
    this.indicator.clear();
    const fill   = active ? 0x22c55e : 0xffd700;
    const stroke = active ? 0x166534 : 0x8b6f00;
    this.indicator.circle(0, 0, 6).fill(fill);
    this.indicator.circle(0, 0, 6).stroke({ color: stroke, width: 1 });
    if (!active) this.clearWhisper();
  }

  setWhisper(text: string): void {
    this.bubbles.setWhisper(text, this.displayName);
  }

  clearWhisper(): void {
    this.bubbles.clearWhisper();
  }

  pushSay(text: string, avatarTexture?: Texture): void {
    this.bubbles.pushSay(text, this.displayName, avatarTexture);
  }

  update(dt: number) {
    this.time += dt * 0.05;
    const floatY = this.indicatorBaseY + Math.sin(this.time) * 3;
    this.indicator.y = floatY;
  }

  syncScreen() {
    const p = isoToScreen(this.worldCol, this.worldRow);
    this.x = p.x;
    this.y = p.y;
  }
}
