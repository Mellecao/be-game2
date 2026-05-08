import { Router } from 'express';
import { getSupabase } from '../lib/supabase.js';

const router = Router();

router.get('/', async (_req, res) => {
  const db     = getSupabase();
  const result = await db
    .table('agents')
    .select('id,display_name,role,goal,backstory,col,row,sprite_char')
    .execute();
  res.json(result.data);
});

router.put('/:agentId', async (req, res) => {
  const db      = getSupabase();
  const payload = req.body as Record<string, unknown>;
  if (Object.keys(payload).length === 0) { res.json({ ok: true }); return; }
  await db.table('agents').update(payload).eq('id', req.params.agentId).execute();
  res.json({ ok: true });
});

export default router;
