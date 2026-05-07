import { Container, Graphics, Text, Sprite, Texture } from 'pixi.js';

export type BubbleKind = 'say' | 'whisper' | 'player';

export interface SpeechBubbleOptions {
  agentName?: string;
  agentAvatar?: Texture;
  ttl?: number;
  maxWidth?: number;
}

const COLORS = {
  sayBg1: 0xfbbf24,
  sayBg2: 0xf59e0b,
  sayBorderInner: 0xffffff,
  sayBorderOuter: 0x92400e,
  whisperBg: 0xf3f4f6,
  whisperBorder: 0x9ca3af,
  whisperText: 0x374151,
  sayText: 0xffffff,
};

export class SpeechBubble extends Container {
  private bg = new Graphics();
  private avatar?: Sprite;
  private nameText?: Text;
  private bodyText: Text;
  private kind: BubbleKind;
  private maxWidth: number;

  constructor(text: string, kind: BubbleKind, opts: SpeechBubbleOptions = {}) {
    super();
    this.kind = kind;

    const isWhisper = kind === 'whisper';
    this.maxWidth = opts.maxWidth ?? (isWhisper ? 240 : 320);

    this.addChild(this.bg);

    if (!isWhisper && opts.agentAvatar) {
      this.avatar = new Sprite(opts.agentAvatar);
      this.avatar.width = 24;
      this.avatar.height = 24;
      this.avatar.x = 8;
      this.avatar.y = 6;
      const mask = new Graphics().circle(20, 18, 12).fill(0xffffff);
      this.avatar.mask = mask;
      this.addChild(this.avatar);
      this.addChild(mask);
    }

    if (!isWhisper && opts.agentName) {
      this.nameText = new Text({
        text: `${opts.agentName}:`,
        style: {
          fontFamily: 'system-ui',
          fontSize: 13,
          fontWeight: 'bold',
          fill: COLORS.sayText,
          wordWrap: false,
        },
      });
      this.nameText.x = (this.avatar ? 40 : 8);
      this.nameText.y = 8;
      this.addChild(this.nameText);
    }

    const textOffsetX = isWhisper ? 8 : (this.nameText ? this.nameText.x + this.nameText.width + 6 : 8);
    const textY = isWhisper ? 6 : 8;

    this.bodyText = new Text({
      text: this._truncateForWhisper(text, isWhisper),
      style: {
        fontFamily: 'system-ui',
        fontSize: isWhisper ? 12 : 13,
        fill: isWhisper ? COLORS.whisperText : COLORS.sayText,
        fontStyle: isWhisper ? 'italic' : 'normal',
        wordWrap: true,
        wordWrapWidth: this.maxWidth - textOffsetX - 8,
        breakWords: true,
        lineHeight: isWhisper ? 16 : 18,
      },
    });
    this.bodyText.x = textOffsetX;
    this.bodyText.y = textY;
    this.addChild(this.bodyText);

    this._drawBackground();
  }

  /** Atualiza texto in-place (usado pra whisper que muda conforme chunks). */
  updateText(text: string): void {
    this.bodyText.text = this._truncateForWhisper(text, this.kind === 'whisper');
    this._drawBackground();
  }

  /** Animação fade-out via direct alpha. */
  fadeOut(durationMs: number): Promise<void> {
    return new Promise((resolve) => {
      const start = performance.now();
      const startAlpha = this.alpha;
      const tick = () => {
        const elapsed = performance.now() - start;
        const t = Math.min(elapsed / durationMs, 1);
        this.alpha = startAlpha * (1 - t);
        if (t < 1) requestAnimationFrame(tick);
        else resolve();
      };
      requestAnimationFrame(tick);
    });
  }

  private _truncateForWhisper(text: string, isWhisper: boolean): string {
    if (!isWhisper) return text;
    const MAX_CHARS = 200;
    if (text.length <= MAX_CHARS) return text;
    return '…' + text.slice(-MAX_CHARS);
  }

  private _drawBackground(): void {
    const w = Math.min(this.bodyText.x + this.bodyText.width + 8, this.maxWidth);
    const h = Math.max(
      (this.bodyText.y + this.bodyText.height + 8),
      (this.avatar ? 36 : 24),
    );

    this.bg.clear();
    if (this.kind === 'whisper') {
      this.bg.roundRect(0, 0, w, h, 10).fill({ color: COLORS.whisperBg, alpha: 0.85 });
      this.bg.stroke({ color: COLORS.whisperBorder, width: 1 });
    } else {
      this.bg.roundRect(0, 0, w, h * 0.5, 14).fill(COLORS.sayBg1);
      this.bg.roundRect(0, h * 0.5, w, h * 0.5, 14).fill(COLORS.sayBg2);
      this.bg.roundRect(0, 0, w, h, 14).stroke({ color: COLORS.sayBorderOuter, width: 1 });
      this.bg.roundRect(2, 2, w - 4, h - 4, 12).stroke({ color: COLORS.sayBorderInner, width: 2 });
    }
  }
}
