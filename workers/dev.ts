// workers/dev.ts
import { startWorker } from './shared/base-worker.js';
import { ask } from './shared/llm.js';
import { spawnSync } from 'node:child_process';
import { mkdirSync, existsSync } from 'node:fs';
import { join } from 'node:path';

const SYSTEM = `Você é um Desenvolvedor Full-Stack da Black Elephant especializado em sites imersivos.
Recebe um briefing e descreve o que o Claude Code CLI deve implementar.
Escreva prompts técnicos em inglês para o Claude Code. Responda em português brasileiro.`;

const BASE_DIR = process.env.PROJECTS_BASE_DIR ?? 'C:/Users/v27me/Videos';

startWorker({
  name: 'dev',
  port: 3006,

  onHeartbeat: async (payload) => {
    const slug       = String((payload.context?.['slug'] as string | undefined) ?? 'projeto');
    const projectDir = join(BASE_DIR, slug);
    if (!existsSync(projectDir)) mkdirSync(projectDir, { recursive: true });

    const prompt = await ask(SYSTEM,
      `Gere um prompt técnico completo em inglês para o Claude Code implementar:\n${payload.description}`,
      2048,
    );

    const result = spawnSync(
      'claude', ['--print', prompt],
      { cwd: projectDir, encoding: 'utf-8', timeout: 300_000 },
    );

    if (result.error) throw result.error;
    return result.stdout ?? 'Dev concluído';
  },

  onInvoke: async (payload) => ask(SYSTEM, payload.message),
});
