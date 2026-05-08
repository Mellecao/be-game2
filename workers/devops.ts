// workers/devops.ts
import { startWorker } from './shared/base-worker.js';
import { ask } from './shared/llm.js';
import { pushToGitHub } from './shared/github.js';
import { join } from 'node:path';

const SYSTEM = `Você é o Engenheiro DevOps da Black Elephant.
Nunca deixa código sem versionamento. Reporta a URL do repositório criado.
Responde em português brasileiro.`;

startWorker({
  name: 'devops',
  port: 3008,

  onHeartbeat: async (payload) => {
    const slug       = String((payload.context?.['slug'] as string | undefined) ?? '');
    if (!slug) return ask(SYSTEM, payload.description);

    const projectDir = join(process.env.PROJECTS_BASE_DIR ?? 'C:/Users/v27me/Videos', slug);
    const url        = pushToGitHub(projectDir, slug);
    return `Repositório criado: ${url}`;
  },

  onInvoke: async (payload) => ask(SYSTEM, payload.message),
});
