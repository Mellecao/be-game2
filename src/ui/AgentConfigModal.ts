import { NPC } from "../game/NPC";

export class AgentConfigModal {
  private overlay: HTMLElement;
  private nameInput!: HTMLInputElement;
  private roleInput!: HTMLInputElement;
  private goalInput!: HTMLTextAreaElement;
  private backstoryInput!: HTMLTextAreaElement;
  private currentNpc: NPC | null = null;

  constructor() {
    this.injectStyles();
    this.overlay = document.createElement("div");
    this.overlay.id = "agent-modal-overlay";
    this.overlay.classList.add("acm-hidden");

    const modal = document.createElement("div");
    modal.id = "agent-modal";

    const title = document.createElement("div");
    title.className = "acm-title";
    title.textContent = "Configurar Agente";

    this.nameInput = this.makeInput("Nome");
    this.roleInput = this.makeInput("Role");
    this.goalInput = this.makeTextarea("Goal");
    this.backstoryInput = this.makeTextarea("Backstory");

    const btnRow = document.createElement("div");
    btnRow.className = "acm-btn-row";

    const saveBtn = document.createElement("button");
    saveBtn.className = "acm-btn acm-btn-save";
    saveBtn.textContent = "Salvar";
    saveBtn.addEventListener("click", () => this.save());

    const closeBtn = document.createElement("button");
    closeBtn.className = "acm-btn acm-btn-close";
    closeBtn.textContent = "Fechar";
    closeBtn.addEventListener("click", () => this.close());

    btnRow.appendChild(saveBtn);
    btnRow.appendChild(closeBtn);

    modal.appendChild(title);
    modal.appendChild(this.makeLabeledField("Nome", this.nameInput));
    modal.appendChild(this.makeLabeledField("Role", this.roleInput));
    modal.appendChild(this.makeLabeledField("Goal", this.goalInput));
    modal.appendChild(this.makeLabeledField("Backstory", this.backstoryInput));
    modal.appendChild(btnRow);

    this.overlay.appendChild(modal);
    document.body.appendChild(this.overlay);

    this.overlay.addEventListener("click", (e) => {
      if (e.target === this.overlay) this.close();
    });
  }

  open(npc: NPC) {
    this.currentNpc = npc;
    this.nameInput.value = npc.displayName;
    this.roleInput.value = npc.role;
    this.goalInput.value = npc.goal;
    this.backstoryInput.value = npc.backstory;
    this.overlay.classList.remove("acm-hidden");
  }

  close() {
    this.overlay.classList.add("acm-hidden");
    this.currentNpc = null;
  }

  private async save() {
    if (!this.currentNpc) return;
    const payload = {
      display_name: this.nameInput.value.trim(),
      role: this.roleInput.value.trim(),
      goal: this.goalInput.value.trim(),
      backstory: this.backstoryInput.value.trim(),
    };
    try {
      await fetch(`/api/agents/${this.currentNpc.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      this.currentNpc.role = payload.role;
      this.currentNpc.goal = payload.goal;
      this.currentNpc.backstory = payload.backstory;
      this.currentNpc.displayName = payload.display_name;
    } catch (err) {
      console.error("[AgentConfigModal] save failed", err);
    }
    this.close();
  }

  private makeInput(placeholder: string): HTMLInputElement {
    const input = document.createElement("input");
    input.type = "text";
    input.placeholder = placeholder;
    input.className = "acm-input";
    return input;
  }

  private makeTextarea(placeholder: string): HTMLTextAreaElement {
    const ta = document.createElement("textarea");
    ta.placeholder = placeholder;
    ta.className = "acm-textarea";
    ta.rows = 3;
    return ta;
  }

  private makeLabeledField(label: string, input: HTMLElement): HTMLElement {
    const wrap = document.createElement("div");
    wrap.className = "acm-field";
    const lbl = document.createElement("label");
    lbl.className = "acm-label";
    lbl.textContent = label;
    wrap.appendChild(lbl);
    wrap.appendChild(input);
    return wrap;
  }

  private injectStyles() {
    if (document.getElementById("acm-styles")) return;
    const style = document.createElement("style");
    style.id = "acm-styles";
    style.textContent = `
      #agent-modal-overlay {
        position: fixed;
        inset: 0;
        background: rgba(0,0,0,0.6);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 200;
      }
      #agent-modal-overlay.acm-hidden { display: none; }
      #agent-modal {
        background: rgba(20,20,30,0.97);
        border: 1px solid rgba(255,255,255,0.15);
        border-radius: 10px;
        padding: 24px 20px;
        min-width: 340px;
        max-width: 480px;
        width: 90%;
        display: flex;
        flex-direction: column;
        gap: 12px;
        font-family: "Segoe UI", sans-serif;
        color: #fff;
      }
      .acm-title {
        font-size: 15px;
        font-weight: bold;
        color: #ffd700;
        text-align: center;
        margin-bottom: 4px;
      }
      .acm-field { display: flex; flex-direction: column; gap: 4px; }
      .acm-label { font-size: 11px; color: #aaa; text-transform: uppercase; letter-spacing: 0.5px; }
      .acm-input, .acm-textarea {
        background: rgba(255,255,255,0.08);
        border: 1px solid rgba(255,255,255,0.15);
        border-radius: 6px;
        color: #fff;
        font-family: "Segoe UI", sans-serif;
        font-size: 13px;
        padding: 8px 10px;
        outline: none;
        resize: vertical;
      }
      .acm-input:focus, .acm-textarea:focus {
        border-color: rgba(255,215,0,0.5);
      }
      .acm-btn-row { display: flex; gap: 8px; justify-content: flex-end; margin-top: 4px; }
      .acm-btn {
        border: none;
        border-radius: 6px;
        padding: 8px 18px;
        font-size: 13px;
        cursor: pointer;
        font-family: "Segoe UI", sans-serif;
      }
      .acm-btn-save { background: #3a8a3a; color: #fff; }
      .acm-btn-save:hover { background: #4caf50; }
      .acm-btn-close { background: rgba(255,255,255,0.1); color: #ccc; }
      .acm-btn-close:hover { background: rgba(255,255,255,0.2); }
    `;
    document.head.appendChild(style);
  }
}
