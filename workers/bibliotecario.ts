// workers/bibliotecario.ts
import { startWorker } from './shared/base-worker.js';
import { ask } from './shared/llm.js';

const SYSTEM = `Você é o Bibliotecário da Black Elephant. Conhece o vault Ideaverse de cor.
Responde em português brasileiro. Cita a fonte (path da nota) quando aplicável.`;

async function searchVaultRemote(query: string): Promise<string> {
  try {
    const url = `http://localhost:8000/api/vault/search?q=${encodeURIComponent(query)}`;
    const res = await fetch(url);
    const { result } = await res.json() as { result: string };
    return result;
  } catch {
    return 'Vault indisponível no momento.';
  }
}

startWorker({
  name: 'bibliotecario',
  port: 3002,

  onHeartbeat: async (payload) => {
    const context = await searchVaultRemote(payload.description.slice(0, 100));
    return ask(SYSTEM, `Contexto do vault:\n${context}\n\nTarefa: ${payload.description}`);
  },

  onInvoke: async (payload) => {
    const context = await searchVaultRemote(payload.message);
    return ask(SYSTEM, `Contexto do vault:\n${context}\n\nJogador perguntou: ${payload.message}`);
  },
});
