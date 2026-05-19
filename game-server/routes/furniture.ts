import { Router } from 'express';
import { getSupabase } from '../lib/supabase.js';

const router = Router();

router.get('/', async (_req, res) => {
  const db     = getSupabase();
  const { data, error } = await db.from('furniture_placements').select('id,col,row,direction,removed');
  if (error) { res.status(500).json({ error: error.message }); return; }
  res.json(data);
});

router.post('/save-all', async (req, res) => {
  const items = req.body as { id: string; col: number; row: number; direction: number; removed: boolean }[];
  const db    = getSupabase();
  const { error } = await db.from('furniture_placements').upsert(items);
  if (error) { res.status(500).json({ error: error.message }); return; }
  res.json({ ok: true, count: items.length });
});

export default router;
