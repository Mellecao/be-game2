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
        <div class="agent-card-avatar">${this.esc(agent.display_name[0])}</div>
        <div class="agent-card-info">
          <div class="agent-card-name">${this.esc(agent.display_name)}</div>
          <div class="agent-card-role">${this.esc(agent.role)}</div>
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
      <div class="agent-profile-avatar">${this.esc(agent.display_name[0])}</div>
      <div class="agent-profile-name">${this.esc(agent.display_name)}</div>
      <div class="agent-profile-role">${this.esc(agent.role)}</div>
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
    const list = document.createElement("div");
    list.className = "ace-list";

    for (const cat of ACE_CATEGORIES) {
      const item = document.createElement("div");
      item.className = "ace-list-item";
      item.innerHTML = `
        <span class="ace-list-icon">${cat.icon}</span>
        <div class="ace-list-text">
          <div class="ace-list-label">${cat.label}</div>
          <div class="ace-list-desc">${cat.desc}</div>
        </div>
        <span class="ace-list-arrow">›</span>
      `;
      item.addEventListener("click", () => this.openAceForm(cat, container));
      list.appendChild(item);
    }

    container.appendChild(list);
  }

  private openAceForm(
    cat: { id: string; icon: string; label: string; desc: string },
    container: HTMLElement,
  ): void {
    container.innerHTML = "";

    const header = document.createElement("div");
    header.className = "ace-full-header";
    header.innerHTML = `
      <button class="ace-full-back">← Voltar</button>
      <div class="ace-full-header-text">
        <span class="ace-full-icon">${cat.icon}</span>
        <span class="ace-full-title">${cat.label}</span>
      </div>
      <div class="ace-full-sub">${cat.desc}</div>
    `;
    header.querySelector(".ace-full-back")!.addEventListener("click", () => {
      container.innerHTML = "";
      this.renderQuickAdd(container);
    });
    container.appendChild(header);

    this.buildFullAceForm(cat.id, container);
  }

  private buildFullAceForm(aceType: string, container: HTMLElement): void {
    const agent = this.currentAgent!;
    const form = document.createElement("form");
    form.className = "ace-full-form";

    if (aceType === "atlas") {
      form.appendChild(this.makeFieldHint("Título *", "text", "ace-title", "", "Ex: Princípio de Pareto, Conceito de Flow, Método GTD"));
      form.appendChild(this.makeSelect("Tipo", "ace-atlas-type", [
        ["notes",       "📄 Nota de Conhecimento"],
        ["moc",         "🗺️ Mapa de Conteúdo (MOC)"],
        ["concept",     "💡 Conceito ou Definição"],
        ["framework",   "⚙️ Framework ou Método"],
      ]));
      form.appendChild(this.makeFieldHint("Tags", "text", "ace-tags", "", "Ex: produtividade, sistemas, criatividade"));
      form.appendChild(this.makeFieldHint("Links relacionados", "text", "ace-links", "", "Ex: [[Conceito X]], [[Black Elephant MOC]]"));
      form.appendChild(this.makeBigTextarea("ace-content",
        "Descreva o que você sabe sobre este tema. Use Markdown para estruturar.\n\nEx:\nEste conceito é fundamental porque...\n\n## Como aplicar\n- Passo 1\n- Passo 2\n\n## Por que importa\n..."));
      form.appendChild(this.makeFieldHint("Conexões com outros conceitos", "textarea", "ace-connections", "", "Como este conhecimento se conecta com o restante do seu sistema?", 2));

    } else if (aceType === "calendar") {
      form.appendChild(this.makeSelect("Tipo de registro", "ace-calendar-type", [
        ["daily",    "📆 Log Diário"],
        ["meeting",  "🤝 Reunião"],
        ["idea",     "💡 Ideia Capturada"],
        ["weekly",   "📊 Revisão Semanal"],
        ["retro",    "🔄 Retrospectiva"],
      ]));
      form.appendChild(this.makeFieldHint("Data *", "date", "ace-date", new Date().toISOString().split("T")[0], ""));
      form.appendChild(this.makeFieldHint("Título *", "text", "ace-title", "", "Ex: Reunião com cliente X, Ideia sobre campanha Y"));
      form.appendChild(this.makeFieldHint("Participantes", "text", "ace-participants", "", "Ex: Ana, Bruno, Carlos (deixe vazio se for pessoal)"));
      form.appendChild(this.makeBigTextarea("ace-content",
        "O que aconteceu? O que foi discutido? Principais decisões tomadas?\n\nEx:\n- Ponto discutido 1\n- Ponto discutido 2\n\n## Decisões\n- \n\n## Insights\n- "));
      form.appendChild(this.makeFieldHint("Próximas ações", "textarea", "ace-next-actions", "", "- [ ] Ação 1\n- [ ] Ação 2", 3));

    } else if (aceType === "cards") {
      form.appendChild(this.makeFieldHint("Título — o conceito em uma frase *", "text", "ace-title", "",
        "Ex: \"O poder dos sistemas supera o poder das metas\" (uma ideia, uma nota)"));
      form.appendChild(this.makeFieldHint("Fonte", "text", "ace-card-source", "", "Ex: Atomic Habits – James Clear, artigo no Medium, conversa com fulano"));
      form.appendChild(this.makeFieldHint("Tags", "text", "ace-tags", "", "Ex: hábitos, sistemas, mentalidade"));
      form.appendChild(this.makeBigTextarea("ace-content",
        "Escreva apenas UMA ideia. Deve ser:\n• Curta e clara\n• Atemporal (evite datas e contextos efêmeros)\n• Escrita com suas próprias palavras\n\nEx:\nEste conceito diz que... porque..."));
      form.appendChild(this.makeFieldHint("Links [[...]]", "text", "ace-links", "", "Ex: [[Sistemas vs Metas]], [[Habit Loop]]"));

    } else if (aceType === "efforts") {
      form.appendChild(this.makeFieldHint("Título do projeto *", "text", "ace-title", "", "Ex: BE-Game v2, Campanha Janeiro, Site Black Elephant"));
      form.appendChild(this.makeSelect("Status", "ace-effort-status", [
        ["on",        "🔥 On — foco total agora"],
        ["ongoing",   "♻️ Ongoing — recorrente, sempre ativo"],
        ["simmering", "〰️ Simmering — segundo plano"],
        ["sleeping",  "😴 Sleeping — pausado"],
      ]));
      form.appendChild(this.makeFieldHint("Rank de prioridade (1–10)", "number", "ace-rank", "5", "10 = máxima prioridade"));
      form.appendChild(this.makeFieldHint("Objetivo", "text", "ace-effort-objective", "", "O que este projeto precisa entregar? Ex: Site publicado e aprovado pelo cliente"));
      form.appendChild(this.makeBigTextarea("ace-content",
        "Descreva o projeto: contexto, motivação, abordagem atual, progresso...\n\n## Contexto\n\n## O que já foi feito\n\n## Bloqueios atuais\n\n## Referências\n- [[Nota relacionada]]"));
      form.appendChild(this.makeFieldHint("Próximos passos", "textarea", "ace-next-steps", "", "- [ ] Passo 1\n- [ ] Passo 2\n- [ ] Passo 3", 3));

    } else if (aceType === "resources") {
      form.appendChild(this.makeFieldHint("Título *", "text", "ace-title", "", "Ex: Guia de Tom de Voz, Template de Briefing, Paleta de Cores Black Elephant"));
      form.appendChild(this.makeSelect("Tipo de recurso", "ace-res-type", [
        ["design",     "🎨 Design / Visual"],
        ["manual",     "📖 Manual / Procedimento"],
        ["template",   "📋 Template"],
        ["referencia", "🔗 Referência"],
        ["guia",       "🧭 Guia / How-to"],
        ["checklist",  "✅ Checklist"],
        ["asset",      "📦 Asset / Arquivo"],
      ]));
      form.appendChild(this.makeFieldHint("URL ou caminho da fonte", "text", "ace-resource-url", "", "Ex: https://figma.com/file/..., C:/Projetos/..."));
      form.appendChild(this.makeBigTextarea("ace-content",
        "Descreva este recurso. O que é? Como usar? Quando usar?\n\n## Descrição\n\n## Como usar\n\n## Quando usar\n- \n\n## Observações\n"));
      const imgGroup = document.createElement("div");
      imgGroup.className = "form-group";
      imgGroup.innerHTML = `<label>Imagem / Preview (opcional)</label>
        <input type="file" id="ace-image-input" accept="image/*" class="form-input" />
        <div id="ace-image-preview" style="display:none;margin-top:6px">
          <img id="ace-image-thumb" style="max-width:100%;max-height:120px;border-radius:4px;object-fit:contain" />
        </div>`;
      form.appendChild(imgGroup);

    } else if (aceType === "sources") {
      form.appendChild(this.makeFieldHint("Título *", "text", "ace-title", "", "Ex: Como construir hábitos atômicos, O Poder do Hábito, TED: Simon Sinek"));
      form.appendChild(this.makeFieldHint("Autor", "text", "ace-author", "", "Ex: James Clear, Cal Newport, Paul Graham"));
      form.appendChild(this.makeFieldHint("URL / Link", "text", "ace-source-url", "", "Ex: https://jamesclear.com/atomic-habits"));
      form.appendChild(this.makeSelect("Tipo de fonte", "ace-src-type", [
        ["artigo",   "📰 Artigo / Blog"],
        ["video",    "🎥 Vídeo / YouTube"],
        ["livro",    "📚 Livro"],
        ["podcast",  "🎙️ Podcast"],
        ["paper",    "🔬 Paper / Pesquisa"],
        ["dado",     "📊 Dado / Estatística"],
        ["post",     "📱 Post / Tweet"],
      ]));
      form.appendChild(this.makeFieldHint("Data de publicação", "date", "ace-pub-date", "", ""));
      form.appendChild(this.makeBigTextarea("ace-content",
        "Principais insights:\n• \n• \n• \n\nCitações relevantes:\n\"...\"\n\nO que aprendi / como aplicar:\n\nConexões com meu trabalho:\n- "));
      form.appendChild(this.makeFieldHint("Tags", "text", "ace-tags", "", "Ex: produtividade, marketing, referência"));
    }

    const submitBtn = document.createElement("button");
    submitBtn.type = "submit";
    submitBtn.className = "ace-submit-btn ace-submit-full";
    submitBtn.textContent = "Salvar e Indexar no Vault";
    form.appendChild(submitBtn);
    container.appendChild(form);

    if (aceType === "resources") {
      const imgInput = form.querySelector<HTMLInputElement>("#ace-image-input")!;
      imgInput.addEventListener("change", () => {
        const file = imgInput.files?.[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = (e) => {
          form.querySelector<HTMLImageElement>("#ace-image-thumb")!.src = e.target!.result as string;
          form.querySelector<HTMLElement>("#ace-image-preview")!.style.display = "block";
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
        form.reset();
        this.showToast("✅ Salvo e indexado no vault!");
      } catch {
        this.showToast("❌ Erro ao salvar");
      } finally {
        submitBtn.disabled    = false;
        submitBtn.textContent = "Salvar e Indexar no Vault";
      }
    });
  }

  private buildRichContent(aceType: string, form: HTMLFormElement): string {
    const val = (id: string) =>
      (form.querySelector<HTMLInputElement | HTMLTextAreaElement>(`#${id}`)?.value ?? "").trim();

    const parts: string[] = [val("ace-content")];

    if (aceType === "atlas") {
      const links = val("ace-links");
      const connections = val("ace-connections");
      if (links) parts.push(`## Links Relacionados\n${links}`);
      if (connections) parts.push(`## Conexões\n${connections}`);
    } else if (aceType === "calendar") {
      const participants = val("ace-participants");
      const nextActions  = val("ace-next-actions");
      if (participants) parts.push(`## Participantes\n${participants}`);
      if (nextActions)  parts.push(`## Próximas Ações\n${nextActions}`);
    } else if (aceType === "cards") {
      const source = val("ace-card-source");
      const links  = val("ace-links");
      if (source) parts.push(`## Fonte\n${source}`);
      if (links)  parts.push(`## Links\n${links}`);
    } else if (aceType === "efforts") {
      const objective  = val("ace-effort-objective");
      const nextSteps  = val("ace-next-steps");
      if (objective) parts.push(`## Objetivo\n${objective}`);
      if (nextSteps) parts.push(`## Próximos Passos\n${nextSteps}`);
    } else if (aceType === "resources") {
      const url = val("ace-resource-url");
      if (url) parts.push(`## Fonte / URL\n${url}`);
    } else if (aceType === "sources") {
      const author  = val("ace-author");
      const pubDate = val("ace-pub-date");
      const url     = val("ace-source-url");
      if (author)  parts.push(`## Autor\n${author}`);
      if (pubDate) parts.push(`## Data de Publicação\n${pubDate}`);
      if (url)     parts.push(`## Link\n${url}`);
    }

    return parts.filter(Boolean).join("\n\n");
  }

  private async submitAceForm(aceType: string, form: HTMLFormElement, agentId: string): Promise<void> {
    const val = (id: string) =>
      (form.querySelector<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>(`#${id}`)?.value ?? "");

    const body: Record<string, unknown> = {
      agent_id: agentId,
      title:    val("ace-title"),
      content:  this.buildRichContent(aceType, form),
      ace_type: aceType,
      tags:     val("ace-tags").split(",").map((t) => t.trim()).filter(Boolean),
    };

    if (aceType === "atlas") {
      const atlasType = val("ace-atlas-type");
      body.ace_subtype = atlasType === "moc" ? "moc" : "notes";
    } else if (aceType === "calendar") {
      body.date = val("ace-date");
      body.ace_subtype = val("ace-calendar-type");
    } else if (aceType === "efforts") {
      body.effort_status = val("ace-effort-status");
      const rank = parseInt(val("ace-rank"));
      if (!isNaN(rank)) body.rank = rank;
    } else if (aceType === "resources") {
      body.ace_subtype = val("ace-res-type");
      const imgInput = form.querySelector<HTMLInputElement>("#ace-image-input");
      if (imgInput?.files?.[0]) {
        const { b64, filename } = await this.fileToBase64(imgInput.files[0]);
        body.image_base64   = b64;
        body.image_filename = filename;
      }
    } else if (aceType === "sources") {
      body.source_url  = val("ace-source-url");
      body.source_author = val("ace-author");
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

  private makeFieldHint(label: string, type: string, id: string, defaultVal: string, hint: string, rows = 4): HTMLElement {
    const g = document.createElement("div");
    g.className = "form-group";
    const lbl = document.createElement("label");
    lbl.textContent = label;
    g.appendChild(lbl);
    if (type === "textarea") {
      const ta = document.createElement("textarea");
      ta.id = id;
      ta.className = "form-textarea";
      ta.rows = rows;
      if (defaultVal) ta.value = defaultVal;
      g.appendChild(ta);
    } else {
      const inp = document.createElement("input");
      inp.type = type;
      inp.id = id;
      inp.className = "form-input";
      if (defaultVal) inp.value = defaultVal;
      g.appendChild(inp);
    }
    if (hint) {
      const h = document.createElement("div");
      h.className = "field-hint";
      h.textContent = hint;
      g.appendChild(h);
    }
    return g;
  }

  private makeSelect(label: string, id: string, options: [string, string][]): HTMLElement {
    const g = document.createElement("div");
    g.className = "form-group";
    const lbl = document.createElement("label");
    lbl.textContent = label;
    const sel = document.createElement("select");
    sel.id = id;
    sel.className = "form-select";
    for (const [value, text] of options) {
      const opt = document.createElement("option");
      opt.value = value;
      opt.textContent = text;
      sel.appendChild(opt);
    }
    g.appendChild(lbl);
    g.appendChild(sel);
    return g;
  }

  private makeBigTextarea(id: string, placeholder: string): HTMLElement {
    const g = document.createElement("div");
    g.className = "form-group ace-big-textarea-group";
    const lbl = document.createElement("label");
    lbl.textContent = "Conteúdo / Descrição";
    const ta = document.createElement("textarea");
    ta.id = id;
    ta.className = "form-textarea ace-big-textarea";
    ta.placeholder = placeholder;
    g.appendChild(lbl);
    g.appendChild(ta);
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
