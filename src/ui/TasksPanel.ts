interface PlannerTask {
  id: string;
  card_name: string;
  status: string;
  log: string;
  created_at: number;
  start_at: number;
  remaining_seconds: number;
  step: number;
}

const STATUS_LABELS: Record<string, string> = {
  waiting:     "Aguardando",
  delegating:  "Delegando",
  planning:    "Planejando",
  copywriting: "Copywriting",
  designing:   "Design",
  developing:  "Dev",
  reviewing:   "QA",
  revision:    "Revisão",
  deploying:   "Deploy",
  closing:     "Finalizando",
  done:        "Concluído",
  error:       "Erro",
  cancelled:   "Cancelado",
};

const STEP_LABELS: Record<string, string> = {
  waiting:     "— Aguardando início",
  delegating:  "— Delegando ao pipeline",
  planning:    "1/7 — Planejamento",
  copywriting: "2/7 — Copywriting",
  designing:   "3/7 — Design",
  developing:  "4/7 — Desenvolvimento",
  reviewing:   "5/7 — QA",
  revision:    "5/7 — Revisão solicitada",
  deploying:   "6/7 — Deploy",
  closing:     "7/7 — Finalizando",
  done:        "✓ Concluído",
  error:       "✗ Erro",
  cancelled:   "— Cancelado",
};

// Maps pipeline status to the NPC/agent ID currently executing
const STATUS_TO_AGENT: Record<string, string> = {
  planning:         "planner",
  copywriting:      "copywriter",
  designing:        "designer",
  imagining:        "image_artist",
  reviewing_assets: "designer",
  regen_assets:     "image_artist",
  modeling_3d:      "agente_3d",
  developing:       "programador",
  reviewing:        "qa",
  revision:         "programador",
  deploying:        "devops",
  closing:          "planner",
  curating:         "bibliotecario",
};

const AGENT_INFO: Record<string, { name: string; initials: string; color: string; role: string }> = {
  planner:       { name: "Planner",       initials: "PL", color: "#3b82f6", role: "Gerente de Projetos" },
  copywriter:    { name: "Copywriter",    initials: "CW", color: "#8b5cf6", role: "Copywriter de Landing Pages" },
  designer:      { name: "Designer",      initials: "DS", color: "#ec4899", role: "UI/UX Designer" },
  image_artist:  { name: "Image Artist",  initials: "IA", color: "#f43f5e", role: "Artista Visual de IA" },
  agente_3d:     { name: "Agente 3D",     initials: "3D", color: "#a855f7", role: "Artista 3D" },
  programador:   { name: "Programador",   initials: "PR", color: "#10b981", role: "Desenvolvedor Full-Stack" },
  qa:            { name: "QA",            initials: "QA", color: "#f59e0b", role: "Engenheiro de Qualidade" },
  devops:        { name: "DevOps",        initials: "DO", color: "#6366f1", role: "Engenheiro DevOps" },
  bibliotecario: { name: "Bibliotecario", initials: "BB", color: "#14b8a6", role: "Curador de Conhecimento" },
};

const ACTIVE_STATUSES = new Set([
  "waiting", "delegating", "planning", "copywriting",
  "designing", "imagining", "reviewing_assets", "regen_assets",
  "modeling_3d", "developing", "reviewing", "revision",
  "deploying", "closing", "curating",
]);

export class TasksPanel {
  private fab: HTMLElement;
  private panel: HTMLElement;
  private listEl: HTMLElement;
  private badge: HTMLElement;
  private isOpen = false;
  private pollTimer: number | null = null;
  private countdownTimer: number | null = null;
  private tasks: PlannerTask[] = [];
  private selectedTaskId: string | null = null;
  private onActiveAgentsChange: ((agentIds: Set<string>) => void) | null = null;
  private sseSource: EventSource | null = null;
  private terminalBuffers: Map<string, string> = new Map();

  constructor() {
    this.fab   = document.getElementById("tasks-fab")!;
    this.panel = document.getElementById("tasks-panel")!;
    this.listEl = document.getElementById("tasks-list")!;
    this.badge  = document.getElementById("tasks-badge")!;

    this.fab.addEventListener("click", () => this.toggle());
    document.getElementById("tasks-close")!.addEventListener("click", () => this.close());
    document.getElementById("tasks-back")!.addEventListener("click", () => this.closeDetail());

    this.startPolling();
    this.startCountdownTick();
  }

  /** Wire up callback that fires with active agent IDs after each poll. */
  setAgentWorkingCallback(cb: (agentIds: Set<string>) => void): void {
    this.onActiveAgentsChange = cb;
  }

  toggle(): void {
    this.isOpen ? this.close() : this.open();
  }

  open(): void {
    this.isOpen = true;
    this.panel.classList.add("open");
    this.render();
  }

  close(): void {
    this.disconnectSSE();
    this.isOpen = false;
    this.selectedTaskId = null;
    this.panel.classList.remove("open");
    this.syncHeaderButtons();
  }

  /** Called by AgentToast when SSE events arrive — triggers an immediate refresh */
  notifyUpdate(): void {
    this.fetchAndUpdate();
  }

  private startPolling(): void {
    this.fetchAndUpdate();
    this.pollTimer = window.setInterval(() => this.fetchAndUpdate(), 2000);
  }

  private startCountdownTick(): void {
    this.countdownTimer = window.setInterval(() => {
      if (!this.isOpen || this.selectedTaskId) return;
      this.panel.querySelectorAll<HTMLElement>(".task-countdown").forEach((el) => {
        const taskId = el.dataset.taskId!;
        const task = this.tasks.find((t) => t.id === taskId);
        if (!task || task.status !== "waiting") return;
        const remaining = Math.max(0, task.start_at - Date.now() / 1000);
        el.textContent = remaining > 0 ? `⏱ Iniciando em ${Math.ceil(remaining)}s` : "⏱ Iniciando...";
      });
    }, 1000);
  }

  private async fetchAndUpdate(): Promise<void> {
    try {
      const res = await fetch("/api/planner/tasks");
      if (!res.ok) return;
      this.tasks = await res.json();
      this.updateBadge();
      this.notifyActiveAgents();
      if (this.isOpen) this.render();
    } catch {
      // silently ignore network errors
    }
  }

  private updateBadge(): void {
    const active = this.tasks.filter((t) => ACTIVE_STATUSES.has(t.status)).length;
    this.badge.textContent = String(active);
    this.badge.style.display = active > 0 ? "flex" : "none";
  }

  private notifyActiveAgents(): void {
    if (!this.onActiveAgentsChange) return;
    const activeIds = new Set<string>();
    for (const task of this.tasks) {
      const agentId = STATUS_TO_AGENT[task.status];
      if (agentId) activeIds.add(agentId);
    }
    this.onActiveAgentsChange(activeIds);
  }

  private syncHeaderButtons(): void {
    const backBtn = document.getElementById("tasks-back")!;
    backBtn.style.display = this.selectedTaskId ? "inline-flex" : "none";
  }

  private openDetail(taskId: string): void {
    this.selectedTaskId = taskId;
    this.syncHeaderButtons();
    this.render();
    this.connectSSE(taskId);
  }

  private closeDetail(): void {
    this.disconnectSSE();
    this.selectedTaskId = null;
    this.syncHeaderButtons();
    this.render();
  }

  private connectSSE(taskId: string): void {
    this.disconnectSSE();
    const task = this.tasks.find((t) => t.id === taskId);
    if (!task || !ACTIVE_STATUSES.has(task.status)) return;

    this.sseSource = new EventSource("/api/events/stream");
    this.sseSource.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data) as { type: string; data: string };
        if (msg.type === "llm_chunk") {
          const chunk = JSON.parse(msg.data) as { task_id: string; text: string };
          if (chunk.task_id !== taskId) return;
          const prev = this.terminalBuffers.get(taskId) ?? "";
          this.terminalBuffers.set(taskId, prev + chunk.text);
          const termEl = document.getElementById(`task-terminal-${taskId}`);
          if (termEl) {
            termEl.textContent = this.terminalBuffers.get(taskId)!;
            termEl.scrollTop = termEl.scrollHeight;
          }
        } else if (msg.type === "pipeline_done" || msg.type === "error") {
          this.disconnectSSE();
        }
      } catch { /* ignore parse errors */ }
    };
    this.sseSource.onerror = () => this.disconnectSSE();
  }

  private disconnectSSE(): void {
    if (this.sseSource) {
      this.sseSource.close();
      this.sseSource = null;
    }
  }

  private render(): void {
    if (this.selectedTaskId) {
      const task = this.tasks.find((t) => t.id === this.selectedTaskId);
      if (task) {
        this.renderDetail(task);
        return;
      }
      // Task disappeared — fall back to list
      this.selectedTaskId = null;
      this.syncHeaderButtons();
    }
    this.renderList();
  }

  private renderList(): void {
    this.listEl.innerHTML = "";

    if (this.tasks.length === 0) {
      this.listEl.innerHTML = `<div class="tasks-empty">Nenhuma task ainda.<br>Crie um card no Trello TO-DO.</div>`;
      return;
    }

    const sorted = [...this.tasks].sort((a, b) => {
      const aActive = ACTIVE_STATUSES.has(a.status) ? 0 : 1;
      const bActive = ACTIVE_STATUSES.has(b.status) ? 0 : 1;
      if (aActive !== bActive) return aActive - bActive;
      return b.created_at - a.created_at;
    });

    for (const task of sorted) {
      this.listEl.appendChild(this.buildCard(task));
    }
  }

  private renderDetail(task: PlannerTask): void {
    const agentId      = STATUS_TO_AGENT[task.status] ?? null;
    const agentInfo    = agentId ? AGENT_INFO[agentId] : null;
    const stepLabel    = STEP_LABELS[task.status] ?? task.status;
    const isActive     = ACTIVE_STATUSES.has(task.status);
    const termContent  = this.terminalBuffers.get(task.id) ?? "";
    const showTerminal = isActive || termContent.length > 0;

    this.listEl.innerHTML = `
      <div class="task-detail">
        <div class="task-detail-name">${this.esc(task.card_name)}</div>

        <div class="task-detail-row">
          <span class="task-status-badge status-${task.status}">
            ${STATUS_LABELS[task.status] ?? task.status}
          </span>
          <span class="task-detail-step">${stepLabel}</span>
        </div>

        ${agentInfo ? `
        <div class="task-detail-agent">
          <div class="task-detail-agent-avatar" style="background:${agentInfo.color}">
            ${agentInfo.initials}
          </div>
          <div class="task-detail-agent-info">
            <div class="task-detail-agent-name">
              ${agentInfo.name}
              ${isActive ? '<span class="task-detail-live">● ao vivo</span>' : ''}
            </div>
            <div class="task-detail-agent-role">${agentInfo.role}</div>
          </div>
        </div>` : ""}

        <div class="task-detail-log-label">Log do agente</div>
        <div class="task-detail-log">${this.esc(task.log || "—")}</div>

        ${showTerminal ? `
        <div class="task-terminal-label">
          Terminal
          ${isActive ? '<span class="task-terminal-live-dot">●</span>' : ''}
        </div>
        <pre class="task-terminal" id="task-terminal-${task.id}">${this.esc(termContent)}</pre>
        ` : ""}

        ${isActive ? `
        <button class="task-cancel-btn" data-task-id="${task.id}">Cancelar task</button>` : ""}
      </div>
    `;

    // Re-connect SSE if this render was triggered by a poll and SSE isn't connected
    if (isActive && !this.sseSource) {
      this.connectSSE(task.id);
    }

    // Scroll terminal to bottom after render
    const termEl = document.getElementById(`task-terminal-${task.id}`);
    if (termEl) termEl.scrollTop = termEl.scrollHeight;

    const cancelBtn = this.listEl.querySelector<HTMLButtonElement>(".task-cancel-btn");
    cancelBtn?.addEventListener("click", () => this.cancelTask(task.id, cancelBtn!));
  }

  private buildCard(task: PlannerTask): HTMLElement {
    const card = document.createElement("div");
    card.className = "task-card";
    card.style.cursor = "pointer";

    const name = document.createElement("div");
    name.className = "task-card-name";
    name.textContent = task.card_name.length > 80
      ? task.card_name.slice(0, 77) + "..."
      : task.card_name;
    card.appendChild(name);

    const meta = document.createElement("div");
    meta.className = "task-card-meta";

    const badge = document.createElement("span");
    badge.className = `task-status-badge status-${task.status}`;
    badge.textContent = STATUS_LABELS[task.status] ?? task.status;
    meta.appendChild(badge);

    if (task.status === "waiting") {
      const countdown = document.createElement("span");
      countdown.className = "task-countdown";
      countdown.dataset.taskId = task.id;
      const remaining = Math.max(0, task.start_at - Date.now() / 1000);
      countdown.textContent = remaining > 0 ? `⏱ Iniciando em ${Math.ceil(remaining)}s` : "⏱ Iniciando...";
      meta.appendChild(countdown);
    }

    card.appendChild(meta);

    if (task.log) {
      const log = document.createElement("div");
      log.className = "task-log";
      log.textContent = task.log;
      card.appendChild(log);
    }

    // Click opens detail
    card.addEventListener("click", (e) => {
      if ((e.target as HTMLElement).closest(".task-cancel-btn")) return;
      this.openDetail(task.id);
    });

    if (ACTIVE_STATUSES.has(task.status)) {
      const btn = document.createElement("button");
      btn.className = "task-cancel-btn";
      btn.textContent = "Cancelar";
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        this.cancelTask(task.id, btn);
      });
      card.appendChild(btn);
    }

    return card;
  }

  private async cancelTask(taskId: string, btn: HTMLButtonElement): Promise<void> {
    btn.disabled = true;
    btn.textContent = "Cancelando...";
    try {
      await fetch(`/api/planner/tasks/${taskId}/cancel`, { method: "POST" });
      await this.fetchAndUpdate();
    } catch {
      btn.disabled = false;
      btn.textContent = "Cancelar";
    }
  }

  private esc(text: string): string {
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
}
