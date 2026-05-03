import { Container, Sprite } from "pixi.js";
import { ISO_TILE_W, isoToScreen } from "./iso";
import { LAYER_LETTERS, NitroBundle, loadNitro, resolveAsset } from "./nitro";

export interface NitroFurnitureOptions {
  col: number;
  row: number;
  direction?: number;
  includeShadow?: boolean;
  frame?: number;
  yOffset?: number;
}

export class NitroFurniture extends Container {
  id = "";
  bundle!: NitroBundle;
  worldCol: number;
  worldRow: number;
  currentDirection: number = 2;
  validDirections: number[] = [0, 2, 4, 6];

  private yShift = 0;
  private includeShadow = true;
  private currentFrame = 0;

  private constructor(col: number, row: number) {
    super();
    this.worldCol = col;
    this.worldRow = row;
  }

  static async load(
    url: string,
    opts: NitroFurnitureOptions
  ): Promise<NitroFurniture> {
    const f = new NitroFurniture(opts.col, opts.row);
    f.yShift = opts.yOffset ?? 0;
    f.includeShadow = opts.includeShadow !== false;
    f.currentFrame = opts.frame ?? 0;
    f.currentDirection = opts.direction ?? 2;
    f.bundle = await loadNitro(url);
    f.recompose();
    f.syncScreen();
    return f;
  }

  moveTo(col: number, row: number) {
    this.worldCol = col;
    this.worldRow = row;
    this.syncScreen();
  }

  rotate() {
    const idx = this.validDirections.indexOf(this.currentDirection);
    this.currentDirection =
      this.validDirections[(idx + 1) % this.validDirections.length];
    this.recompose();
  }

  private recompose() {
    this.removeChildren();
    this.compose();
  }

  private compose() {
    const { manifest, spritesheet } = this.bundle;
    const direction = this.currentDirection;
    const frame = this.currentFrame;

    const viz =
      manifest.visualizations.find((v) => v.angle === 45) ??
      manifest.visualizations[0];

    const layerOverrides = viz.directions?.[String(direction)]?.layers ?? {};

    type LayerSpec = { sprite: Sprite; z: number };
    const layers: LayerSpec[] = [];

    if (this.includeShadow) {
      const shadowName = `${manifest.name}_64_sd_${direction}_${frame}`;
      const sd = resolveAsset(manifest, spritesheet, shadowName);
      if (sd) {
        const sp = this.makeSprite(sd);
        sp.alpha = 0.45;
        layers.push({ sprite: sp, z: -10000 });
      }
    }

    for (let li = 0; li < viz.layerCount; li++) {
      const letter = LAYER_LETTERS[li];
      const assetName = `${manifest.name}_64_${letter}_${direction}_${frame}`;
      const resolved = resolveAsset(manifest, spritesheet, assetName);
      if (!resolved) continue;

      const z =
        layerOverrides[String(li)]?.z ??
        viz.layers?.[String(li)]?.z ??
        li;

      const sp = this.makeSprite(resolved);
      layers.push({ sprite: sp, z });
    }

    layers.sort((a, b) => a.z - b.z);
    for (const { sprite } of layers) this.addChild(sprite);
  }

  private makeSprite(resolved: {
    texture: import("pixi.js").Texture;
    offsetX: number;
    offsetY: number;
    flipH: boolean;
  }): Sprite {
    const sp = new Sprite(resolved.texture);
    sp.anchor.set(0, 0);
    sp.x = ISO_TILE_W / 2 - resolved.offsetX;
    sp.y = -resolved.offsetY;
    if (resolved.flipH) {
      sp.scale.x = -1;
      sp.x += resolved.texture.width;
    }
    return sp;
  }

  private syncScreen() {
    const p = isoToScreen(this.worldCol, this.worldRow);
    this.x = p.x;
    this.y = p.y + this.yShift;
  }
}
