// workers/designer.ts
import { startWorker } from './shared/base-worker.js';
import { ask } from './shared/llm.js';

const SYSTEM = `Você é o UI/UX Designer e Diretor de Arte da Black Elephant.
A partir da copy recebida, cria um guia visual completo em Markdown:
paleta de cores (hex), tipografia (Google Fonts), mood/estética, estrutura de layout por seção,
componentes e animações sugeridas (GSAP). Escreva em português brasileiro.`;

async function saveGuideToVault(slug: string, content: string): Promise<void> {
  await fetch('http://localhost:8000/api/vault/knowledge', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      agent_id: 'designer', title: `${slug}-visual-guide`,
      content, ace_type: 'resources', tags: ['design', 'visual-guide'],
    }),
  });
}

startWorker({
  name: 'designer',
  port: 3005,

  onHeartbeat: async (payload) => {
    const guide = await ask(SYSTEM, payload.description, 4096);
    const slug  = String((payload.context?.['slug'] as string | undefined) ?? 'sem-slug');
    await saveGuideToVault(slug, guide).catch(console.error);
    return guide;
  },

  onInvoke: async (payload) => ask(SYSTEM, payload.message, 2048),
});
