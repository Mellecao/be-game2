import { Router } from 'express';
import { getSupabase } from '../lib/supabase.js';

const router = Router();

router.post('/login', async (req, res) => {
  const { nickname } = req.body as { nickname?: string };
  if (!nickname?.trim()) {
    res.status(400).json({ error: 'nickname obrigatório' });
    return;
  }

  const nick = nickname.trim().slice(0, 20);
  const db   = getSupabase();

  const { data: existing } = await db
    .from('players')
    .select('id, nickname, sprite_char')
    .eq('nickname', nick)
    .maybeSingle();

  if (existing) {
    await db.from('players').update({ last_seen: new Date().toISOString() }).eq('id', existing.id);
    res.json({ ...existing, is_new: false });
    return;
  }

  const sprite_char = Math.ceil(Math.random() * 4);
  const { data: created, error } = await db
    .from('players')
    .insert({ nickname: nick, sprite_char })
    .select('id, nickname, sprite_char')
    .single();

  if (error) {
    res.status(500).json({ error: error.message });
    return;
  }

  res.json({ ...created, is_new: true });
});

export default router;
