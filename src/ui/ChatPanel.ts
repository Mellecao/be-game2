import { sendChat } from "../api/agentApi";

interface NpcConfig {
  id: string;
  name: string;
  portraitUrl: string;
}

export class ChatPanel {
  private panel: HTMLElement;
  private messagesEl: HTMLElement;
  private formEl: HTMLFormElement;
  private inputEl: HTMLInputElement;
  private sendBtn: HTMLButtonElement;
  private closeBtn: HTMLButtonElement;
  private nameEl: HTMLElement;
  private portraitEl: HTMLImageElement;

  private currentNpc: NpcConfig | null = null;
  private busy = false;

  constructor() {
    this.panel = this.q("#chat-panel");
    this.messagesEl = this.q("#chat-messages");
    this.formEl = this.q("#chat-form") as HTMLFormElement;
    this.inputEl = this.q("#chat-input") as HTMLInputElement;
    this.sendBtn = this.q("#chat-send") as HTMLButtonElement;
    this.closeBtn = this.q("#chat-close") as HTMLButtonElement;
    this.nameEl = this.q("#chat-name");
    this.portraitEl = this.q("#chat-portrait") as HTMLImageElement;

    this.formEl.addEventListener("submit", (e) => this.handleSubmit(e));
    this.closeBtn.addEventListener("click", () => this.close());
  }

  private q<T extends HTMLElement>(sel: string): T {
    const el = document.querySelector<T>(sel);
    if (!el) throw new Error(`Elemento ${sel} nao encontrado`);
    return el;
  }

  open(npc: NpcConfig) {
    this.currentNpc = npc;
    this.nameEl.textContent = npc.name;
    this.portraitEl.src = npc.portraitUrl;
    this.portraitEl.alt = npc.name;
    if (this.messagesEl.childElementCount === 0) {
      this.addMessage(
        "assistant",
        `Oi! Sou o ${npc.name} da Black Elephant. Me passa um briefing ou pergunta o que precisar sobre copy de landing pages.`
      );
    }
    this.panel.classList.remove("hidden");
    setTimeout(() => this.inputEl.focus(), 50);
  }

  close() {
    this.panel.classList.add("hidden");
  }

  private async handleSubmit(e: Event) {
    e.preventDefault();
    if (this.busy || !this.currentNpc) return;

    const text = this.inputEl.value.trim();
    if (!text) return;

    this.addMessage("user", text);
    this.inputEl.value = "";
    this.setBusy(true);

    const typingEl = this.addMessage(
      "assistant",
      "Pensando... (Gemma 4 local pode levar 30-60s)",
      true
    );
    const startedAt = performance.now();
    const ticker = setInterval(() => {
      const sec = Math.floor((performance.now() - startedAt) / 1000);
      typingEl.textContent = `Pensando... ${sec}s (modelo local roda na sua maquina)`;
    }, 1000);

    try {
      const reply = await sendChat(this.currentNpc.id, text);
      clearInterval(ticker);
      typingEl.remove();
      this.addMessage("assistant", reply.response);
    } catch (err) {
      clearInterval(ticker);
      typingEl.remove();
      const msg = err instanceof Error ? err.message : String(err);
      this.addMessage("assistant", `Erro: ${msg}`);
    } finally {
      this.setBusy(false);
    }
  }

  private addMessage(role: "user" | "assistant", text: string, typing = false): HTMLElement {
    const el = document.createElement("div");
    el.className = `msg ${role}${typing ? " typing" : ""}`;
    el.textContent = text;
    this.messagesEl.appendChild(el);
    this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
    return el;
  }

  private setBusy(busy: boolean) {
    this.busy = busy;
    this.sendBtn.disabled = busy;
    this.inputEl.disabled = busy;
  }
}
