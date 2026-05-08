// workers/planner.ts
import { startWorker } from './shared/base-worker.js';
import { ask } from './shared/llm.js';
import { listCards, getCard } from './shared/trello.js';

const SYSTEM = `Você é o Gerente de Projetos da Black Elephant.
Analisa cards do Trello e descreve claramente o que precisa ser feito.
Responde em português brasileiro, objetivo.`;

const SEEN = new Set<string>();
let polling = false;

async function notifyGameServer(task: { id: string; card_name: string; status: string; log: string; step: number }): Promise<void> {
  try {
    await fetch('http://localhost:8000/api/planner/tasks/upsert', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(task),
    });
  } catch { /* game-server may not be up */ }
}

async function pollTrello(): Promise<void> {
  const listId = process.env.TRELLO_LIST_ID;
  if (!listId) return;

  const cards = await listCards(listId);
  for (const card of cards) {
    if (SEEN.has(card.id)) continue;
    SEEN.add(card.id);

    console.log(`[planner] novo card: "${card.name}"`);
    await notifyGameServer({
      id: card.id, card_name: card.name,
      status: 'waiting', log: 'Aguardando 180s antes de executar', step: 0,
    });

    setTimeout(async () => {
      const fresh = await getCard(card.id);
      await notifyGameServer({ id: fresh.id, card_name: fresh.name, status: 'planning', log: 'Planner analisando', step: 1 });
      console.log(`[planner] card "${fresh.name}" pronto para pipeline`);
    }, 180_000);
  }
}

if (!polling) {
  polling = true;
  setInterval(pollTrello, 60_000);
  pollTrello().catch(console.error);
}

startWorker({
  name: 'planner',
  port: 3003,

  onHeartbeat: async (payload) => {
    return ask(SYSTEM, `Analise e descreva o que precisa ser feito:\n${payload.description}`);
  },

  onInvoke: async (payload) => {
    const listId = process.env.TRELLO_LIST_ID ?? '';
    const cards  = listId ? await listCards(listId) : [];
    const context = cards.length
      ? cards.map((c) => `- ${c.name}`).join('\n')
      : 'Nenhum card no momento.';
    return ask(SYSTEM, `Cards no Trello:\n${context}\n\nPergunta: ${payload.message}`);
  },
});
