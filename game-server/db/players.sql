-- Rodar no SQL Editor do Supabase (https://supabase.com/dashboard)
-- Tabelas de posição/inventário já existentes no projeto:
--   furniture_placements (id, col, row, direction, removed)
--   inventory_items (item_id, quantity, owner_id)
--   agents (id, display_name, role, goal, backstory, col, row, sprite_char)

CREATE TABLE IF NOT EXISTS players (
  id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  nickname    TEXT        UNIQUE NOT NULL,
  sprite_char INTEGER     NOT NULL DEFAULT 1,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  last_seen   TIMESTAMPTZ DEFAULT NOW()
);
