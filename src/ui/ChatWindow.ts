export interface AgentMessage {
  id?: number;
  type: 'whisper' | 'say' | 'player' | 'reply';
  text: string;
  ts: number;
  slug?: string;
}

const INPUT_ENABLED_AGENTS = new Set(['secretario', 'bibliotecario']);

export class ChatWindow {
  el: HTMLDivElement;
  private body: HTMLDivElement;
  private input: HTMLInputElement | null = null;
  private dragOffset: { x: number; y: number } | null = null;

  constructor(public agentId: string, private agentLabel: string) {
    this.el = document.createElement('div');
    this.el.className = 'chat-window';
    this.el.dataset.agentId = agentId;

    this.el.innerHTML = `
      <div class="chat-header" data-drag-handle>
        <img class="chat-avatar" alt="" />
        <span class="chat-title">${escapeHtml(agentLabel)}</span>
        <button class="chat-close" aria-label="Fechar">×</button>
      </div>
      <div class="chat-body"></div>
      ${INPUT_ENABLED_AGENTS.has(agentId) ? `
        <div class="chat-input-area">
          <input type="text" placeholder="Pergunte..." maxlength="500" />
        </div>
      ` : ''}
    `;

    this.body = this.el.querySelector('.chat-body')!;
    this.input = this.el.querySelector<HTMLInputElement>('.chat-input-area input');

    this._wireEvents();
    document.body.appendChild(this.el);
  }

  setPosition(pos: { left: number; top: number }): void {
    this.el.style.left = `${pos.left}px`;
    this.el.style.top = `${pos.top}px`;
  }

  setZIndex(z: number): void {
    this.el.style.zIndex = String(z);
  }

  async loadHistory(): Promise<void> {
    try {
      const r = await fetch(`/api/agents/${this.agentId}/messages?limit=200`);
      const data = await r.json();
      for (const m of data.messages || []) this.appendMessage(m);
    } catch (err) {
      console.error('chat history load failed', err);
    }
  }

  appendMessage(msg: AgentMessage): void {
    const div = document.createElement('div');
    div.className = `msg msg-${msg.type}`;
    const time = new Date(msg.ts * 1000).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    if (msg.type === 'say' || msg.type === 'reply') {
      div.innerHTML = `<b>${escapeHtml(this.agentLabel)}:</b> ${escapeHtml(msg.text)} <span class="msg-time">[${time}]</span>`;
    } else if (msg.type === 'player') {
      div.innerHTML = `<b>Você:</b> ${escapeHtml(msg.text)} <span class="msg-time">[${time}]</span>`;
    } else {
      div.innerHTML = `${escapeHtml(msg.text)} <span class="msg-time">[${time}]</span>`;
    }
    this.body.appendChild(div);
    this.body.scrollTop = this.body.scrollHeight;
  }

  destroy(): void {
    this.el.remove();
  }

  private _wireEvents(): void {
    const close = this.el.querySelector('.chat-close')!;
    close.addEventListener('click', () => {
      this.destroy();
      this._savePosition();
      const event = new CustomEvent('chatwindow:close', { detail: { agentId: this.agentId } });
      window.dispatchEvent(event);
    });

    const handle = this.el.querySelector<HTMLElement>('[data-drag-handle]')!;
    handle.addEventListener('mousedown', (e) => {
      const rect = this.el.getBoundingClientRect();
      this.dragOffset = { x: e.clientX - rect.left, y: e.clientY - rect.top };
      document.addEventListener('mousemove', this._onMouseMove);
      document.addEventListener('mouseup', this._onMouseUp);
    });

    this.el.addEventListener('click', () => {
      const event = new CustomEvent('chatwindow:focus', { detail: { agentId: this.agentId } });
      window.dispatchEvent(event);
    });

    if (this.input) {
      this.input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          const text = this.input!.value.trim();
          if (!text) return;
          this._submitMessage(text);
          this.input!.value = '';
        }
      });
    }
  }

  private _onMouseMove = (e: MouseEvent) => {
    if (!this.dragOffset) return;
    this.el.style.left = `${e.clientX - this.dragOffset.x}px`;
    this.el.style.top = `${e.clientY - this.dragOffset.y}px`;
  };

  private _onMouseUp = () => {
    this.dragOffset = null;
    document.removeEventListener('mousemove', this._onMouseMove);
    document.removeEventListener('mouseup', this._onMouseUp);
    this._savePosition();
  };

  private _savePosition(): void {
    const r = this.el.getBoundingClientRect();
    localStorage.setItem(`chat:${this.agentId}:pos`, JSON.stringify({ left: r.left, top: r.top }));
  }

  private async _submitMessage(text: string): Promise<void> {
    try {
      const r = await fetch(`/api/chat/${this.agentId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      });
      if (!r.ok) console.error('chat submit failed', r.status);
    } catch (err) {
      console.error('chat submit error', err);
    }
  }
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[c]!);
}
