import { ChatWindow, AgentMessage } from './ChatWindow';

const AGENT_LABELS: Record<string, string> = {
  researcher: 'Researcher',
  copywriter: 'Copywriter',
  designer: 'Designer',
  image_artist: 'Image Artist',
  agente_3d: '3D Artist',
  designer_reviewer: 'Designer Reviewer',
  qa_code: 'QA Código',
  qa_visual: 'QA Visual',
  dev: 'Dev',
  devops: 'DevOps',
  planner: 'Planner',
  secretario: 'Secretário',
  bibliotecario: 'Bibliotecário',
};

const Z_BASE = 1100;

export class ChatWindowManager {
  private windows = new Map<string, ChatWindow>();
  private nextZ = Z_BASE;

  constructor() {
    window.addEventListener('chatwindow:close', (e: Event) => {
      const detail = (e as CustomEvent).detail;
      this.windows.delete(detail.agentId);
    });
    window.addEventListener('chatwindow:focus', (e: Event) => {
      const detail = (e as CustomEvent).detail;
      this.bringToFront(detail.agentId);
    });
  }

  open(agentId: string): ChatWindow {
    const existing = this.windows.get(agentId);
    if (existing) {
      this.bringToFront(agentId);
      return existing;
    }
    const label = AGENT_LABELS[agentId] ?? agentId;
    const win = new ChatWindow(agentId, label);
    win.setPosition(this._computePosition(agentId));
    win.setZIndex(this.nextZ++);
    win.loadHistory();
    this.windows.set(agentId, win);
    return win;
  }

  close(agentId: string): void {
    const w = this.windows.get(agentId);
    if (!w) return;
    w.destroy();
    this.windows.delete(agentId);
  }

  bringToFront(agentId: string): void {
    const w = this.windows.get(agentId);
    if (w) w.setZIndex(this.nextZ++);
  }

  appendMessage(agentId: string, msg: AgentMessage): void {
    const w = this.windows.get(agentId);
    if (w) w.appendMessage(msg);
  }

  private _computePosition(agentId: string): { left: number; top: number } {
    const stored = localStorage.getItem(`chat:${agentId}:pos`);
    if (stored) {
      try {
        return JSON.parse(stored);
      } catch {}
    }
    const count = this.windows.size;
    return { left: 80 + count * 30, top: 200 + count * 30 };
  }
}
