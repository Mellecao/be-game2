import { Container, Sprite, Texture, Assets, Text, TextStyle } from 'pixi.js'
import { isoToScreen } from '../game/iso'
import { RemotePlayerData } from './MultiplayerService'

type DirKey = 'front' | 'back' | 'side'

const LERP_FACTOR = 0.2
const WALK_FPS = 8
const IDLE_FPS = 4
const DIRS: DirKey[] = ['front', 'back', 'side']

const TINTS: Record<number, number> = {
  1: 0xffffff,
  2: 0x88ccff,
  3: 0x88ffaa,
  4: 0xffaa88,
}

export class RemotePlayer extends Container {
  private sprite!: Sprite
  private nameLabel!: Text
  private idleTextures: Record<DirKey, Texture[]> = { front: [], back: [], side: [] }
  private walkTextures: Record<DirKey, Texture[]> = { front: [], back: [], side: [] }

  private dirKey: DirKey = 'front'
  private flip = 1
  private moving = false

  private idleFrame: Record<DirKey, number> = { front: 0, back: 0, side: 0 }
  private idleTimer: Record<DirKey, number> = { front: 0, back: 0, side: 0 }
  private walkFrame: Record<DirKey, number> = { front: 0, back: 0, side: 0 }
  private walkTimer: Record<DirKey, number> = { front: 0, back: 0, side: 0 }

  worldCol = 0.5
  worldRow = 4.5
  private targetCol = 0.5
  private targetRow = 4.5

  static async load(data: RemotePlayerData): Promise<RemotePlayer> {
    const rp = new RemotePlayer()

    // Assets.load is cached by PixiJS — no cost if Player already loaded these files
    const [shadowTex, ...rest] = await Promise.all([
      Assets.load('/avatar/shadow.png'),
      ...[1, 2, 3, 4, 5].map((i) => Assets.load(`/avatar/front_${i}_iddle.png`)),
      ...[1, 2, 3, 4, 5].map((i) => Assets.load(`/avatar/back_${i}_iddle.png`)),
      ...[1, 2, 3, 4, 5].map((i) => Assets.load(`/avatar/side_${i}_iddle.png`)),
      ...[1, 2, 3, 4, 5].map((i) => Assets.load(`/avatar/front_${i}_walking.png`)),
      ...[1, 2, 3, 4, 5].map((i) => Assets.load(`/avatar/back_${i}_walking.png`)),
      ...[1, 2, 3, 4, 5].map((i) => Assets.load(`/avatar/side_${i}_walking.png`)),
    ])

    rp.idleTextures.front = rest.slice(0, 5)
    rp.idleTextures.back  = rest.slice(5, 10)
    rp.idleTextures.side  = rest.slice(10, 15)
    rp.walkTextures.front = rest.slice(15, 20)
    rp.walkTextures.back  = rest.slice(20, 25)
    rp.walkTextures.side  = rest.slice(25, 30)

    const shadow = new Sprite(shadowTex)
    shadow.anchor.set(0.5, 0.5)
    shadow.alpha = 0.45
    shadow.y = 4
    shadow.scale.set(1.1, 0.75)
    rp.addChild(shadow)

    rp.sprite = new Sprite(rp.idleTextures.front[0])
    rp.sprite.anchor.set(0.5, 1)
    rp.sprite.scale.set(2.64)
    rp.sprite.tint = TINTS[data.spriteChar] ?? 0xffffff
    rp.addChild(rp.sprite)

    rp.nameLabel = new Text({
      text: data.name,
      style: new TextStyle({
        fontSize: 12,
        fill: 0xffffff,
        fontFamily: 'monospace',
        stroke: { color: 0x000000, width: 3 },
      }),
    })
    rp.nameLabel.anchor.set(0.5, 1)
    rp.nameLabel.y = -(rp.sprite.height + 6)
    rp.addChild(rp.nameLabel)

    rp.syncScreen()
    return rp
  }

  setTarget(col: number, row: number, dir: string): void {
    this.targetCol = col
    this.targetRow = row
    switch (dir) {
      case 'front': this.dirKey = 'front'; this.flip =  1; break
      case 'back':  this.dirKey = 'back';  this.flip =  1; break
      case 'right': this.dirKey = 'side';  this.flip =  1; break
      case 'left':  this.dirKey = 'side';  this.flip = -1; break
    }
  }

  update(dt: number): void {
    const dCol = this.targetCol - this.worldCol
    const dRow = this.targetRow - this.worldRow
    this.moving = Math.hypot(dCol, dRow) > 0.05

    this.worldCol += dCol * LERP_FACTOR
    this.worldRow += dRow * LERP_FACTOR

    const idleTicks = 60 / IDLE_FPS
    const walkTicks = 60 / WALK_FPS
    for (const k of DIRS) {
      this.idleTimer[k] += dt
      if (this.idleTimer[k] >= idleTicks) {
        this.idleTimer[k] -= idleTicks
        this.idleFrame[k] = (this.idleFrame[k] + 1) % 5
      }
      this.walkTimer[k] += dt
      if (this.walkTimer[k] >= walkTicks) {
        this.walkTimer[k] -= walkTicks
        this.walkFrame[k] = (this.walkFrame[k] + 1) % 5
      }
    }

    this.sprite.texture = this.moving
      ? this.walkTextures[this.dirKey][this.walkFrame[this.dirKey]]
      : this.idleTextures[this.dirKey][this.idleFrame[this.dirKey]]
    this.sprite.scale.x = 2.64 * this.flip
    this.nameLabel.y = -(this.sprite.height + 6)

    this.syncScreen()
  }

  private syncScreen(): void {
    const pos = isoToScreen(this.worldCol, this.worldRow)
    this.x = pos.x
    this.y = pos.y
  }

  override destroy(): void {
    super.destroy({ children: true, texture: false, textureSource: false })
  }
}
