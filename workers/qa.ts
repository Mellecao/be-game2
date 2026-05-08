// workers/qa.ts
import { startWorker } from './shared/base-worker.js';
import { ask } from './shared/llm.js';
import { readdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';

const SYSTEM = `Você é um QA meticuloso da Black Elephant.
Analisa o código do projeto com checklist:
1. HTML: doctype, meta viewport, title, charset
2. Sem texto hardcoded em inglês (exceto código)
3. Dependências externas declaradas
4. README presente
Emite STATUS: APROVADO ou STATUS: REPROVADO com justificativa.
Responde em português brasileiro com relatório estruturado.`;

async function readProjectFiles(projectDir: string): Promise<string> {
  try {
    const entries = await readdir(projectDir);
    const parts: string[] = [`Arquivos: ${entries.join(', ')}`];
    for (const file of ['index.html', 'README.md']) {
      try {
        const content = await readFile(join(projectDir, file), 'utf-8');
        parts.push(`\n--- ${file} (primeiros 500 chars) ---\n${content.slice(0, 500)}`);
      } catch { /* skip */ }
    }
    return parts.join('\n');
  } catch {
    return `Pasta ${projectDir} não encontrada.`;
  }
}

startWorker({
  name: 'qa',
  port: 3007,

  onHeartbeat: async (payload) => {
    const slug       = String((payload.context?.['slug'] as string | undefined) ?? '');
    const projectDir = slug
      ? join(process.env.PROJECTS_BASE_DIR ?? 'C:/Users/v27me/Videos', slug)
      : '';
    const files = projectDir ? await readProjectFiles(projectDir) : payload.description;
    return ask(SYSTEM, `Projeto: ${slug}\n\n${files}`, 2048);
  },

  onInvoke: async (payload) => ask(SYSTEM, payload.message),
});
