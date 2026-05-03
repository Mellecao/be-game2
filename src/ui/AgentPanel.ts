export class AgentPanel {
  private toggleBtn: HTMLButtonElement;
  private active = false;

  constructor(private onToggle: (active: boolean) => void) {
    const wrap = document.createElement("div");
    wrap.id = "agent-panel";

    this.toggleBtn = document.createElement("button");
    this.toggleBtn.id = "agent-toggle";
    this.toggleBtn.textContent = "🧑‍💼 Agentes";
    this.toggleBtn.addEventListener("click", () => this.toggle());

    wrap.appendChild(this.toggleBtn);
    document.body.appendChild(wrap);
  }

  private toggle() {
    this.active = !this.active;
    this.toggleBtn.classList.toggle("bp-active", this.active);
    this.onToggle(this.active);
  }
}
