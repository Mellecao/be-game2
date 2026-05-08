import { Router } from 'express';
import { record, initSchema } from '../db/messages.js';

const WORKER_PORTS: Record<string, number> = {
  secretario:    3001,
  bibliotecario: 3002,
};

const DB_PATH = process.env.AGENT_DB_PATH ?? 'agent_messages.db';

initSchema(DB_PATH);

const router = Router();

router.post('/:agentId', async (req, res) => {
  const { agentId } = req.params;
  const message = String((req.body as Record<string, unknown>).message ?? '').trim();

  if (!message) { res.status(400).json({ error: 'mensagem vazia' }); return; }

  const port = WORKER_PORTS[agentId];
  if (!port) { res.status(404).json({ error: `Agente sem handler de chat: ${agentId}` }); return; }

  record(DB_PATH, 'global', 'player', 'player', message);

  const workerRes = await fetch(`http://localhost:${port}/invoke`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, agentId }),
  });
  if (!workerRes.ok) { res.status(502).json({ error: 'worker error' }); return; }

  const { reply } = await workerRes.json() as { reply: string };
  record(DB_PATH, 'global', agentId, 'reply', reply);

  res.json({ reply, npc_id: agentId });
});

export default router;
