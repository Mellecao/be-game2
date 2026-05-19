import { existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
const __dir = dirname(fileURLToPath(import.meta.url));
const envFile = resolve(__dir, '.env');
if (existsSync(envFile)) process.loadEnvFile(envFile);

import express from 'express';
import cors from 'cors';
import { initSchema, history } from './db/messages.js';
import agentsRouter    from './routes/agents.js';
import inventoryRouter from './routes/inventory.js';
import furnitureRouter from './routes/furniture.js';
import chatRouter      from './routes/chat.js';
import vaultRouter     from './routes/vault.js';
import tasksRouter     from './routes/tasks.js';
import eventsRouter    from './routes/events.js';
import playersRouter   from './routes/players.js';

const DB_PATH = process.env.AGENT_DB_PATH ?? 'agent_messages.db';

export function createApp() {
  const app = express();
  app.use(cors());
  app.use(express.json({ limit: '20mb' }));

  app.get('/',           (_req, res) => res.json({ status: 'ok', service: 'be-game-server' }));
  app.get('/api/health', (_req, res) => res.json({ status: 'ok' }));

  app.use('/api/players',       playersRouter);
  app.use('/api/agents',        agentsRouter);
  app.use('/api/inventory',     inventoryRouter);
  app.use('/api/furniture',     furnitureRouter);
  app.use('/api/chat',          chatRouter);
  app.use('/api/vault',         vaultRouter);
  app.use('/api/planner/tasks', tasksRouter);
  app.use('/api/events',        eventsRouter);

  app.get('/api/agents/:agentId/messages', (_req, res) => {
    const limit = Number(_req.query['limit'] ?? 200);
    const msgs  = history(DB_PATH, _req.params.agentId, limit);
    res.json({ messages: msgs });
  });

  return app;
}

const PORT = Number(process.env.PORT ?? 8000);
const app  = createApp();
initSchema(DB_PATH);
app.listen(PORT, () => console.log(`[game-server] running on :${PORT}`));
