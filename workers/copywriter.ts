// workers/copywriter.ts
import { startWorker } from './shared/base-worker.js';
import { ask } from './shared/llm.js';

const SYSTEM = `Você é um Copywriter sênior da Black Elephant, especializado em landing pages.
Cria textos persuasivos em Markdown: headline, hero, benefícios (3-5), como funciona, CTA, FAQ.
Consulte contexto do vault quando fornecido. Escreva em português brasileiro.`;

async function saveToVault(slug: string, content: string): Promise<void> {
  await fetch('http://localhost:8000/api/vault/knowledge', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      agent_id: 'copywriter', title: `${slug}-copy`,
      content, ace_type: 'atlas', ace_subtype: 'notes',
      tags: ['copy', 'landing-page'],
    }),
  });
}

startWorker({
  name: 'copywriter',
  port: 3004,

  onHeartbeat: async (payload) => {
    const copy = await ask(SYSTEM, payload.description, 4096);
    const slug = String((payload.context?.['slug'] as string | undefined) ?? 'sem-slug');
    await saveToVault(slug, copy).catch(console.error);
    return copy;
  },

  onInvoke: async (payload) => {
    return ask(SYSTEM, payload.message, 2048);
  },
});
