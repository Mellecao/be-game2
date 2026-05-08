import { Router } from 'express';
import { getTasks, cancelTask, upsertTask } from '../lib/pipeline-state.js';

const router = Router();

router.get('/', (_req, res) => {
  res.json(getTasks());
});

router.post('/upsert', (req, res) => {
  const task = req.body as Parameters<typeof upsertTask>[0];
  upsertTask(task);
  res.json({ ok: true });
});

router.post('/:taskId/cancel', (req, res) => {
  const ok = cancelTask(req.params.taskId);
  if (!ok) { res.status(404).json({ error: 'Task nao encontrada ou ja finalizada' }); return; }
  res.json({ ok: true });
});

export default router;
