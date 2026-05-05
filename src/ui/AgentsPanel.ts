interface AgentData {
  id: string;
  display_name: string;
  role: string;
  goal: string;
  backstory: string;
  col: number;
  row: number;
  sprite_char: number;
}

interface KnowledgeItem {
  path: string;
  title: string;
  preview: string;
  tags: string[];
  created: string;
}

const ACE_CATEGORIES = [
  { id: "atlas",     icon: "🗺️",  label: "Atlas",     desc: "Conhecimento permanente e MOCs" },
  { id: "calendar",  icon: "📅",  label: "Calendar",  desc: "Registros temporais" },
  { id: "cards",     icon: "🃏",  label: "Cards",     desc: "Notas atômicas e curtas" },
  { id: "efforts",   icon: "🔥",  label: "Efforts",   desc: "Projetos ativos" },
  { id: "resources", icon: "📚",  label: "Resources", desc: "Biblioteca de consulta" },
  { id: "sources",   icon: "🌐",  label: "Sources",   desc: "O que vem de fora" },
];

export class AgentsPanel {
  private fab: HTMLElement;
  private panel: HTMLElement;
  private viewList: HTMLElement;
  private viewProfile: HTMLElement;
  private viewTraining: HTMLElement;
  private isOpen = false;
  private agents: AgentData[] = [];
  private currentAgent: AgentData | null = null;
  private currentTab = "quick";

  constructor() {
    this.fab          = document.getElementById("agents-fab")!;
    this.panel        = document.getElementById("agents-panel")!;
    this.viewList     = document.getElementById("agents-view-list")!;
    this.viewProfile  = document.getElementById("agents-view-profile")!;
    this.viewTraining = document.getElementById("agents-view-training")!;

    this.fab.addEventListener("click", () => this.toggle());
    document.getElementById("agents-close")!.addEventListener("click", () => this.close());
    document.getElementById("agents-back-profile")!.addEventListener("click", () => this.showView("list"));
    document.getElementById("agents-back-training")!.addEventListener("click", () => this.showView("profile"));

    document.querySelectorAll<HTMLElement>(".agents-tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        document.querySelectorAll(".agents-tab").forEach((t) => t.classList.remove("active"));
        tab.classList.add("active");
        this.currentTab = tab.dataset.tab!;
        if (this.currentAgent) this.renderTrainingTab();
      });
    });

    this.fetchAgents();
  }

  toggle(): void { this.isOpen ? this.close() : this.open(); }

  open(): void {
    this.isOpen = true;
    this.panel.classList.add("open");
  }

  close(): void {
    this.isOpen = false;
    this.panel.classList.remove("open");
  }

  private showView(view: "list" | "profile" | "training"): void {
    this.viewList.style.display     = view === "list"     ? "flex" : "none";
    this.viewProfile.style.display  = view === "profile"  ? "flex" : "none";
    this.viewTraining.style.display = view === "training" ? "flex" : "none";
  }

  // ── Agents List ─────────────────────────────────────────────────────────────

  private async fetchAgents(): Promise<void> {
    try {
      const res = await fetch("/api/agents");
      if (!res.ok) return;
      this.agents = await res.json();
      this.renderAgentList();
    } catch { /* ignore */ }
  }

  private renderAgentList(): void {
    const listEl = document.getElementById("agents-list")!;
    listEl.innerHTML = "";
    for (const agent of this.agents) {
      const card = document.createElement("div");
      card.className = "agent-card";
      card.innerHTML = `
        <div class="agent-card-avatar">${agent.display_name[0]}</div>
        <div class="agent-card-info">
          <div class="agent-card-name">${agent.display_name}</div>
          <div class="agent-card-role">${agent.role}</div>
        </div>
      `;
      card.addEventListener("click", () => this.openProfile(agent));
      listEl.appendChild(card);
    }
  }

  // ── Agent Profile ───────────────────────────────────────────────────────────

  private openProfile(agent: AgentData): void {
    this.currentAgent = agent;
    document.getElementById("agents-profile-name")!.textContent = agent.display_name;
    this.renderProfileContent();
    this.showView("profile");
  }

  private renderProfileContent(): void {
    const agent = this.currentAgent!;
    const el    = document.getElementById("agents-profile-content")!;
    el.innerHTML = `
      <div class="agent-profile-avatar">${agent.display_name[0]}</div>
      <div class="agent-profile-name">${agent.display_name}</div>
      <div class="agent-profile-role">${agent.role}</div>
      <div class="agent-crew-section">
        <h4>Definições CrewAI</h4>
        <div class="form-group">
          <label>Goal</label>
          <textarea id="agent-edit-goal" class="agent-edit-field" rows="3"></textarea>
        </div>
        <div class="form-group">
          <label>Backstory</label>
          <textarea id="agent-edit-backstory" class="agent-edit-field" rows="5"></textarea>
        </div>
      </div>
      <button id="agent-train-btn" class="agent-train-btn">Treinar</button>
    `;

    (el.querySelector<HTMLTextAreaElement>("#agent-edit-goal")!).value = agent.goal;
    (el.querySelector<HTMLTextAreaElement>("#agent-edit-backstory")!).value = agent.backstory;

    el.querySelector<HTMLTextAreaElement>("#agent-edit-goal")!.addEventListener("blur", async (e) => {
      const val = (e.target as HTMLTextAreaElement).value;
      await this.saveAgentField(agent.id, "goal", val);
      agent.goal = val;
    });

    el.querySelector<HTMLTextAreaElement>("#agent-edit-backstory")!.addEventListener("blur", async (e) => {
      const val = (e.target as HTMLTextAreaElement).value;
      await this.saveAgentField(agent.id, "backstory", val);
      agent.backstory = val;
    });

    el.querySelector("#agent-train-btn")!.addEventListener("click", () => this.openTraining());
  }

  private async saveAgentField(agentId: string, field: string, value: string): Promise<void> {
    try {
      await fetch(`/api/agents/${agentId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ [field]: value }),
      });
    } catch { /* ignore */ }
  }

  // ── Training Panel ──────────────────────────────────────────────────────────

  private openTraining(): void {
    document.getElementById("agents-training-title")!.textContent =
      `Treinar: ${this.currentAgent!.display_name}`;
    this.currentTab = "quick";
    document.querySelectorAll(".agents-tab").forEach((t) => t.classList.remove("active"));
    document.querySelector<HTMLElement>('.agents-tab[data-tab="quick"]')!.classList.add("active");
    this.renderTrainingTab();
    this.showView("training");
  }

  private renderTrainingTab(): void {
    const container = document.getElementById("agents-training-content")!;
    container.innerHTML = "";
    if (this.currentTab === "quick")     this.renderQuickAdd(container);
    else if (this.currentTab === "novo") this.renderNovoDoc(container);
    else                                 this.renderKnowledge(container);
  }

  // ── Tab: Quick-Add ACE ───────────────────────────────────────────────────────

  private renderQuickAdd(container: HTMLElement): void {
    const grid = document.createElement("div");
    grid.className = "ace-grid";

    for (const cat of ACE_CATEGORIES) {
      const wrapper = document.createElement("div");
      wrapper.className = "ace-card-wrapper";

      const card = document.createElement("div");
      card.className = "ace-card";
      card.innerHTML = `
        <span class="ace-card-icon">${cat.icon}</span>
        <span class="ace-card-label">${cat.label}</span>
        <span class="ace-card-desc">${cat.desc}</span>
      `;

      const formContainer = document.createElement("div");
      formContainer.className = "ace-form-container";
      formContainer.style.display = "none";

      card.addEventListener("click", () => {
        const isOpen = formContainer.style.display !== "none";
        grid.querySelectorAll<HTMLElement>(".ace-form-container").forEach((f) => (f.style.display = "none"));
        grid.querySelectorAll(".ace-card").forEach((c) => c.classList.remove("ace-card-open"));
        if (!isOpen) {
          formContainer.style.display = "block";
          card.classList.add("ace-card-open");
          this.buildAceForm(cat.id, formContainer, card);
        }
      });

      wrapper.appendChild(card);
      wrapper.appendChild(formContainer);
      grid.appendChild(wrapper);
    }

    container.appendChild(grid);
  }

  private buildAceForm(aceType: string, container: HTMLElement, card: HTMLElement): void {
    const agent = this.currentAgent!;
    container.innerHTML = "";

    const form = document.createElement("form");
    form.className = "ace-form";

    form.appendChild(this.makeField("Título", "text", "ace-title", ""));

    if (aceType === "atlas") {
      form.appendChild(this.makeToggle("Criar como MOC?", "ace-is-moc"));
      form.appendChild(this.makeField("Conteúdo", "textarea", "ace-content", ""));
      form.appendChild(this.makeField("Tags (vírgula)", "text", "ace-tags", ""));
    } else if (aceType === "calendar") {
      const today = new Date().toISOString().split("T")[0];
      form.appendChild(this.makeField("Data", "date", "ace-date", today));
      form.appendChild(this.makeField("Conteúdo", "textarea", "ace-content", ""));
    } else if (aceType === "cards") {
      form.appendChild(this.makeField("Conteúdo (curto)", "textarea", "ace-content", "", 3));
      form.appendChild(this.makeField("Tags (vírgula)", "text", "ace-tags", ""));
    } else if (aceType === "efforts") {
      const statusGroup = document.createElement("div");
      statusGroup.className = "form-group";
      statusGroup.innerHTML = `<label>Status</label>
        <select id="ace-effort-status" class="form-select">
          <option value="on">🔥 On (Ativo)</option>
          <option value="ongoing">♻️ Ongoing</option>
          <option value="simmering">〰️ Simmering</option>
        </select>`;
      form.appendChild(statusGroup);
      form.appendChild(this.makeField("Rank (1-10)", "number", "ace-rank", "5"));
      form.appendChild(this.makeField("Conteúdo", "textarea", "ace-content", ""));
    } else if (aceType === "resources") {
      const typeGroup = document.createElement("div");
      typeGroup.className = "form-group";
      typeGroup.innerHTML = `<label>Tipo</label>
        <select id="ace-res-type" class="form-select">
          <option value="design">Design</option>
          <option value="manual">Manual</option>
          <option value="referencia">Referência</option>
        </select>`;
      form.appendChild(typeGroup);
      form.appendChild(this.makeField("Conteúdo", "textarea", "ace-content", ""));
      const imgGroup = document.createElement("div");
      imgGroup.className = "form-group";
      imgGroup.innerHTML = `<label>Imagem (opcional)</label>
        <input type="file" id="ace-image-input" accept="image/*" class="form-input" />
        <div id="ace-image-preview" style="display:none;margin-top:6px">
          <img id="ace-image-thumb" style="max-width:100%;max-height:100px;border-radius:4px" />
        </div>`;
      form.appendChild(imgGroup);
    } else if (aceType === "sources") {
      form.appendChild(this.makeField("Origem (URL ou autor)", "text", "ace-source-url", ""));
      const srcTypeGroup = document.createElement("div");
      srcTypeGroup.className = "form-group";
      srcTypeGroup.innerHTML = `<label>Tipo</label>
        <select id="ace-src-type" class="form-select">
          <option value="artigo">Artigo</option>
          <option value="video">Vídeo</option>
          <option value="livro">Livro</option>
          <option value="dado">Dado</option>
        </select>`;
      form.appendChild(srcTypeGroup);
      form.appendChild(this.makeField("Conteúdo", "textarea", "ace-content", ""));
    }

    const submitBtn = document.createElement("button");
    submitBtn.type = "submit";
    submitBtn.className = "ace-submit-btn";
    submitBtn.textContent = "Salvar e Indexar";
    form.appendChild(submitBtn);
    container.appendChild(form);

    if (aceType === "resources") {
      const imgInput = form.querySelector<HTMLInputElement>("#ace-image-input")!;
      imgInput.addEventListener("change", () => {
        const file = imgInput.files?.[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = (e) => {
          const thumb   = form.querySelector<HTMLImageElement>("#ace-image-thumb")!;
          const preview = form.querySelector<HTMLElement>("#ace-image-preview")!;
          thumb.src             = e.target!.result as string;
          preview.style.display = "block";
        };
        reader.readAsDataURL(file);
      });
    }

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      submitBtn.disabled    = true;
      submitBtn.textContent = "Salvando...";
      try {
        await this.submitAceForm(aceType, form, agent.id);
        card.classList.remove("ace-card-open");
        container.style.display = "none";
        this.showToast("✅ Salvo e indexado!");
      } catch {
        this.showToast("❌ Erro ao salvar");
      } finally {
        submitBtn.disabled    = false;
        submitBtn.textContent = "Salvar e Indexar";
      }
    });
  }

  private async submitAceForm(aceType: string, form: HTMLFormElement, agentId: string): Promise<void> {
    const val = (id: string) =>
      (form.querySelector<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>(`#${id}`)?.value ?? "");

    const body: Record<string, unknown> = {
      agent_id: agentId,
      title:    val("ace-title"),
      content:  val("ace-content"),
      ace_type: aceType,
      tags:     val("ace-tags").split(",").map((t) => t.trim()).filter(Boolean),
    };

    if (aceType === "atlas") {
      body.ace_subtype = (form.querySelector<HTMLInputElement>("#ace-is-moc")?.checked) ? "moc" : "notes";
    } else if (aceType === "calendar") {
      body.date = val("ace-date");
    } else if (aceType === "efforts") {
      body.effort_status = val("ace-effort-status");
      const rank = parseInt(val("ace-rank"));
      if (!isNaN(rank)) body.rank = rank;
    } else if (aceType === "resources") {
      body.ace_subtype = val("ace-res-type");
      const imgInput = form.querySelector<HTMLInputElement>("#ace-image-input");
      if (imgInput?.files?.[0]) {
        const { b64, filename } = await this.fileToBase64(imgInput.files[0]);
        body.image_base64    = b64;
        body.image_filename  = filename;
      }
    } else if (aceType === "sources") {
      body.source_url  = val("ace-source-url");
      body.ace_subtype = val("ace-src-type");
    }

    const res = await fetch("/api/vault/knowledge", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error("API error");
  }

  // ── Tab: Novo Documento ──────────────────────────────────────────────────────

  private renderNovoDoc(container: HTMLElement): void {
    const agent = this.currentAgent!;
    container.innerHTML = `
      <form id="novo-doc-form" class="novo-doc-form">
        <div class="form-group">
          <label>Título</label>
          <input type="text" id="novo-titulo" class="form-input" required />
        </div>
        <div class="form-group">
          <label>Destino</label>
          <select id="novo-destino" class="form-select">
            <option value="atlas/notes">Atlas / Notes</option>
            <option value="atlas/cards">Atlas / Cards</option>
            <option value="atlas/sources">Atlas / Sources</option>
            <option value="atlas/resources">Atlas / Resources</option>
            <option value="calendar">Calendar</option>
            <option value="efforts/on">Efforts / On</option>
            <option value="efforts/ongoing">Efforts / Ongoing</option>
            <option value="efforts/simmering">Efforts / Simmering</option>
          </select>
        </div>
        <div class="form-group">
          <label>Tags (vírgula)</label>
          <input type="text" id="novo-tags" class="form-input" placeholder="ex: copywriting, referencia" />
        </div>
        <div class="form-group">
          <label>Conteúdo (Markdown)</label>
          <textarea id="novo-content" class="form-textarea" rows="7"></textarea>
        </div>
        <div class="form-group">
          <label>Imagem (opcional)</label>
          <div class="image-drop-zone" id="novo-drop-zone">
            <span>Arraste uma imagem ou clique para selecionar</span>
            <input type="file" id="novo-image-input" accept="image/*" style="display:none" />
          </div>
          <div id="novo-image-preview" style="display:none;margin-top:6px">
            <img id="novo-image-thumb" style="max-width:100%;max-height:120px;border-radius:4px" />
            <button type="button" id="novo-image-clear" class="image-clear-btn">✕ Remover imagem</button>
          </div>
        </div>
        <button type="submit" class="ace-submit-btn">Salvar e Indexar</button>
      </form>
    `;

    const dropZone = container.querySelector<HTMLElement>("#novo-drop-zone")!;
    const imgInput = container.querySelector<HTMLInputElement>("#novo-image-input")!;
    const preview  = container.querySelector<HTMLElement>("#novo-image-preview")!;
    const thumb    = container.querySelector<HTMLImageElement>("#novo-image-thumb")!;

    dropZone.addEventListener("click", () => imgInput.click());
    dropZone.addEventListener("dragover", (e) => { e.preventDefault(); dropZone.classList.add("dragover"); });
    dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
    dropZone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropZone.classList.remove("dragover");
      const f = (e as DragEvent).dataTransfer?.files[0];
      if (f) this.previewImage(f, thumb, preview, dropZone);
    });
    imgInput.addEventListener("change", () => {
      if (imgInput.files?.[0]) this.previewImage(imgInput.files[0], thumb, preview, dropZone);
    });
    container.querySelector("#novo-image-clear")!.addEventListener("click", () => {
      imgInput.value        = "";
      preview.style.display = "none";
      dropZone.style.display = "flex";
    });

    container.querySelector<HTMLFormElement>("#novo-doc-form")!.addEventListener("submit", async (e) => {
      e.preventDefault();
      const btn = container.querySelector<HTMLButtonElement>(".ace-submit-btn")!;
      btn.disabled = true; btn.textContent = "Salvando...";
      try {
        const titulo  = container.querySelector<HTMLInputElement>("#novo-titulo")!.value;
        const destino = container.querySelector<HTMLSelectElement>("#novo-destino")!.value;
        const tags    = container.querySelector<HTMLInputElement>("#novo-tags")!.value
          .split(",").map((t) => t.trim()).filter(Boolean);
        const content = container.querySelector<HTMLTextAreaElement>("#novo-content")!.value;
        const { ace_type, ace_subtype, effort_status } = this.mapDestino(destino);

        const body: Record<string, unknown> = { agent_id: agent.id, title: titulo, content, ace_type, ace_subtype, tags };
        if (effort_status) body.effort_status = effort_status;

        if (imgInput.files?.[0]) {
          const { b64, filename } = await this.fileToBase64(imgInput.files[0]);
          body.image_base64   = b64;
          body.image_filename = filename;
        }

        const res = await fetch("/api/vault/knowledge", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!res.ok) throw new Error();

        this.showToast("✅ Documento salvo e indexado!");
        container.querySelector<HTMLFormElement>("#novo-doc-form")!.reset();
        imgInput.value = "";
        preview.style.display  = "none";
        dropZone.style.display = "flex";
      } catch {
        this.showToast("❌ Erro ao salvar documento");
      } finally {
        btn.disabled = false; btn.textContent = "Salvar e Indexar";
      }
    });
  }

  private mapDestino(d: string): { ace_type: string; ace_subtype: string; effort_status: string | null } {
    const map: Record<string, { ace_type: string; ace_subtype: string; effort_status: string | null }> = {
      "atlas/notes":       { ace_type: "atlas",     ace_subtype: "notes",  effort_status: null },
      "atlas/cards":       { ace_type: "cards",     ace_subtype: "",       effort_status: null },
      "atlas/sources":     { ace_type: "sources",   ace_subtype: "",       effort_status: null },
      "atlas/resources":   { ace_type: "resources", ace_subtype: "",       effort_status: null },
      "calendar":          { ace_type: "calendar",  ace_subtype: "daily",  effort_status: null },
      "efforts/on":        { ace_type: "efforts",   ace_subtype: "",       effort_status: "on" },
      "efforts/ongoing":   { ace_type: "efforts",   ace_subtype: "",       effort_status: "ongoing" },
      "efforts/simmering": { ace_type: "efforts",   ace_subtype: "",       effort_status: "simmering" },
    };
    return map[d] ?? { ace_type: "atlas", ace_subtype: "notes", effort_status: null };
  }

  // ── Tab: Conhecimento Atual ──────────────────────────────────────────────────

  private renderKnowledge(container: HTMLElement): void {
    const agent = this.currentAgent!;
    container.innerHTML = `
      <div class="knowledge-toolbar">
        <input type="text" id="knowledge-search" class="form-input" placeholder="Buscar título ou preview..." />
        <button id="knowledge-reindex" class="reindex-btn">Re-indexar tudo</button>
      </div>
      <div id="knowledge-list"><div class="knowledge-loading">Carregando...</div></div>
    `;

    let allItems: KnowledgeItem[] = [];

    container.querySelector("#knowledge-search")!.addEventListener("input", (e) => {
      const q = (e.target as HTMLInputElement).value.toLowerCase();
      this.renderKnowledgeItems(
        allItems.filter((i) => i.title.toLowerCase().includes(q) || i.preview.toLowerCase().includes(q)),
        agent.id,
        container,
      );
    });

    const reindexBtn = container.querySelector<HTMLButtonElement>("#knowledge-reindex")!;
    reindexBtn.addEventListener("click", async () => {
      reindexBtn.disabled = true; reindexBtn.textContent = "Indexando...";
      try {
        const res  = await fetch(`/api/vault/reindex/${agent.id}`, { method: "POST" });
        const data = await res.json();
        this.showToast(`✅ ${data.indexed_count} chunks re-indexados`);
      } catch {
        this.showToast("❌ Erro ao re-indexar");
      } finally {
        reindexBtn.disabled = false; reindexBtn.textContent = "Re-indexar tudo";
      }
    });

    fetch(`/api/vault/knowledge/${agent.id}`)
      .then((r) => r.json())
      .then((items: KnowledgeItem[]) => {
        allItems = items;
        this.renderKnowledgeItems(items, agent.id, container);
      })
      .catch(() => {
        const listEl = container.querySelector<HTMLElement>("#knowledge-list")!;
        listEl.innerHTML = '<div class="knowledge-empty">Erro ao carregar arquivos do vault.</div>';
      });
  }

  private renderKnowledgeItems(items: KnowledgeItem[], agentId: string, container: HTMLElement): void {
    const listEl = container.querySelector<HTMLElement>("#knowledge-list")!;
    if (items.length === 0) {
      listEl.innerHTML = '<div class="knowledge-empty">Nenhum arquivo encontrado. Adicione conhecimento nas abas acima.</div>';
      return;
    }
    listEl.innerHTML = "";
    for (const item of items) {
      const card = document.createElement("div");
      card.className = "knowledge-card";
      card.innerHTML = `
        <div class="knowledge-card-header">
          <span class="knowledge-title">${this.esc(item.title)}</span>
          <button class="knowledge-delete-btn" title="Excluir">🗑️</button>
        </div>
        <div class="knowledge-path">${this.esc(item.path)}</div>
        <div class="knowledge-preview">${this.esc(item.preview)}</div>
      `;
      card.querySelector(".knowledge-delete-btn")!.addEventListener("click", async () => {
        if (!confirm(`Excluir "${item.title}" do vault?`)) return;
        try {
          await fetch("/api/vault/knowledge", {
            method: "DELETE",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ path: item.path, agent_id: agentId }),
          });
          card.remove();
          this.showToast("🗑️ Arquivo excluído do vault");
        } catch {
          this.showToast("❌ Erro ao excluir arquivo");
        }
      });
      listEl.appendChild(card);
    }
  }

  // ── Utilities ───────────────────────────────────────────────────────────────

  private makeField(label: string, type: string, id: string, defaultVal: string, rows = 4): HTMLElement {
    const g = document.createElement("div");
    g.className = "form-group";
    if (type === "textarea") {
      g.innerHTML = `<label>${label}</label><textarea id="${id}" class="form-textarea" rows="${rows}"></textarea>`;
      (g.querySelector("textarea") as HTMLTextAreaElement).value = defaultVal;
    } else {
      g.innerHTML = `<label>${label}</label><input type="${type}" id="${id}" class="form-input" />`;
      (g.querySelector("input") as HTMLInputElement).value = defaultVal;
    }
    return g;
  }

  private makeToggle(label: string, id: string): HTMLElement {
    const g = document.createElement("div");
    g.className = "form-group form-toggle";
    g.innerHTML = `<label><input type="checkbox" id="${id}" /> ${label}</label>`;
    return g;
  }

  private previewImage(file: File, thumb: HTMLImageElement, preview: HTMLElement, dropZone: HTMLElement): void {
    const reader = new FileReader();
    reader.onload = (e) => {
      thumb.src              = e.target!.result as string;
      preview.style.display  = "block";
      dropZone.style.display = "none";
    };
    reader.readAsDataURL(file);
  }

  private async fileToBase64(file: File): Promise<{ b64: string; filename: string }> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload  = (e) => resolve({ b64: (e.target!.result as string).split(",")[1], filename: file.name });
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  private showToast(msg: string): void {
    const container = document.getElementById("agent-toasts")!;
    const toast     = document.createElement("div");
    toast.className = "agent-toast toast-info";
    toast.textContent = msg;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
  }

  private esc(s: string): string {
    return s
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
}
