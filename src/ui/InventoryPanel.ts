import { NitroFurniture } from "../game/NitroFurniture";

const MAX_PER_ITEM = 4;

const ITEMS = [
  { id: "sofa",   label: "Sofá" },
  { id: "chair",  label: "Cadeira" },
  { id: "desk",   label: "Mesa Gamer" },
  { id: "table",  label: "Mesa" },
  { id: "window", label: "Janela" },
];

export class InventoryPanel {
  private wrap: HTMLElement;
  private cards = new Map<string, { counter: HTMLElement; btn: HTMLButtonElement }>();

  constructor(
    private getFurniture: () => NitroFurniture[],
    private onSpawn: (itemId: string) => void
  ) {
    this.injectStyles();
    this.wrap = document.createElement("div");
    this.wrap.id = "inventory-panel";

    const title = document.createElement("div");
    title.className = "inv-title";
    title.textContent = "Inventário";
    this.wrap.appendChild(title);

    for (const item of ITEMS) {
      const card = document.createElement("div");
      card.className = "inv-card";

      const label = document.createElement("span");
      label.className = "inv-label";
      label.textContent = item.label;

      const counter = document.createElement("span");
      counter.className = "inv-count";
      counter.textContent = `0/${MAX_PER_ITEM}`;

      const btn = document.createElement("button");
      btn.className = "inv-btn";
      btn.textContent = "+";
      btn.addEventListener("click", () => {
        this.onSpawn(item.id);
        setTimeout(() => this.refresh(), 300);
      });

      card.appendChild(label);
      card.appendChild(counter);
      card.appendChild(btn);
      this.wrap.appendChild(card);
      this.cards.set(item.id, { counter, btn });
    }

    document.body.appendChild(this.wrap);
    this.hide();
  }

  show() {
    this.wrap.classList.remove("inv-hidden");
    this.refresh();
  }

  hide() {
    this.wrap.classList.add("inv-hidden");
  }

  refresh() {
    const list = this.getFurniture();
    for (const item of ITEMS) {
      const count = list.filter(
        (f) => (f.id === item.id || f.id.startsWith(item.id + "_")) && f.visible
      ).length;
      const refs = this.cards.get(item.id)!;
      refs.counter.textContent = `${count}/${MAX_PER_ITEM}`;
      refs.btn.disabled = count >= MAX_PER_ITEM;
    }
  }

  private injectStyles() {
    if (document.getElementById("inv-styles")) return;
    const style = document.createElement("style");
    style.id = "inv-styles";
    style.textContent = `
      #inventory-panel {
        position: fixed;
        top: 50%;
        right: 16px;
        transform: translateY(-50%);
        background: rgba(20,20,30,0.92);
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 8px;
        padding: 12px 10px;
        display: flex;
        flex-direction: column;
        gap: 8px;
        min-width: 160px;
        z-index: 100;
        font-family: "Segoe UI", sans-serif;
        color: #fff;
      }
      #inventory-panel.inv-hidden { display: none; }
      .inv-title {
        font-size: 13px;
        font-weight: bold;
        text-align: center;
        margin-bottom: 4px;
        color: #ffd700;
      }
      .inv-card {
        display: flex;
        align-items: center;
        gap: 8px;
        background: rgba(255,255,255,0.05);
        border-radius: 4px;
        padding: 6px 8px;
      }
      .inv-label { flex: 1; font-size: 12px; }
      .inv-count { font-size: 11px; color: #aaa; min-width: 28px; text-align: right; }
      .inv-btn {
        background: #3a8a3a;
        border: none;
        border-radius: 4px;
        color: #fff;
        font-size: 16px;
        width: 24px;
        height: 24px;
        cursor: pointer;
        line-height: 1;
        padding: 0;
      }
      .inv-btn:disabled { background: #555; cursor: not-allowed; }
      .inv-btn:not(:disabled):hover { background: #4caf50; }
    `;
    document.head.appendChild(style);
  }
}