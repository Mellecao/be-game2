import { Router } from 'express';
import { getSupabase } from '../lib/supabase.js';

const router = Router();

router.get('/', async (_req, res) => {
  const db     = getSupabase();
  const result = await db.table('furniture_placements').select('id,col,row,direction,removed').execute();
  res.json(result.data);
});

router.post('/save-all', async (req, res) => {
  const items = req.body as { id: string; col: number; row: number; direction: number; removed: boolean }[];
  const db    = getSupabase();
  await db.table('furniture_placements').upsert(items).execute();
  res.json({ ok: true, count: items.length });
});

export default router;
