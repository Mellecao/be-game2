import type { TasksPanel } from "./TasksPanel";

const DURATION_MS = 7000;

// Events that should never show as toasts (too noisy or handled elsewhere)
const SILENT_EVENTS = new Set(["llm_chunk", "pipeline_step", "qa_failed"]);

type EventStyle = { bg: string };
const EVENT_STYLES: Record<string, EventStyle> = {
  task_new:          { bg: "#78350f" },
  planner_delegating:{ bg: "#1e3a5f" },
  dev_done:          { bg: "#14532d" },
  task_cancelled:    { bg: "#1c1c2e" },
  error:             { bg: "#7f1d1d" },
  pipeline_done:     { bg: "#14532d" },
};

export class AgentToast {
  private container: HTMLElement;

  constructor() {
    this.container = document.getElementById("agent-toasts")!;
    Object.assign(this.container.style, {
      position: "fixed",
      top: "16px",
      right: "16px",
      display: "flex",
      flexDirection: "column",
      gap: "8px",
      zIndex: "9999",
      pointerEvents: "none",
      maxWidth: "360px",
    });
  }

  show(type: string, message: string): void {
    const style = EVENT_STYLES[type] ?? { bg: "#1e293b" };
    const toast = document.createElement("div");

    Object.assign(toast.style, {
      background: style.bg,
      color: "#f1f5f9",
      padding: "10px 14px",
      borderRadius: "8px",
      fontSize: "13px",
      lineHeight: "1.4",
      boxShadow: "0 4px 12px rgba(0,0,0,0.4)",
      opacity: "0",
      transform: "translateX(110%)",
      transition: "opacity 0.3s ease, transform 0.3s ease",
      wordBreak: "break-word",
    });
    toast.textContent = message;

    this.container.appendChild(toast);
    requestAnimationFrame(() => {
      toast.style.opacity = "1";
      toast.style.transform = "translateX(0)";
    });

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(110%)";
      setTimeout(() => toast.remove(), 400);
    }, DURATION_MS);
  }
}

export function connectEventStream(
  toast: AgentToast,
  tasks?: TasksPanel,
  onLLMChunk?: (taskId: string, chunk: string) => void,
): void {
  const source = new EventSource("/api/events/stream");

  source.onmessage = (e) => {
    try {
      const event = JSON.parse(e.data) as { type: string; data: string };
      if (event.type === "connected") return;

      // Route LLM chunks to the game world (whisper bubbles), never toast them
      if (event.type === "llm_chunk") {
        if (onLLMChunk) {
          const chunk = JSON.parse(event.data) as { task_id: string; text: string };
          onLLMChunk(chunk.task_id, chunk.text);
        }
        return;
      }

      if (!SILENT_EVENTS.has(event.type)) {
        toast.show(event.type, event.data);
      }

      if (tasks && ["task_new", "planner_delegating", "dev_done", "task_cancelled", "error", "pipeline_done"].includes(event.type)) {
        tasks.notifyUpdate();
      }
    } catch {
      // ignore
    }
  };

  source.onerror = () => {
    source.close();
    setTimeout(() => connectEventStream(toast, tasks, onLLMChunk), 5000);
  };
}
