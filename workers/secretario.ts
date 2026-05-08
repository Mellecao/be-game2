// workers/secretario.ts
import { startWorker } from './shared/base-worker.js';
import { ask } from './shared/llm.js';

const SYSTEM = `Você é o Secretário da Black Elephant. Tem visão completa do pipeline.
Responde em português brasileiro, factual, 1-3 frases. Se não souber, diz "sem info no momento".`;

async function getPipelineContext(): Promise<string> {
  try {
    const res   = await fetch('http://localhost:8000/api/planner/tasks');
    const tasks = await res.json() as { card_name: string; status: string; step: number; log: string }[];
    if (!tasks.length) return 'Nenhuma task ativa no momento.';
    return tasks.slice(0, 5).map((t) =>
      `- "${t.card_name}" [${t.status}] etapa ${t.step}: ${t.log}`,
    ).join('\n');
  } catch {
    return 'Pipeline indisponível no momento.';
  }
}

startWorker({
  name:   'secretario',
  port:   3001,
  apiKey: process.env.PAPERCLIP_API_KEY_SECRETARIO,

  onHeartbeat: async (payload) => {
    const context = await getPipelineContext();
    return ask(SYSTEM, `Contexto do pipeline:\n${context}\n\nTarefa: ${payload.description}`);
  },

  onInvoke: async (payload) => {
    const context = await getPipelineContext();
    return ask(SYSTEM, `Contexto do pipeline:\n${context}\n\nJogador perguntou: ${payload.message}`);
  },
});
