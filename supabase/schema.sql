-- BE-Game schema
-- Execute no Supabase Dashboard > SQL Editor

-- Jogadores
create table if not exists public.players (
    id uuid primary key default gen_random_uuid(),
    user_id text unique not null,
    avatar_skin smallint not null default 1 check (avatar_skin between 1 and 5),
    position_x integer not null default 6,
    position_y integer not null default 5,
    last_seen timestamptz not null default now(),
    created_at timestamptz not null default now()
);

-- Mensagens do chat com NPCs
create table if not exists public.chat_messages (
    id bigserial primary key,
    player_id uuid not null references public.players(id) on delete cascade,
    npc_id text not null,
    role text not null check (role in ('user', 'assistant')),
    message text not null,
    created_at timestamptz not null default now()
);

create index if not exists chat_messages_player_npc_idx
    on public.chat_messages (player_id, npc_id, created_at);

-- Posicionamento de mobilia
create table if not exists public.furniture_placements (
    id        text primary key,
    col       integer not null,
    row       integer not null,
    direction integer not null,
    removed   boolean not null default false
);

-- RLS desabilitado (v1 sem auth)
alter table public.players disable row level security;
alter table public.chat_messages disable row level security;
alter table public.furniture_placements disable row level security;
