import { Container, Texture } from 'pixi.js';
import { SpeechBubble, BubbleKind } from './SpeechBubble';

const BASE_OFFSET = 40;
const GAP = 6;
const WHISPER_LOWER = 16;

export interface BubbleStackHost {
  addChild(child: Container): void;
  removeChild(child: Container): void;
}

export class BubbleStack {
  private container: Container;
  private stack: SpeechBubble[] = [];
  private whisperSlot: SpeechBubble | null = null;

  constructor(private host: BubbleStackHost) {
    this.container = new Container();
    host.addChild(this.container);
  }

  pushSay(text: string, agentName: string, agentAvatar: Texture | undefined, ttl?: number): void {
    this._push(text, 'say', { agentName, agentAvatar, ttl });
  }

  pushPlayer(text: string, playerAvatar: Texture | undefined, ttl?: number): void {
    this._push(text, 'player', { agentName: 'Você', agentAvatar: playerAvatar, ttl });
  }

  setWhisper(text: string, agentName?: string): void {
    if (this.whisperSlot) {
      this.whisperSlot.updateText(text);
    } else {
      this.whisperSlot = new SpeechBubble(text, 'whisper', { agentName });
      this.container.addChild(this.whisperSlot);
    }
    this._repositionWhisper();
  }

  clearWhisper(): void {
    if (!this.whisperSlot) return;
    const slot = this.whisperSlot;
    this.whisperSlot = null;
    slot.fadeOut(200).then(() => slot.destroy());
  }

  destroy(): void {
    for (const b of this.stack) b.destroy();
    this.whisperSlot?.destroy();
    this.container.destroy({ children: true });
  }

  private _push(text: string, kind: BubbleKind, opts: { agentName?: string; agentAvatar?: Texture; ttl?: number }): void {
    const bubble = new SpeechBubble(text, kind, opts);
    this.container.addChild(bubble);
    bubble.y = -BASE_OFFSET;

    for (const existing of this.stack) {
      const targetY = existing.y - (bubble.height + GAP);
      this._tweenY(existing, targetY, 150);
    }
    this.stack.push(bubble);

    if (this.whisperSlot) this.clearWhisper();
    this._repositionWhisper();

    const computedTtl = opts.ttl ?? Math.min(2000 + text.length * 60, 8000);
    setTimeout(() => this._removeBubble(bubble), computedTtl);
  }

  private _repositionWhisper(): void {
    if (!this.whisperSlot) return;
    let stackBottom = -BASE_OFFSET;
    for (const b of this.stack) stackBottom = Math.min(stackBottom, b.y);
    this.whisperSlot.y = stackBottom + WHISPER_LOWER + this.whisperSlot.height;
  }

  private _removeBubble(bubble: SpeechBubble): void {
    bubble.fadeOut(300).then(() => {
      bubble.destroy();
      this.stack = this.stack.filter((b) => b !== bubble);
    });
  }

  private _tweenY(target: SpeechBubble, toY: number, durationMs: number): void {
    const fromY = target.y;
    const start = performance.now();
    const tick = () => {
      const elapsed = performance.now() - start;
      const t = Math.min(elapsed / durationMs, 1);
      const eased = 1 - Math.pow(1 - t, 2);
      target.y = fromY + (toY - fromY) * eased;
      if (t < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }
}
