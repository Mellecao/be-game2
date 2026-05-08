import { Router } from 'express';
import { getSupabase } from '../lib/supabase.js';

const router = Router();
const DEFAULTS = ['sofa', 'chair', 'desk', 'table', 'window'];

async function ensureSeed() {
  const db  = getSupabase();
  const res = await db.table('inventory_items').select('id').limit(1).execute();
  if (!res.data?.length) {
    await db.table('inventory_items').insert(
      DEFAULTS.map((item_id) => ({ item_id, quantity: 1, owner_id: null })),
    ).execute();
  }
}

router.get('/', async (_req, res) => {
  await ensureSeed();
  const db     = getSupabase();
  const result = await db.table('inventory_items').select('item_id,quantity').is('owner_id', null).execute();
  res.json(result.data);
});

router.post('/add', async (req, res) => {
  const { item_id } = req.body as { item_id: string };
  const db = getSupabase();
  const existing = await db.table('inventory_items').select('id,quantity').eq('item_id', item_id).is('owner_id', null).execute();
  if (existing.data?.length) {
    const current = existing.data[0].quantity as number;
    if (current >= 4) { res.status(400).json({ error: 'Limite de 4 atingido' }); return; }
    await db.table('inventory_items').update({ quantity: current + 1 }).eq('id', existing.data[0].id).execute();
  } else {
    await db.table('inventory_items').insert({ item_id, quantity: 1, owner_id: null }).execute();
  }
  res.json({ ok: true });
});

router.post('/remove', async (req, res) => {
  const { item_id } = req.body as { item_id: string };
  const db = getSupabase();
  const existing = await db.table('inventory_items').select('id,quantity').eq('item_id', item_id).is('owner_id', null).execute();
  if (!existing.data?.length || (existing.data[0].quantity as number) <= 0) {
    res.status(400).json({ error: 'Sem estoque' }); return;
  }
  const current = existing.data[0].quantity as number;
  await db.table('inventory_items').update({ quantity: current - 1 }).eq('id', existing.data[0].id).execute();
  res.json({ ok: true });
});

export default router;
