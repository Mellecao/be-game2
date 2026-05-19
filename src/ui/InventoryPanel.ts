import { NitroFurniture } from "../game/NitroFurniture";

const MAX_PER_ITEM = 4;

const ITEMS: { id: string; label: string; icon: string }[] = [
  // originais (sem arquivo _icon.png)
  { id: "sofa",          label: "Sofá",          icon: "🛋️" },
  { id: "chair",         label: "Cadeira",        icon: "🪑" },
  { id: "desk",          label: "Mesa Gamer",     icon: "🖥️" },
  { id: "table",         label: "Mesa",           icon: "🪵" },
  { id: "window",        label: "Janela",         icon: "🪟" },
  { id: "plant",         label: "Planta",         icon: "🌿" },
  // novos (com ícone PNG do zip)
  { id: "deskcomp",      label: "Computador",     icon: "/army_c15_deskcomp_1778690424/army_c15_deskcomp_icon.png" },
  { id: "leatherchr",    label: "Cad. Couro",     icon: "/army_c15_leatherchr_1778690400/army_c15_leatherchr_icon.png" },
  { id: "officetent",    label: "Tenda",          icon: "/army_c15_officetent_1778690315/army_c15_officetent_icon.png" },
  { id: "armyplant",     label: "Planta Army",    icon: "/army_c15_plant_1778690335/army_c15_plant_icon.png" },
  { id: "tie",           label: "Gravata",        icon: "/clothing_tie1_1778690313/clothing_tie1_icon.png" },
  { id: "flatscreen",    label: "Monitor",        icon: "/computer_flatscreen_1778690427/computer_flatscreen_icon.png" },
  { id: "laptop",        label: "Laptop",         icon: "/computer_laptop_1778690419/computer_laptop_icon.png" },
  { id: "oldcomputer",   label: "PC Antigo",      icon: "/computer_old_1778690435/computer_old_icon.png" },
  { id: "eastertable",   label: "Mesa Easter",    icon: "/easter14_table_1778690446/easter14_table_icon.png" },
  { id: "printer",       label: "Impressora",     icon: "/exe_c15_printer_1778690397/exe_c15_printer_icon.png" },
  { id: "exewall",       label: "Parede",         icon: "/exe_c15_wall_1778690389/exe_c15_wall_icon.png" },
  { id: "drinkscabinet", label: "Bar",            icon: "/exe_drinks_cabinet_1778690403/exe_drinks_cabinet_icon.png" },
  { id: "glassdivider",  label: "Divisória",      icon: "/exe_glassdvdr_1778690405/exe_glassdvdr_icon.png" },
  { id: "globe",         label: "Globo",          icon: "/exe_globe_1778690408/exe_globe_icon.png" },
  { id: "exeplant",      label: "Planta Exe",     icon: "/exe_plant_1778690332/exe_plant_icon.png" },
  { id: "rug",           label: "Tapete",         icon: "/exe_rug_1778690416/exe_rug_icon.png" },
  { id: "exetable",      label: "Mesa Exe",       icon: "/exe_table_1778690167/exe_table_icon.png" },
  { id: "execchair",     label: "Cad. Exec",      icon: "/hc_exe_chair_1778690353/hc_exe_chair_icon.png" },
  { id: "execchair2",    label: "Cad. Exec 2",    icon: "/hc_exe_chair2_1778690340/hc_exe_chair2_icon.png" },
  { id: "cubelight",     label: "Luminária",      icon: "/hc_exe_cubelight_1778690378/hc_exe_cubelight_icon.png" },
  { id: "elevator",      label: "Elevador",       icon: "/hc_exe_elevator_1778690383/hc_exe_elevator_icon.png" },
  { id: "hcglasdvdr",    label: "Divis. HC",      icon: "/hc_exe_glassdvdr_1778690361/hc_exe_glassdvdr_icon.png" },
  { id: "exelight",      label: "Abajur",         icon: "/hc_exe_light_1778690364/hc_exe_light_icon.png" },
  { id: "exesmalltable", label: "Mesa Lateral",   icon: "/hc_exe_s_table_1778690359/hc_exe_s_table_icon.png" },
  { id: "seccam",        label: "Câmera Seg.",    icon: "/hc_exe_seccam_1778690381/hc_exe_seccam_icon.png" },
  { id: "exesofa",       label: "Sofá Exe",       icon: "/hc_exe_sofa_1778690356/hc_exe_sofa_icon.png" },
  { id: "exebigtable",   label: "Mesa Grande",    icon: "/hc_exe_table_1778690343/hc_exe_table_icon.png" },
  { id: "waterfall",     label: "Cascata",        icon: "/hc_exe_wfall_1778690386/hc_exe_wfall_icon.png" },
  { id: "workdesk",      label: "Mesa Trab.",     icon: "/hc_exe_wrkdesk_1778690337/hc_exe_wrkdesk_icon.png" },
  { id: "hc21",          label: "HC21",           icon: "/hc21_10_1778690440/hc21_10_icon.png" },
  { id: "exenewsofa",    label: "Sofá Novo",      icon: "/house_sofa_1778690307/house_sofa_icon.png" },
  { id: "labmachine",    label: "Máq. Lab",       icon: "/hween_c18_labmchn3_1778690443/hween_c18_labmchn3_icon.png" },
  { id: "laptopdesk",    label: "Mesa Laptop",    icon: "/laptopdesk_1778690421/laptopdesk_icon.png" },
  { id: "newchair",      label: "Cad. Nova",      icon: "/waasa_chair_1778690438/waasa_chair_icon.png" },
  { id: "xmasdeskitems", label: "Itens Natal",    icon: "/xmas_c16_deskitems_1778690310/xmas_c16_deskitems_icon.png" },
];

export class InventoryPanel {
  private wrap: HTMLElement;
  private cards = new Map<
    string,
    { counter: HTMLElement; addBtn: HTMLButtonElement; removeBtn: HTMLButtonElement; card: HTMLElement }
  >();
  private searchInput!: HTMLInputElement;
  private gridEl!: HTMLElement;

  constructor(
    private getFurniture: () => NitroFurniture[],
    private onSpawn: (itemId: string) => void,
    private onRemove: (itemId: string) => void
  ) {
    this.injectFonts();
    this.injectStyles();

    this.wrap = document.createElement("div");
    this.wrap.id = "inventory-panel";

    this.wrap.appendChild(this.buildHeader());
    this.wrap.appendChild(this.buildSearch());

    this.gridEl = document.createElement("div");
    this.gridEl.className = "inv-grid";
    for (const item of ITEMS) this.gridEl.appendChild(this.makeCard(item));
    this.wrap.appendChild(this.gridEl);

    document.body.appendChild(this.wrap);
    this.hide();
  }

  // ── public ────────────────────────────────────────────────────────────────

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
      refs.addBtn.disabled = count >= MAX_PER_ITEM;
      refs.removeBtn.disabled = count === 0;
    }
  }

  // ── private builders ───────────────────────────────────────────────────────

  private buildHeader(): HTMLElement {
    const header = document.createElement("div");
    header.className = "inv-header";

    const chest = document.createElement("span");
    chest.className = "inv-header-icon";
    chest.textContent = "📦";

    const title = document.createElement("span");
    title.className = "inv-title";
    title.textContent = "INVENTÁRIO";

    header.appendChild(chest);
    header.appendChild(title);
    return header;
  }

  private buildSearch(): HTMLElement {
    const wrap = document.createElement("div");
    wrap.className = "inv-search-wrap";

    const icon = document.createElement("span");
    icon.className = "inv-search-icon";
    icon.textContent = "🔍";

    this.searchInput = document.createElement("input");
    this.searchInput.type = "text";
    this.searchInput.className = "inv-search";
    this.searchInput.placeholder = "PESQUISAR...";
    this.searchInput.addEventListener("input", () => this.applyFilter());

    wrap.appendChild(icon);
    wrap.appendChild(this.searchInput);
    return wrap;
  }

  private makeCard(item: (typeof ITEMS)[0]): HTMLElement {
    const card = document.createElement("div");
    card.className = "inv-card";
    card.dataset.label = item.label.toLowerCase();
    card.dataset.id = item.id;

    // icon
    const iconBox = document.createElement("div");
    iconBox.className = "inv-icon-box";
    if (item.icon.startsWith("/")) {
      const img = document.createElement("img");
      img.src = item.icon;
      img.alt = item.label;
      img.className = "inv-icon-img";
      iconBox.appendChild(img);
    } else {
      iconBox.classList.add("inv-icon-emoji");
      iconBox.textContent = item.icon;
    }
    card.appendChild(iconBox);

    // label (middle, flex-grows)
    const label = document.createElement("div");
    label.className = "inv-label";
    label.textContent = item.label;
    card.appendChild(label);

    // right side: counter + buttons
    const controls = document.createElement("div");
    controls.className = "inv-controls";

    const removeBtn = document.createElement("button");
    removeBtn.className = "inv-btn inv-btn-remove";
    removeBtn.textContent = "−";
    removeBtn.title = "Remover";
    removeBtn.disabled = true;
    removeBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      this.onRemove(item.id);
      setTimeout(() => this.refresh(), 50);
    });

    const counter = document.createElement("span");
    counter.className = "inv-count";
    counter.textContent = `0/${MAX_PER_ITEM}`;

    const addBtn = document.createElement("button");
    addBtn.className = "inv-btn inv-btn-add";
    addBtn.textContent = "+";
    addBtn.title = "Adicionar";
    addBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      this.onSpawn(item.id);
      setTimeout(() => this.refresh(), 300);
    });

    controls.appendChild(removeBtn);
    controls.appendChild(counter);
    controls.appendChild(addBtn);
    card.appendChild(controls);

    // clicking the card body (icon / label) also adds the item
    card.addEventListener("click", () => {
      if (!addBtn.disabled) {
        this.onSpawn(item.id);
        setTimeout(() => this.refresh(), 300);
      }
    });

    this.cards.set(item.id, { counter, addBtn, removeBtn, card });
    return card;
  }

  private applyFilter() {
    const q = this.searchInput.value.toLowerCase().trim();
    for (const child of this.gridEl.children) {
      const el = child as HTMLElement;
      const match = !q
        || el.dataset.label?.includes(q)
        || el.dataset.id?.includes(q);
      el.style.display = match ? "" : "none";
    }
  }

  // ── styles ─────────────────────────────────────────────────────────────────

  private injectFonts() {
    if (document.getElementById("inv-fonts")) return;
    const link = document.createElement("link");
    link.id = "inv-fonts";
    link.rel = "stylesheet";
    link.href = "https://fonts.googleapis.com/css2?family=VT323&family=Press+Start+2P&display=swap";
    document.head.appendChild(link);
  }

  private injectStyles() {
    if (document.getElementById("inv-styles")) return;
    const style = document.createElement("style");
    style.id = "inv-styles";
    style.textContent = `
      /* ── Inventory Panel ── */
      #inventory-panel {
        position: fixed;
        top: 0;
        right: 0;
        width: 270px;
        height: 100vh;
        background: #08080f;
        border-left: 3px solid #b89000;
        box-shadow:
          inset 0 0 0 2px #0a0a0f,
          inset -3px 0 0 #4a3800,
          -6px 0 32px rgba(0,0,0,0.85);
        display: flex;
        flex-direction: column;
        z-index: 100;
        font-family: 'VT323', monospace;
        image-rendering: pixelated;
      }
      #inventory-panel.inv-hidden { display: none; }

      /* ── Header ── */
      .inv-header {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 14px 16px 12px;
        background: #0c0c1c;
        border-bottom: 3px solid #b89000;
        box-shadow: 0 3px 0 #3a2800;
        flex-shrink: 0;
      }
      .inv-header-icon {
        font-size: 20px;
        line-height: 1;
      }
      .inv-title {
        font-family: 'Press Start 2P', monospace;
        font-size: 9px;
        color: #f0d050;
        letter-spacing: 0.12em;
        text-shadow: 2px 2px 0 #6a4800, 0 0 16px rgba(240,200,60,0.5);
        flex: 1;
      }

      /* ── Search ── */
      .inv-search-wrap {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 8px 10px;
        background: #0a0a16;
        border-bottom: 2px solid #2a1e00;
        flex-shrink: 0;
      }
      .inv-search-icon {
        font-size: 16px;
        flex-shrink: 0;
        line-height: 1;
      }
      .inv-search {
        flex: 1;
        padding: 6px 8px;
        background: #040408;
        border: 2px solid #6a4e00;
        color: #f0d050;
        font-family: 'VT323', monospace;
        font-size: 18px;
        letter-spacing: 0.05em;
        outline: none;
        width: 0;
        box-shadow: inset 2px 2px 0 #1a1000;
      }
      .inv-search::placeholder { color: #4a3800; }
      .inv-search:focus {
        border-color: #f0c000;
        box-shadow: inset 2px 2px 0 #1a1000, 0 0 8px rgba(240,192,0,0.25);
      }

      /* ── List ── */
      .inv-grid {
        flex: 1;
        overflow-y: auto;
        padding: 6px;
        display: flex;
        flex-direction: column;
        gap: 4px;
        scrollbar-width: thin;
        scrollbar-color: #b89000 #08080f;
      }
      .inv-grid::-webkit-scrollbar { width: 5px; }
      .inv-grid::-webkit-scrollbar-track { background: #08080f; }
      .inv-grid::-webkit-scrollbar-thumb { background: #b89000; }

      /* ── Card (horizontal row) ── */
      .inv-card {
        background: #0d0d20;
        border: 2px solid #2a1e00;
        display: flex;
        flex-direction: row;
        align-items: center;
        gap: 8px;
        padding: 5px 7px 5px 5px;
        cursor: pointer;
        transition: border-color 0.1s, background 0.1s;
        position: relative;
        overflow: hidden;
        flex-shrink: 0;
      }
      .inv-card::before {
        content: '';
        position: absolute;
        inset: 0;
        background: repeating-linear-gradient(
          0deg,
          transparent,
          transparent 3px,
          rgba(0,0,0,0.07) 3px,
          rgba(0,0,0,0.07) 4px
        );
        pointer-events: none;
      }
      .inv-card:hover {
        border-color: #d4a800;
        background: #111128;
      }
      .inv-card:active { background: #0a0a18; }

      /* ── Icon box ── */
      .inv-icon-box {
        width: 40px;
        height: 40px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #040408;
        border: 2px solid #1c1600;
        flex-shrink: 0;
      }
      .inv-icon-img {
        width: 36px;
        height: 36px;
        image-rendering: pixelated;
        object-fit: contain;
      }
      .inv-icon-emoji {
        font-size: 22px;
        line-height: 1;
      }

      /* ── Label ── */
      .inv-label {
        font-family: 'VT323', monospace;
        font-size: 17px;
        color: #d4a800;
        line-height: 1;
        flex: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        letter-spacing: 0.03em;
      }

      /* ── Controls (counter + buttons) ── */
      .inv-controls {
        display: flex;
        align-items: center;
        gap: 4px;
        flex-shrink: 0;
      }
      .inv-count {
        font-family: 'VT323', monospace;
        font-size: 16px;
        color: #555;
        min-width: 28px;
        text-align: center;
      }

      /* ── Buttons ── */
      .inv-btn {
        width: 24px;
        height: 24px;
        border: 2px solid;
        font-size: 18px;
        font-family: 'VT323', monospace;
        line-height: 1;
        cursor: pointer;
        padding: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: background 0.08s, box-shadow 0.08s;
        flex-shrink: 0;
      }
      .inv-btn-add {
        border-color: #2a7000;
        background: #061400;
        color: #50d000;
      }
      .inv-btn-add:not(:disabled):hover {
        background: #0d2800;
        border-color: #50d000;
        box-shadow: 0 0 6px rgba(80,208,0,0.5);
      }
      .inv-btn-remove {
        border-color: #700000;
        background: #140000;
        color: #d05050;
      }
      .inv-btn-remove:not(:disabled):hover {
        background: #2a0000;
        border-color: #d05050;
        box-shadow: 0 0 6px rgba(208,80,80,0.5);
      }
      .inv-btn:disabled {
        opacity: 0.2;
        cursor: not-allowed;
      }
    `;
    document.head.appendChild(style);
  }
}
