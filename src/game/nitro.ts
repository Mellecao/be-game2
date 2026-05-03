import { Spritesheet, Texture } from "pixi.js";
import { inflate } from "pako";

// .nitro file format:
//   uint16 (BE)  count
//   per entry:
//     uint16 (BE)  filename length
//     bytes        filename (utf-8)
//     uint32 (BE)  zlib-compressed length
//     bytes        zlib-compressed payload
// Each bundle ships a JSON manifest + a PNG spritesheet.

export interface NitroAsset {
  x: number;
  y: number;
  source?: string;
  flipH?: boolean;
}

export interface NitroVisualizationLayer {
  z?: number;
  ink?: number;
  alpha?: number;
  ignoreMouse?: boolean;
}

export interface NitroVisualizationDirection {
  layers?: Record<string, NitroVisualizationLayer>;
}

export interface NitroVisualization {
  size: number;
  layerCount: number;
  angle: number;
  layers?: Record<string, NitroVisualizationLayer>;
  directions?: Record<string, NitroVisualizationDirection>;
}

export interface NitroManifest {
  name: string;
  logicType: string;
  visualizationType: string;
  assets: Record<string, NitroAsset>;
  logic?: {
    model?: {
      dimensions?: { x: number; y: number; z: number };
      directions?: number[];
    };
  };
  visualizations: NitroVisualization[];
  spritesheet: {
    frames: Record<
      string,
      {
        frame: { x: number; y: number; w: number; h: number };
        rotated: boolean;
        trimmed: boolean;
        spriteSourceSize: { x: number; y: number; w: number; h: number };
        sourceSize: { w: number; h: number };
        pivot: { x: number; y: number };
      }
    >;
    meta: {
      image: string;
      format: string;
      size: { w: number; h: number };
      scale: number;
    };
  };
}

export interface NitroBundle {
  manifest: NitroManifest;
  spritesheet: Spritesheet;
}

function readU16BE(buf: Uint8Array, pos: number): number {
  return (buf[pos] << 8) | buf[pos + 1];
}
function readU32BE(buf: Uint8Array, pos: number): number {
  return (
    (buf[pos] * 0x1000000) +
    ((buf[pos + 1] << 16) | (buf[pos + 2] << 8) | buf[pos + 3])
  );
}

async function fetchBundle(url: string): Promise<Map<string, Uint8Array>> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch ${url}: ${res.status}`);
  const buf = new Uint8Array(await res.arrayBuffer());
  const out = new Map<string, Uint8Array>();
  let pos = 0;
  const count = readU16BE(buf, pos); pos += 2;
  for (let i = 0; i < count; i++) {
    const nameLen = readU16BE(buf, pos); pos += 2;
    const name = new TextDecoder("utf-8").decode(buf.subarray(pos, pos + nameLen));
    pos += nameLen;
    const dataLen = readU32BE(buf, pos); pos += 4;
    const compressed = buf.subarray(pos, pos + dataLen);
    pos += dataLen;
    const data = inflate(compressed);
    out.set(name, data);
  }
  return out;
}

const bundleCache = new Map<string, Promise<NitroBundle>>();

export function loadNitro(url: string): Promise<NitroBundle> {
  if (!bundleCache.has(url)) bundleCache.set(url, _loadNitro(url));
  return bundleCache.get(url)!;
}

async function _loadNitro(url: string): Promise<NitroBundle> {
  const files = await fetchBundle(url);
  const jsonName = [...files.keys()].find((n) => n.endsWith(".json"));
  const pngName = [...files.keys()].find((n) => n.endsWith(".png"));
  if (!jsonName || !pngName) {
    throw new Error(`Nitro bundle ${url} is missing .json or .png`);
  }
  const manifest = JSON.parse(
    new TextDecoder("utf-8").decode(files.get(jsonName)!)
  ) as NitroManifest;

  // Build a blob URL for the PNG and load it through Pixi's asset system so
  // the texture is properly tracked.
  const pngBytes = files.get(pngName)!;
  const pngBuf = pngBytes.slice().buffer as ArrayBuffer;
  const pngBlob = new Blob([pngBuf], { type: "image/png" });
  const pngUrl = URL.createObjectURL(pngBlob);

  const img = new Image();
  await new Promise<void>((resolve, reject) => {
    img.onload = () => resolve();
    img.onerror = () => reject(new Error(`Failed to decode PNG in ${url}`));
    img.src = pngUrl;
  });

  const texture = Texture.from(img);
  if (!texture || !texture.source) {
    throw new Error(`Texture.from(img) returned no source for ${url}`);
  }
  texture.source.scaleMode = "nearest";

  const sheet = new Spritesheet(texture, manifest.spritesheet);
  await sheet.parse();

  return { manifest, spritesheet: sheet };
}

// Resolve an asset name (which may have `source` indirection + flipH) and
// return the underlying frame texture plus a flip flag.
export function resolveAsset(
  manifest: NitroManifest,
  sheet: Spritesheet,
  assetName: string
): { texture: Texture; offsetX: number; offsetY: number; flipH: boolean } | null {
  const asset = manifest.assets[assetName];
  if (!asset) return null;
  const realName = asset.source ?? assetName;
  const frameKey = `${manifest.name}_${realName}`;
  const tex = sheet.textures[frameKey];
  if (!tex) return null;
  return {
    texture: tex,
    offsetX: asset.x,
    offsetY: asset.y,
    flipH: !!asset.flipH,
  };
}

// Letter sequence used by Habbo for layers: a,b,c,d,e,...
export const LAYER_LETTERS = "abcdefghijklmnopqrstuvwxyz";
