export class BuildingPanel {
  private wrap: HTMLElement;
  private toggleBtn: HTMLButtonElement;
  private saveBtn: HTMLButtonElement;
  private removeWallsBtn: HTMLButtonElement;
  private active = false;
  private removeWallsActive = false;

  constructor(
    private onToggle: (active: boolean) => void,
    private onSave: () => Promise<void>,
    private onRemoveWalls: (active: boolean) => void
  ) {
    this.wrap = document.createElement("div");
    this.wrap.id = "building-panel";

    this.toggleBtn = this.makeBtn("building-toggle", "🔨 Building", () =>
      this.toggle()
    );
    this.saveBtn = this.makeBtn("building-save", "💾 Save", () => this.save());
    this.removeWallsBtn = this.makeBtn(
      "building-remove-walls",
      "🗑️ Remove Walls",
      () => this.toggleRemoveWalls()
    );

    this.saveBtn.classList.add("bp-hidden");
    this.removeWallsBtn.classList.add("bp-hidden");

    this.wrap.appendChild(this.toggleBtn);
    this.wrap.appendChild(this.saveBtn);
    this.wrap.appendChild(this.removeWallsBtn);
    document.body.appendChild(this.wrap);
  }

  private makeBtn(
    id: string,
    label: string,
    onClick: () => void
  ): HTMLButtonElement {
    const btn = document.createElement("button");
    btn.id = id;
    btn.textContent = label;
    btn.addEventListener("click", onClick);
    return btn;
  }

  private toggle() {
    this.active = !this.active;
    this.toggleBtn.classList.toggle("bp-active", this.active);
    this.saveBtn.classList.toggle("bp-hidden", !this.active);
    this.removeWallsBtn.classList.toggle("bp-hidden", !this.active);
    if (!this.active) {
      this.removeWallsActive = false;
      this.removeWallsBtn.classList.remove("bp-active");
      this.onRemoveWalls(false);
    }
    this.onToggle(this.active);
  }

  private async save() {
    this.saveBtn.disabled = true;
    this.saveBtn.textContent = "💾 Saving…";
    try {
      await this.onSave();
      this.saveBtn.textContent = "✅ Saved!";
    } catch (err) {
      console.error("[save]", err);
      this.saveBtn.textContent = "❌ Error";
    }
    setTimeout(() => {
      this.saveBtn.textContent = "💾 Save";
      this.saveBtn.disabled = false;
    }, 1600);
  }

  private toggleRemoveWalls() {
    this.removeWallsActive = !this.removeWallsActive;
    this.removeWallsBtn.classList.toggle("bp-active", this.removeWallsActive);
    this.onRemoveWalls(this.removeWallsActive);
  }
}
