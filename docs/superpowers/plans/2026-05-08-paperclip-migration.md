# Paperclip AI Migration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all CrewAI + Python server code with Paperclip AI + TypeScript (Express game-server + worker HTTP agents), keeping the PixiJS game frontend untouched.

**Architecture:** Paperclip AI orchestrates pipeline agents (copywriter → designer → dev → qa → devops) via heartbeat. A new Express TypeScript game-server replaces the Python FastAPI server on port 8000. Each agent is a standalone Express HTTP worker; NPC chat calls workers directly for real-time response; pipeline tasks go through Paperclip.

**Tech Stack:** Node.js 20+, TypeScript 5.x, Express 5, better-sqlite3, @supabase/supabase-js, @anthropic-ai/sdk, Vitest, Paperclip AI (npx paperclipai)

---

## File Map

**Created:**
- `game-server/package.json`
- `game-server/tsconfig.json`
- `game-server/index.ts` — Express app entry
- `game-server/db/messages.ts` — SQLite agent_messages
- `game-server/lib/supabase.ts` — Supabase client
- `game-server/lib/vault.ts` — Obsidian file read/write/search
- `game-server/lib/trello.ts` — Trello REST client
- `game-server/lib/github.ts` — GitHub REST client
- `game-server/routes/agents.ts` — /api/agents
- `game-server/routes/inventory.ts` — /api/inventory
- `game-server/routes/furniture.ts` — /api/furniture
- `game-server/routes/chat.ts` — /api/chat/:agentId
- `game-server/routes/vault.ts` — /api/vault/*
- `game-server/routes/tasks.ts` — /api/planner/tasks
- `game-server/routes/events.ts` — SSE /api/events/stream
- `workers/package.json`
- `workers/tsconfig.json`
- `workers/shared/llm.ts` — Anthropic client
- `workers/shared/base-worker.ts` — Express worker template
- `workers/secretario.ts` — NPC: pipeline status
- `workers/bibliotecario.ts` — NPC: vault search
- `workers/planner.ts` — polls Trello, creates Paperclip tasks
- `workers/copywriter.ts` — writes copy
- `workers/designer.ts` — visual guide
- `workers/dev.ts` — spawns Claude Code CLI
- `workers/qa.ts` — code review
- `workers/devops.ts` — GitHub push

**Modified:**
- `vite.config.ts` — proxy port unchanged (8000)

**Deleted (Task 27):**
- `server/` (all Python files)
- `agents.py`, `tasks.py`, `main.py`, `planner_main.py`
- `supabase/Usersv27mecrewai-studio/`

---

## Task 1: Install Paperclip AI

**Files:** none

- [ ] **Step 1: Run onboarding**

```powershell
npx paperclipai onboard --yes
```

Expected: Paperclip installs, creates config, prints a local URL (e.g. `http://localhost:4000`).

- [ ] **Step 2: Verify it starts**

```powershell
npx paperclipai start
```

Expected: Server running. Open the printed URL in browser — you should see the Paperclip UI.

- [ ] **Step 3: Note the API base URL and port**

Check the Paperclip UI for: REST API endpoint (usually `http://localhost:4000/api`), how to register HTTP webhook agents, how to create tasks.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: paperclip onboard config"
```

---

## Task 2: Init game-server package

**Files:**
- Create: `game-server/package.json`
- Create: `game-server/tsconfig.json`

- [ ] **Step 1: Create package.json**

```json
{
  "name": "be-game-server",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "start": "node --import tsx/esm index.ts",
    "dev": "tsx watch index.ts",
    "test": "vitest run"
  },
  "dependencies": {
    "@supabase/supabase-js": "^2.45.0",
    "@anthropic-ai/sdk": "^0.30.0",
    "better-sqlite3": "^11.0.0",
    "cors": "^2.8.5",
    "express": "^5.0.0",
    "yaml": "^2.5.0"
  },
  "devDependencies": {
    "@types/better-sqlite3": "^7.6.11",
    "@types/cors": "^2.8.17",
    "@types/express": "^5.0.0",
    "@types/node": "^22.0.0",
    "supertest": "^7.0.0",
    "@types/supertest": "^6.0.0",
    "tsx": "^4.0.0",
    "typescript": "^5.6.0",
    "vitest": "^2.0.0"
  }
}
```

- [ ] **Step 2: Create tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "esModuleInterop": true,
    "outDir": "dist",
    "rootDir": ".",
    "skipLibCheck": true
  },
  "include": ["."]
}
```

- [ ] **Step 3: Install deps**

```powershell
Set-Location game-server; npm install
```

Expected: `node_modules/` created.

- [ ] **Step 4: Commit**

```bash
git add game-server/package.json game-server/tsconfig.json
git commit -m "chore: init game-server package"
```

---

## Task 3: game-server/db/messages.ts

**Files:**
- Create: `game-server/db/messages.ts`
- Create: `game-server/db/messages.test.ts`

- [ ] **Step 1: Write failing test**

```typescript
// game-server/db/messages.test.ts
import { describe, it, expect, beforeEach } from 'vitest';
import { initSchema, record, history } from './messages.js';

describe('messages db', () => {
  beforeEach(() => { initSchema(':memory:'); });

  it('records and retrieves a message', () => {
    record(':memory:', 'global', 'secretario', 'reply', 'olá');
    const msgs = history(':memory:', 'secretario', 10);
    expect(msgs).toHaveLength(1);
    expect(msgs[0].text).toBe('olá');
    expect(msgs[0].agent_id).toBe('secretario');
  });
});
```

- [ ] **Step 2: Run test — verify FAIL**

```powershell
Set-Location game-server; npx vitest run db/messages.test.ts
```

Expected: FAIL — `Cannot find module './messages.js'`

- [ ] **Step 3: Implement**

```typescript
// game-server/db/messages.ts
import Database from 'better-sqlite3';

const DEFAULT_PATH = process.env.AGENT_DB_PATH ?? 'agent_messages.db';
let _db: Database.Database | null = null;

function getDb(path = DEFAULT_PATH): Database.Database {
  if (path === ':memory:') return new Database(':memory:');
  if (!_db) _db = new Database(path);
  return _db;
}

export function initSchema(path = DEFAULT_PATH): void {
  const db = getDb(path);
  db.exec(`
    CREATE TABLE IF NOT EXISTS agent_messages (
      id       INTEGER PRIMARY KEY AUTOINCREMENT,
      slug     TEXT NOT NULL,
      agent_id TEXT NOT NULL,
      type     TEXT NOT NULL,
      text     TEXT NOT NULL,
      ts       REAL NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_am_agent ON agent_messages(agent_id, ts DESC);
    CREATE INDEX IF NOT EXISTS idx_am_slug  ON agent_messages(slug, ts DESC);
  `);
}

export function record(
  dbPath: string,
  slug: string,
  agentId: string,
  type: string,
  text: string,
): number {
  const db = getDb(dbPath);
  const ts = Date.now() / 1000;
  const result = db
    .prepare('INSERT INTO agent_messages (slug, agent_id, type, text, ts) VALUES (?, ?, ?, ?, ?)')
    .run(slug, agentId, type, text, ts);
  return Number(result.lastInsertRowid);
}

export function history(
  dbPath: string,
  agentId: string,
  limit = 200,
): Record<string, unknown>[] {
  const db = getDb(dbPath);
  return db
    .prepare(
      `SELECT * FROM (SELECT * FROM agent_messages WHERE agent_id = ? ORDER BY ts DESC LIMIT ?)
       ORDER BY ts ASC`,
    )
    .all(agentId, limit) as Record<string, unknown>[];
}
```

- [ ] **Step 4: Run test — verify PASS**

```powershell
npx vitest run db/messages.test.ts
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add game-server/db/
git commit -m "feat(game-server): SQLite agent_messages db"
```

---

## Task 4: game-server/lib/supabase.ts

**Files:**
- Create: `game-server/lib/supabase.ts`

- [ ] **Step 1: Create file**

```typescript
// game-server/lib/supabase.ts
import { createClient, SupabaseClient } from '@supabase/supabase-js';

let _client: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient {
  if (!_client) {
    const url  = process.env.SUPABASE_URL;
    const key  = process.env.SUPABASE_ANON_KEY ?? process.env.SUPABASE_SERVICE_KEY;
    if (!url || !key) throw new Error('SUPABASE_URL and SUPABASE_ANON_KEY are required');
    _client = createClient(url, key);
  }
  return _client;
}
```

- [ ] **Step 2: Commit**

```bash
git add game-server/lib/supabase.ts
git commit -m "feat(game-server): Supabase client"
```

---

## Task 5: game-server/lib/vault.ts

**Files:**
- Create: `game-server/lib/vault.ts`
- Create: `game-server/lib/vault.test.ts`

- [ ] **Step 1: Write failing test**

```typescript
// game-server/lib/vault.test.ts
import { describe, it, expect } from 'vitest';
import { buildFrontmatter, vaultFilePath } from './vault.js';

describe('vault helpers', () => {
  it('builds YAML frontmatter', () => {
    const fm = buildFrontmatter({ agentId: 'copywriter', aceType: 'atlas', tags: ['test'] });
    expect(fm).toContain('agent: copywriter');
    expect(fm).toContain('tags:');
  });

  it('resolves atlas/notes path', () => {
    const p = vaultFilePath('/vault', {
      agentId: 'copywriter', title: 'Minha Nota',
      aceType: 'atlas', aceSubtype: 'notes',
    });
    expect(p).toContain('Atlas/Notes/Agentes/Copywriter');
    expect(p).toContain('Minha Nota.md');
  });
});
```

- [ ] **Step 2: Run test — verify FAIL**

```powershell
npx vitest run lib/vault.test.ts
```

Expected: FAIL

- [ ] **Step 3: Implement**

```typescript
// game-server/lib/vault.ts
import { readdir, readFile, writeFile, mkdir, unlink } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { join, dirname, basename } from 'node:path';
import { stringify } from 'yaml';

const VAULT_PATH = process.env.OBSIDIAN_VAULT_PATH ?? 'C:/Users/v27me/Documents/Ideaverse';

const AGENT_DISPLAY: Record<string, string> = {
  copywriter: 'Copywriter', vendedor: 'Vendedor', planner: 'Planner',
  designer: 'Designer', qa: 'QA', devops: 'DevOps',
  bibliotecario: 'Bibliotecario', secretario: 'Secretário',
  dev: 'Dev', researcher: 'Researcher',
};

export interface VaultCreateOpts {
  agentId: string;
  title: string;
  content: string;
  aceType: string;
  aceSubtype?: string;
  tags?: string[];
  effortStatus?: string;
  date?: string;
  sourceUrl?: string;
  sourceAuthor?: string;
  rank?: number;
}

export interface VaultFrontmatterOpts {
  agentId: string;
  aceType: string;
  tags?: string[];
  date?: string;
  sourceUrl?: string;
  sourceAuthor?: string;
  rank?: number;
}

const UP_MAP: Record<string, string> = {
  atlas: '[[Black Elephant MOC]]', calendar: '[[Calendar]]',
  cards: '[[Atlas]]', efforts: '[[Efforts]]',
  resources: '[[Atlas]]', sources: '[[Atlas]]',
};

export function buildFrontmatter(opts: VaultFrontmatterOpts): string {
  const today = new Date().toISOString().split('T')[0];
  const tags = ['agente', opts.agentId, ...(opts.tags ?? [])].filter(
    (v, i, a) => a.indexOf(v) === i,
  );
  const fm: Record<string, unknown> = {
    up: [UP_MAP[opts.aceType] ?? '[[Black Elephant MOC]]'],
    agent: opts.agentId,
    tags,
    created: today,
  };
  if (opts.rank != null) fm['rank'] = opts.rank;
  if (opts.sourceUrl) fm['source_url'] = opts.sourceUrl;
  if (opts.sourceAuthor) fm['source_author'] = opts.sourceAuthor;
  return `---\n${stringify(fm)}---\n\n`;
}

export function vaultFilePath(vaultRoot: string, opts: Omit<VaultCreateOpts, 'content'>): string {
  const safe  = opts.title.replace(/[<>:"/\\|?*]/g, '').trim() || 'nota';
  const name  = AGENT_DISPLAY[opts.agentId] ?? opts.agentId;
  const t = opts.aceType, s = opts.aceSubtype ?? '';
  if (t === 'atlas') {
    if (s === 'moc') return join(vaultRoot, 'Atlas', 'Maps', `${safe} MOC.md`);
    return join(vaultRoot, 'Atlas', 'Notes', 'Agentes', name, `${safe}.md`);
  }
  if (t === 'calendar') {
    const d = opts.date ?? new Date().toISOString().split('T')[0];
    return join(vaultRoot, 'Calendar', `${d}-${safe}.md`);
  }
  if (t === 'cards') return join(vaultRoot, 'Atlas', 'Notes', 'Cards', name, `${safe}.md`);
  if (t === 'efforts') {
    const folderMap: Record<string, string> = { on: 'On', ongoing: 'Ongoing', simmering: 'Simmering' };
    const folder = folderMap[opts.effortStatus ?? 'on'] ?? 'On';
    const suffix = opts.effortStatus === 'ongoing' ? '(OE)' : '(E)';
    return join(vaultRoot, 'Efforts', folder, `${safe} ${suffix}.md`);
  }
  if (t === 'resources') return join(vaultRoot, 'Atlas', 'Utilities', name, `${safe}.md`);
  if (t === 'sources')   return join(vaultRoot, 'Atlas', 'Notes', 'Sources', name, `${safe}.md`);
  return join(vaultRoot, 'Atlas', 'Notes', 'Agentes', name, `${safe}.md`);
}

export async function writeNote(opts: VaultCreateOpts): Promise<string> {
  let filePath = vaultFilePath(VAULT_PATH, opts);
  await mkdir(dirname(filePath), { recursive: true });
  if (existsSync(filePath)) {
    const stem = basename(filePath, '.md');
    filePath   = join(dirname(filePath), `${stem}_${Date.now()}.md`);
  }
  const fm   = buildFrontmatter(opts);
  const body = `${fm}# ${opts.title}\n\n${opts.content}`;
  await writeFile(filePath, body, 'utf-8');
  return filePath;
}

export async function searchVault(query: string, maxResults = 5): Promise<string> {
  const q   = query.toLowerCase();
  const hits: { path: string; excerpt: string }[] = [];
  await _walkMd(VAULT_PATH, async (filePath) => {
    if (hits.length >= maxResults) return;
    const text = await readFile(filePath, 'utf-8');
    if (text.toLowerCase().includes(q)) {
      const lines = text.split('\n');
      const idx   = lines.findIndex((l) => l.toLowerCase().includes(q));
      const start = Math.max(0, idx - 1);
      const excerpt = lines.slice(start, start + 4).join('\n');
      hits.push({ path: filePath.replace(VAULT_PATH, ''), excerpt });
    }
  });
  if (!hits.length) return 'Nenhum resultado encontrado no vault.';
  return hits.map((h) => `**${h.path}**\n${h.excerpt}`).join('\n\n---\n\n');
}

export async function getAgentFiles(agentId: string): Promise<{ path: string; title: string; preview: string; tags: string[]; created: string }[]> {
  const name  = AGENT_DISPLAY[agentId] ?? agentId;
  const items: { path: string; title: string; preview: string; tags: string[]; created: string }[] = [];
  await _walkMd(VAULT_PATH, async (filePath) => {
    const text = await readFile(filePath, 'utf-8');
    if (!text.includes(`agent: ${agentId}`)) return;
    const title   = basename(filePath, '.md');
    const preview = text.replace(/^---[\s\S]*?---\n*/m, '').slice(0, 120);
    const tagMatch = text.match(/^tags:\s*\n((?:\s+-\s+.+\n)*)/m);
    const tags    = tagMatch ? tagMatch[1].split('\n').map((l) => l.replace(/\s+-\s+/, '').trim()).filter(Boolean) : [];
    const dateMatch = text.match(/created:\s*(.+)/);
    const created = dateMatch?.[1]?.trim() ?? '';
    items.push({ path: filePath.replace(VAULT_PATH + '/', ''), title, preview, tags, created });
  });
  return items;
}

export async function deleteNote(relativePath: string): Promise<void> {
  await unlink(join(VAULT_PATH, relativePath));
}

async function _walkMd(dir: string, fn: (p: string) => Promise<void>): Promise<void> {
  let entries: string[];
  try { entries = await readdir(dir); } catch { return; }
  for (const entry of entries) {
    const full = join(dir, entry);
    if (entry.startsWith('.')) continue;
    try {
      const stat = await import('node:fs/promises').then((m) => m.stat(full));
      if (stat.isDirectory()) await _walkMd(full, fn);
      else if (entry.endsWith('.md')) await fn(full);
    } catch { /* skip */ }
  }
}
```

- [ ] **Step 4: Run test — verify PASS**

```powershell
npx vitest run lib/vault.test.ts
```

- [ ] **Step 5: Commit**

```bash
git add game-server/lib/vault.ts game-server/lib/vault.test.ts
git commit -m "feat(game-server): vault read/write/search lib"
```

---

## Task 6: game-server/lib/trello.ts

**Files:**
- Create: `game-server/lib/trello.ts`

- [ ] **Step 1: Implement**

```typescript
// game-server/lib/trello.ts
const BASE = 'https://api.trello.com/1';

function auth() {
  const key   = process.env.TRELLO_API_KEY;
  const token = process.env.TRELLO_TOKEN;
  if (!key || !token) throw new Error('TRELLO_API_KEY and TRELLO_TOKEN are required');
  return { key, token };
}

export async function listCards(listId: string): Promise<{ id: string; name: string; desc: string }[]> {
  const { key, token } = auth();
  const url = `${BASE}/lists/${listId}/cards?key=${key}&token=${token}&fields=name,desc,id`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Trello error ${res.status}`);
  return res.json() as Promise<{ id: string; name: string; desc: string }[]>;
}

export async function getCard(cardId: string): Promise<{ id: string; name: string; desc: string }> {
  const { key, token } = auth();
  const url = `${BASE}/cards/${cardId}?key=${key}&token=${token}&fields=name,desc`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Trello error ${res.status}`);
  return res.json() as Promise<{ id: string; name: string; desc: string }>;
}

export async function moveCard(cardId: string, listId: string): Promise<void> {
  const { key, token } = auth();
  await fetch(`${BASE}/cards/${cardId}?key=${key}&token=${token}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ idList: listId }),
  });
}

export async function updateCardDesc(cardId: string, desc: string): Promise<void> {
  const { key, token } = auth();
  await fetch(`${BASE}/cards/${cardId}?key=${key}&token=${token}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ desc }),
  });
}
```

- [ ] **Step 2: Commit**

```bash
git add game-server/lib/trello.ts
git commit -m "feat(game-server): Trello REST client"
```

---

## Task 7: game-server/lib/github.ts

**Files:**
- Create: `game-server/lib/github.ts`

- [ ] **Step 1: Implement**

```typescript
// game-server/lib/github.ts
import { execSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { join } from 'node:path';

export function pushToGitHub(projectDir: string, slug: string): string {
  const ghToken = process.env.GITHUB_TOKEN;
  const ghUser  = process.env.GITHUB_USER ?? 'omelleca';
  if (!ghToken) throw new Error('GITHUB_TOKEN required');

  const repoUrl = `https://${ghUser}:${ghToken}@github.com/${ghUser}/${slug}.git`;

  if (!existsSync(join(projectDir, '.git'))) {
    execSync('git init', { cwd: projectDir });
    execSync('git add -A', { cwd: projectDir });
    execSync(`git commit -m "feat: ${slug} initial"`, { cwd: projectDir });
  }

  try {
    execSync(`gh repo create ${slug} --public --source=. --remote=origin --push`, { cwd: projectDir });
    return `https://github.com/${ghUser}/${slug}`;
  } catch {
    execSync(`git remote set-url origin ${repoUrl} || git remote add origin ${repoUrl}`, { cwd: projectDir });
    execSync('git push -u origin HEAD', { cwd: projectDir });
    return `https://github.com/${ghUser}/${slug}`;
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add game-server/lib/github.ts
git commit -m "feat(game-server): GitHub push lib"
```

---

## Task 8: game-server/routes/agents.ts

**Files:**
- Create: `game-server/routes/agents.ts`
- Create: `game-server/routes/agents.test.ts`

- [ ] **Step 1: Write failing test**

```typescript
// game-server/routes/agents.test.ts
import { describe, it, expect, vi } from 'vitest';
import request from 'supertest';
import express from 'express';
import agentsRouter from './agents.js';

vi.mock('../lib/supabase.js', () => ({
  getSupabase: () => ({
    table: () => ({
      select: () => ({ execute: async () => ({ data: [{ id: 'secretario', display_name: 'Secretário' }] }) }),
      update: () => ({ eq: () => ({ execute: async () => ({}) }) }),
    }),
  }),
}));

const app = express();
app.use(express.json());
app.use('/api/agents', agentsRouter);

describe('GET /api/agents', () => {
  it('returns agent list', async () => {
    const res = await request(app).get('/api/agents');
    expect(res.status).toBe(200);
    expect(res.body[0].id).toBe('secretario');
  });
});
```

- [ ] **Step 2: Run test — verify FAIL**

```powershell
npx vitest run routes/agents.test.ts
```

- [ ] **Step 3: Implement**

```typescript
// game-server/routes/agents.ts
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
```

- [ ] **Step 4: Run test — verify PASS**

```powershell
npx vitest run routes/agents.test.ts
```

- [ ] **Step 5: Commit**

```bash
git add game-server/routes/agents.ts game-server/routes/agents.test.ts
git commit -m "feat(game-server): agents route"
```

---

## Task 9: game-server/routes/inventory.ts

**Files:**
- Create: `game-server/routes/inventory.ts`

- [ ] **Step 1: Implement**

```typescript
// game-server/routes/inventory.ts
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
```

- [ ] **Step 2: Commit**

```bash
git add game-server/routes/inventory.ts
git commit -m "feat(game-server): inventory route"
```

---

## Task 10: game-server/routes/furniture.ts

**Files:**
- Create: `game-server/routes/furniture.ts`

- [ ] **Step 1: Implement**

```typescript
// game-server/routes/furniture.ts
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
```

- [ ] **Step 2: Commit**

```bash
git add game-server/routes/furniture.ts
git commit -m "feat(game-server): furniture route"
```

---

## Task 11: game-server/routes/vault.ts

**Files:**
- Create: `game-server/routes/vault.ts`

- [ ] **Step 1: Implement**

```typescript
// game-server/routes/vault.ts
import { Router } from 'express';
import { writeNote, getAgentFiles, deleteNote, searchVault } from '../lib/vault.js';

const router = Router();

router.get('/knowledge/:agentId', async (req, res) => {
  const items = await getAgentFiles(req.params.agentId);
  res.json(items);
});

router.post('/knowledge', async (req, res) => {
  const body = req.body as {
    agent_id: string; title: string; content: string;
    ace_type: string; ace_subtype?: string; tags?: string[];
    effort_status?: string; date?: string;
    source_url?: string; source_author?: string; rank?: number;
  };
  const filePath = await writeNote({
    agentId:      body.agent_id,
    title:        body.title,
    content:      body.content,
    aceType:      body.ace_type,
    aceSubtype:   body.ace_subtype,
    tags:         body.tags,
    effortStatus: body.effort_status,
    date:         body.date,
    sourceUrl:    body.source_url,
    sourceAuthor: body.source_author,
    rank:         body.rank,
  });
  res.json({ path: filePath, indexed: false });
});

router.delete('/knowledge', async (req, res) => {
  const { path } = req.body as { path: string };
  if (!path) { res.status(400).json({ error: 'path required' }); return; }
  await deleteNote(path);
  res.json({ deleted: true });
});

router.get('/search', async (req, res) => {
  const q = String(req.query['q'] ?? '');
  if (!q) { res.status(400).json({ error: 'q required' }); return; }
  const result = await searchVault(q);
  res.json({ query: q, result });
});

export default router;
```

- [ ] **Step 2: Commit**

```bash
git add game-server/routes/vault.ts
git commit -m "feat(game-server): vault routes"
```

---

## Task 12: game-server/routes/tasks.ts

**Files:**
- Create: `game-server/routes/tasks.ts`
- Create: `game-server/lib/pipeline-state.ts`

- [ ] **Step 1: Create pipeline-state.ts (in-memory store)**

```typescript
// game-server/lib/pipeline-state.ts
export interface PipelineTask {
  id: string;
  card_name: string;
  status: string;
  log: string;
  created_at: number;
  start_at: number;
  step: number;
  remaining_seconds: number;
}

const _tasks = new Map<string, PipelineTask>();

export function getTasks(): PipelineTask[] {
  const now = Date.now() / 1000;
  return [..._tasks.values()]
    .map((t) => ({
      ...t,
      remaining_seconds: t.status === 'waiting' ? Math.max(0, Math.floor(t.start_at - now)) : 0,
    }))
    .sort((a, b) => b.created_at - a.created_at);
}

export function upsertTask(task: Partial<PipelineTask> & { id: string; card_name: string }): void {
  const now = Date.now() / 1000;
  const existing = _tasks.get(task.id);
  _tasks.set(task.id, {
    status: 'waiting', log: '', step: 0,
    created_at: now, start_at: now + 180, remaining_seconds: 180,
    ...existing,
    ...task,
  } as PipelineTask);
}

export function cancelTask(taskId: string): boolean {
  const task = _tasks.get(taskId);
  if (!task) return false;
  if (['done', 'error', 'cancelled'].includes(task.status)) return false;
  task.status = 'cancelled';
  task.log    = 'Cancelado pelo usuario';
  return true;
}
```

- [ ] **Step 2: Create tasks route**

```typescript
// game-server/routes/tasks.ts
import { Router } from 'express';
import { getTasks, cancelTask } from '../lib/pipeline-state.js';

const router = Router();

router.get('/', (_req, res) => {
  res.json(getTasks());
});

router.post('/:taskId/cancel', (req, res) => {
  const ok = cancelTask(req.params.taskId);
  if (!ok) { res.status(404).json({ error: 'Task nao encontrada ou ja finalizada' }); return; }
  res.json({ ok: true });
});

export default router;
```

- [ ] **Step 3: Commit**

```bash
git add game-server/lib/pipeline-state.ts game-server/routes/tasks.ts
git commit -m "feat(game-server): pipeline tasks route + in-memory state"
```

---

## Task 13: game-server/routes/events.ts (SSE)

**Files:**
- Create: `game-server/routes/events.ts`
- Create: `game-server/lib/event-bus.ts`

- [ ] **Step 1: Create event-bus.ts**

```typescript
// game-server/lib/event-bus.ts
import { EventEmitter } from 'node:events';

export const bus = new EventEmitter();
bus.setMaxListeners(100);

export function emit(type: string, data: unknown): void {
  bus.emit('event', JSON.stringify({ type, data }));
}
```

- [ ] **Step 2: Create events route**

```typescript
// game-server/routes/events.ts
import { Router, Request, Response } from 'express';
import { bus } from '../lib/event-bus.js';

const router = Router();

router.get('/stream', (req: Request, res: Response) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('X-Accel-Buffering', 'no');
  res.flushHeaders();

  res.write(`data: ${JSON.stringify({ type: 'connected', data: 'Stream conectado' })}\n\n`);

  const onEvent = (payload: string) => res.write(`data: ${payload}\n\n`);
  bus.on('event', onEvent);

  const keepalive = setInterval(() => res.write(': keepalive\n\n'), 20_000);

  req.on('close', () => {
    bus.off('event', onEvent);
    clearInterval(keepalive);
  });
});

export default router;
```

- [ ] **Step 3: Commit**

```bash
git add game-server/lib/event-bus.ts game-server/routes/events.ts
git commit -m "feat(game-server): SSE event stream"
```

---

## Task 14: game-server/routes/chat.ts

**Files:**
- Create: `game-server/routes/chat.ts`

Workers secretario and bibliotecario each expose `POST /invoke` on their ports (3001 and 3002). The chat route calls them directly for real-time response.

- [ ] **Step 1: Write failing test**

```typescript
// game-server/routes/chat.test.ts
import { describe, it, expect, vi } from 'vitest';
import request from 'supertest';
import express from 'express';

vi.mock('node:fetch' as string, () => ({
  default: async () => ({ ok: true, json: async () => ({ reply: 'olá jogador' }) }),
}));

// Dynamic import after mock
const { default: chatRouter } = await import('./chat.js');
const app = express();
app.use(express.json());
app.use('/api/chat', chatRouter);

describe('POST /api/chat/secretario', () => {
  it('proxies to worker and returns reply', async () => {
    const res = await request(app).post('/api/chat/secretario').send({ message: 'oi' });
    expect(res.status).toBe(200);
    expect(res.body.reply).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run test — verify FAIL**

```powershell
npx vitest run routes/chat.test.ts
```

- [ ] **Step 3: Implement**

```typescript
// game-server/routes/chat.ts
import { Router } from 'express';
import { record } from '../db/messages.js';

const WORKER_PORTS: Record<string, number> = {
  secretario:   3001,
  bibliotecario: 3002,
};

const router = Router();

router.post('/:agentId', async (req, res) => {
  const { agentId } = req.params;
  const message = String((req.body as Record<string, unknown>).message ?? '').trim();

  if (!message) { res.status(400).json({ error: 'mensagem vazia' }); return; }

  const port = WORKER_PORTS[agentId];
  if (!port) { res.status(404).json({ error: `Agente sem handler de chat: ${agentId}` }); return; }

  record(DEFAULT_PATH, 'global', 'player', 'player', message);

  const workerRes = await fetch(`http://localhost:${port}/invoke`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, agentId }),
  });
  if (!workerRes.ok) { res.status(502).json({ error: 'worker error' }); return; }

  const { reply } = await workerRes.json() as { reply: string };
  record(DEFAULT_PATH, 'global', agentId, 'reply', reply);

  res.json({ reply, npc_id: agentId });
});

const DEFAULT_PATH = process.env.AGENT_DB_PATH ?? 'agent_messages.db';
export default router;
```

- [ ] **Step 4: Run test — verify PASS**

```powershell
npx vitest run routes/chat.test.ts
```

- [ ] **Step 5: Commit**

```bash
git add game-server/routes/chat.ts game-server/routes/chat.test.ts
git commit -m "feat(game-server): chat route proxies to NPC workers"
```

---

## Task 15: game-server/index.ts (main)

**Files:**
- Create: `game-server/index.ts`

- [ ] **Step 1: Write failing test**

```typescript
// game-server/index.test.ts
import { describe, it, expect } from 'vitest';
import request from 'supertest';
import { createApp } from './index.js';

const app = createApp();

describe('health', () => {
  it('GET /api/health returns ok', async () => {
    const res = await request(app).get('/api/health');
    expect(res.status).toBe(200);
    expect(res.body.status).toBe('ok');
  });
});
```

- [ ] **Step 2: Run test — verify FAIL**

```powershell
npx vitest run index.test.ts
```

- [ ] **Step 3: Implement**

```typescript
// game-server/index.ts
import express from 'express';
import cors from 'cors';
import { initSchema } from './db/messages.js';
import agentsRouter    from './routes/agents.js';
import inventoryRouter from './routes/inventory.js';
import furnitureRouter from './routes/furniture.js';
import chatRouter      from './routes/chat.js';
import vaultRouter     from './routes/vault.js';
import tasksRouter     from './routes/tasks.js';
import eventsRouter    from './routes/events.js';

export function createApp() {
  const app = express();
  app.use(cors());
  app.use(express.json({ limit: '20mb' }));

  app.get('/',          (_req, res) => res.json({ status: 'ok', service: 'be-game-server' }));
  app.get('/api/health', (_req, res) => res.json({ status: 'ok' }));

  app.use('/api/agents',        agentsRouter);
  app.use('/api/inventory',     inventoryRouter);
  app.use('/api/furniture',     furnitureRouter);
  app.use('/api/chat',          chatRouter);
  app.use('/api/vault',         vaultRouter);
  app.use('/api/planner/tasks', tasksRouter);
  app.use('/api/events',        eventsRouter);

  app.get('/api/agents/:agentId/messages', async (req, res) => {
    const { history } = await import('./db/messages.js');
    const limit = Number(req.query['limit'] ?? 200);
    const msgs  = history(process.env.AGENT_DB_PATH ?? 'agent_messages.db', req.params.agentId, limit);
    res.json({ messages: msgs });
  });

  return app;
}

const PORT = Number(process.env.PORT ?? 8000);
const app  = createApp();
initSchema();
app.listen(PORT, () => console.log(`[game-server] running on :${PORT}`));
```

- [ ] **Step 4: Run test — verify PASS**

```powershell
npx vitest run index.test.ts
```

- [ ] **Step 5: Commit**

```bash
git add game-server/index.ts game-server/index.test.ts
git commit -m "feat(game-server): Express app entry with all routes"
```

---

## Task 16: workers/package.json + tsconfig

**Files:**
- Create: `workers/package.json`
- Create: `workers/tsconfig.json`

- [ ] **Step 1: Create package.json**

```json
{
  "name": "be-game-workers",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "secretario":   "tsx workers/secretario.ts",
    "bibliotecario":"tsx workers/bibliotecario.ts",
    "planner":      "tsx workers/planner.ts",
    "copywriter":   "tsx workers/copywriter.ts",
    "designer":     "tsx workers/designer.ts",
    "dev":          "tsx workers/dev.ts",
    "qa":           "tsx workers/qa.ts",
    "devops":       "tsx workers/devops.ts",
    "test":         "vitest run"
  },
  "dependencies": {
    "@anthropic-ai/sdk": "^0.30.0",
    "express": "^5.0.0"
  },
  "devDependencies": {
    "@types/express": "^5.0.0",
    "@types/node": "^22.0.0",
    "tsx": "^4.0.0",
    "typescript": "^5.6.0",
    "vitest": "^2.0.0"
  }
}
```

- [ ] **Step 2: Create tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true
  },
  "include": ["."]
}
```

- [ ] **Step 3: Install deps**

```powershell
Set-Location workers; npm install
```

- [ ] **Step 4: Commit**

```bash
git add workers/package.json workers/tsconfig.json
git commit -m "chore: init workers package"
```

---

## Task 17: workers/shared/trello.ts + github.ts

Workers precisam de Trello e GitHub mas não podem importar de `game-server/` (pacotes separados). Adicionamos cópias em `workers/shared/`.

**Files:**
- Create: `workers/shared/trello.ts`
- Create: `workers/shared/github.ts`

- [ ] **Step 1: Create workers/shared/trello.ts**

```typescript
// workers/shared/trello.ts
const BASE = 'https://api.trello.com/1';
function auth() {
  const key = process.env.TRELLO_API_KEY;
  const token = process.env.TRELLO_TOKEN;
  if (!key || !token) throw new Error('TRELLO_API_KEY and TRELLO_TOKEN required');
  return { key, token };
}
export async function listCards(listId: string) {
  const { key, token } = auth();
  const res = await fetch(`${BASE}/lists/${listId}/cards?key=${key}&token=${token}&fields=name,desc,id`);
  if (!res.ok) throw new Error(`Trello ${res.status}`);
  return res.json() as Promise<{ id: string; name: string; desc: string }[]>;
}
export async function getCard(cardId: string) {
  const { key, token } = auth();
  const res = await fetch(`${BASE}/cards/${cardId}?key=${key}&token=${token}&fields=name,desc`);
  if (!res.ok) throw new Error(`Trello ${res.status}`);
  return res.json() as Promise<{ id: string; name: string; desc: string }>;
}
export async function moveCard(cardId: string, listId: string) {
  const { key, token } = auth();
  await fetch(`${BASE}/cards/${cardId}?key=${key}&token=${token}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ idList: listId }),
  });
}
```

- [ ] **Step 2: Create workers/shared/github.ts**

```typescript
// workers/shared/github.ts
import { execSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { join } from 'node:path';

export function pushToGitHub(projectDir: string, slug: string): string {
  const ghToken = process.env.GITHUB_TOKEN;
  const ghUser  = process.env.GITHUB_USER ?? 'omelleca';
  if (!ghToken) throw new Error('GITHUB_TOKEN required');
  if (!existsSync(join(projectDir, '.git'))) {
    execSync('git init', { cwd: projectDir });
    execSync('git add -A', { cwd: projectDir });
    execSync(`git commit -m "feat: ${slug} initial"`, { cwd: projectDir });
  }
  try {
    execSync(`gh repo create ${slug} --public --source=. --remote=origin --push`, { cwd: projectDir });
  } catch {
    const url = `https://${ghUser}:${ghToken}@github.com/${ghUser}/${slug}.git`;
    execSync(`git remote add origin ${url} || git remote set-url origin ${url}`, { cwd: projectDir });
    execSync('git push -u origin HEAD', { cwd: projectDir });
  }
  return `https://github.com/${ghUser}/${slug}`;
}
```

- [ ] **Step 3: Commit**

```bash
git add workers/shared/trello.ts workers/shared/github.ts
git commit -m "feat(workers): shared Trello + GitHub clients"
```

---

## Task 18: workers/shared/llm.ts

**Files:**
- Create: `workers/shared/llm.ts`

- [ ] **Step 1: Implement**

```typescript
// workers/shared/llm.ts
import Anthropic from '@anthropic-ai/sdk';

let _client: Anthropic | null = null;

export function getLLM(): Anthropic {
  if (!_client) {
    _client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
  }
  return _client;
}

export async function ask(system: string, userMessage: string, maxTokens = 2048): Promise<string> {
  const client = getLLM();
  const msg = await client.messages.create({
    model:      process.env.AGENT_MODEL ?? 'claude-sonnet-4-6',
    max_tokens: maxTokens,
    system,
    messages:   [{ role: 'user', content: userMessage }],
  });
  const block = msg.content[0];
  return block.type === 'text' ? block.text : '';
}
```

- [ ] **Step 2: Commit**

```bash
git add workers/shared/llm.ts
git commit -m "feat(workers): Anthropic LLM client"
```

---

## Task 18: workers/shared/base-worker.ts

**Files:**
- Create: `workers/shared/base-worker.ts`

Each worker extends this. Exposes:
- `POST /heartbeat` — called by Paperclip with `{ task_id, description, context }`
- `POST /invoke` — called by game-server directly for real-time chat

- [ ] **Step 1: Implement**

```typescript
// workers/shared/base-worker.ts
import express, { Router } from 'express';

export interface HeartbeatPayload {
  task_id: string;
  description: string;
  context?: Record<string, unknown>;
}

export interface InvokePayload {
  message: string;
  agentId: string;
}

export interface WorkerConfig {
  name: string;
  port: number;
  onHeartbeat: (payload: HeartbeatPayload) => Promise<string>;
  onInvoke:    (payload: InvokePayload)    => Promise<string>;
}

export function startWorker(config: WorkerConfig): void {
  const app = express();
  app.use(express.json());

  app.get('/health', (_req, res) => res.json({ worker: config.name, status: 'ok' }));

  app.post('/heartbeat', async (req, res) => {
    const payload = req.body as HeartbeatPayload;
    try {
      const result = await config.onHeartbeat(payload);
      res.json({ task_id: payload.task_id, status: 'completed', result });
    } catch (err) {
      res.status(500).json({ task_id: payload.task_id, status: 'failed', error: String(err) });
    }
  });

  app.post('/invoke', async (req, res) => {
    const payload = req.body as InvokePayload;
    try {
      const reply = await config.onInvoke(payload);
      res.json({ reply });
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  app.listen(config.port, () =>
    console.log(`[${config.name}] worker running on :${config.port}`),
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add workers/shared/base-worker.ts
git commit -m "feat(workers): base HTTP worker template"
```

---

## Task 19: workers/secretario.ts

**Files:**
- Create: `workers/secretario.ts`

Secretário: responde perguntas do jogador sobre o status do pipeline. Chama `GET http://localhost:8000/api/planner/tasks` para obter dados reais.

- [ ] **Step 1: Implement**

```typescript
// workers/secretario.ts
import { startWorker } from './shared/base-worker.js';
import { ask } from './shared/llm.js';

const SYSTEM = `Você é o Secretário da Black Elephant. Tem visão completa do pipeline.
Responde em português brasileiro, factual, 1-3 frases. Se não souber, diz "sem info no momento".`;

async function getPipelineContext(): Promise<string> {
  try {
    const res   = await fetch('http://localhost:8000/api/planner/tasks');
    const tasks = await res.json() as { card_name: string; status: string; step: number; log: string }[];
    if (!tasks.length) return 'Nenhuma task ativa no momento.';
    return tasks.slice(0, 5).map((t) =>
      `- "${t.card_name}" [${t.status}] etapa ${t.step}: ${t.log}`,
    ).join('\n');
  } catch {
    return 'Pipeline indisponível no momento.';
  }
}

startWorker({
  name: 'secretario',
  port: 3001,

  onHeartbeat: async (payload) => {
    const context = await getPipelineContext();
    return ask(SYSTEM, `Contexto do pipeline:\n${context}\n\nTarefa: ${payload.description}`);
  },

  onInvoke: async (payload) => {
    const context = await getPipelineContext();
    return ask(SYSTEM, `Contexto do pipeline:\n${context}\n\nJogador perguntou: ${payload.message}`);
  },
});
```

- [ ] **Step 2: Start and smoke-test**

```powershell
Set-Location workers; npx tsx secretario.ts
```

In another terminal:
```powershell
Invoke-RestMethod -Uri http://localhost:3001/health
```

Expected: `{ worker: "secretario", status: "ok" }`

- [ ] **Step 3: Commit**

```bash
git add workers/secretario.ts
git commit -m "feat(workers): secretario NPC worker"
```

---

## Task 20: workers/bibliotecario.ts

**Files:**
- Create: `workers/bibliotecario.ts`

- [ ] **Step 1: Implement**

```typescript
// workers/bibliotecario.ts
import { startWorker } from './shared/base-worker.js';
import { ask } from './shared/llm.js';

const SYSTEM = `Você é o Bibliotecário da Black Elephant. Conhece o vault Ideaverse de cor.
Responde em português brasileiro. Cita a fonte (path da nota) quando aplicável.`;

async function searchVaultRemote(query: string): Promise<string> {
  try {
    const url = `http://localhost:8000/api/vault/search?q=${encodeURIComponent(query)}`;
    const res = await fetch(url);
    const { result } = await res.json() as { result: string };
    return result;
  } catch {
    return 'Vault indisponível no momento.';
  }
}

startWorker({
  name: 'bibliotecario',
  port: 3002,

  onHeartbeat: async (payload) => {
    const context = await searchVaultRemote(payload.description.slice(0, 100));
    return ask(SYSTEM, `Contexto do vault:\n${context}\n\nTarefa: ${payload.description}`);
  },

  onInvoke: async (payload) => {
    const context = await searchVaultRemote(payload.message);
    return ask(SYSTEM, `Contexto do vault:\n${context}\n\nJogador perguntou: ${payload.message}`);
  },
});
```

- [ ] **Step 2: Smoke-test**

```powershell
npx tsx bibliotecario.ts
# outro terminal:
Invoke-RestMethod -Uri http://localhost:3002/health
```

Expected: `{ worker: "bibliotecario", status: "ok" }`

- [ ] **Step 3: Commit**

```bash
git add workers/bibliotecario.ts
git commit -m "feat(workers): bibliotecario NPC worker"
```

---

## Task 21: workers/planner.ts

**Files:**
- Create: `workers/planner.ts`

Planner: poll Trello a cada 60s, detecta novos cards, cria tasks no Paperclip e atualiza pipeline-state no game-server.

- [ ] **Step 1: Implement**

```typescript
// workers/planner.ts
import { startWorker } from './shared/base-worker.js';
import { ask } from './shared/llm.js';
import { listCards, getCard } from './shared/trello.js';

const SYSTEM = `Você é o Gerente de Projetos da Black Elephant.
Analisa cards do Trello e descreve claramente o que precisa ser feito.
Responde em português brasileiro, objetivo.`;

const SEEN = new Set<string>();
let polling = false;

async function notifyGameServer(task: { id: string; card_name: string; status: string; log: string; step: number }): Promise<void> {
  try {
    await fetch('http://localhost:8000/api/planner/tasks/upsert', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(task),
    });
  } catch { /* game-server may not be up */ }
}

async function pollTrello(): Promise<void> {
  const listId = process.env.TRELLO_LIST_ID;
  if (!listId) return;

  const cards = await listCards(listId);
  for (const card of cards) {
    if (SEEN.has(card.id)) continue;
    SEEN.add(card.id);

    console.log(`[planner] novo card: "${card.name}"`);
    await notifyGameServer({
      id: card.id, card_name: card.name,
      status: 'waiting', log: 'Aguardando 180s antes de executar', step: 0,
    });

    setTimeout(async () => {
      const fresh = await getCard(card.id);
      await notifyGameServer({ id: fresh.id, card_name: fresh.name, status: 'planning', log: 'Planner analisando', step: 1 });
      // Paperclip will dispatch the downstream agents via heartbeat
      console.log(`[planner] card "${fresh.name}" pronto para pipeline`);
    }, 180_000);
  }
}

if (!polling) {
  polling = true;
  setInterval(pollTrello, 60_000);
  pollTrello().catch(console.error);
}

startWorker({
  name: 'planner',
  port: 3003,

  onHeartbeat: async (payload) => {
    return ask(SYSTEM, `Analise e descreva o que precisa ser feito:\n${payload.description}`);
  },

  onInvoke: async (payload) => {
    const listId = process.env.TRELLO_LIST_ID ?? '';
    const cards  = listId ? await listCards(listId) : [];
    const context = cards.length
      ? cards.map((c) => `- ${c.name}`).join('\n')
      : 'Nenhum card no momento.';
    return ask(SYSTEM, `Cards no Trello:\n${context}\n\nPergunta: ${payload.message}`);
  },
});
```

- [ ] **Step 2: Add upsert route to game-server/routes/tasks.ts**

Open `game-server/routes/tasks.ts` and add:

```typescript
import { upsertTask } from '../lib/pipeline-state.js';

// Add after existing routes:
router.post('/upsert', (req, res) => {
  const task = req.body as Parameters<typeof upsertTask>[0];
  upsertTask(task);
  res.json({ ok: true });
});
```

- [ ] **Step 3: Commit**

```bash
git add workers/planner.ts game-server/routes/tasks.ts
git commit -m "feat(workers): planner polls Trello + notifies game-server"
```

---

## Task 22: workers/copywriter.ts

**Files:**
- Create: `workers/copywriter.ts`

- [ ] **Step 1: Implement**

```typescript
// workers/copywriter.ts
import { startWorker } from './shared/base-worker.js';
import { ask } from './shared/llm.js';
const SYSTEM = `Você é um Copywriter sênior da Black Elephant, especializado em landing pages.
Cria textos persuasivos em Markdown: headline, hero, benefícios (3-5), como funciona, CTA, FAQ.
Consulte contexto do vault quando fornecido. Escreva em português brasileiro.`;

async function saveToVault(slug: string, content: string): Promise<void> {
  await fetch('http://localhost:8000/api/vault/knowledge', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      agent_id: 'copywriter', title: `${slug}-copy`,
      content, ace_type: 'atlas', ace_subtype: 'notes',
      tags: ['copy', 'landing-page'],
    }),
  });
}

startWorker({
  name: 'copywriter',
  port: 3004,

  onHeartbeat: async (payload) => {
    const copy = await ask(SYSTEM, payload.description, 4096);
    const slug = String((payload.context?.['slug'] as string | undefined) ?? 'sem-slug');
    await saveToVault(slug, copy).catch(console.error);
    return copy;
  },

  onInvoke: async (payload) => {
    return ask(SYSTEM, payload.message, 2048);
  },
});
```

- [ ] **Step 2: Commit**

```bash
git add workers/copywriter.ts
git commit -m "feat(workers): copywriter agent"
```

---

## Task 23: workers/designer.ts

**Files:**
- Create: `workers/designer.ts`

- [ ] **Step 1: Implement**

```typescript
// workers/designer.ts
import { startWorker } from './shared/base-worker.js';
import { ask } from './shared/llm.js';
const SYSTEM = `Você é o UI/UX Designer e Diretor de Arte da Black Elephant.
A partir da copy recebida, cria um guia visual completo em Markdown:
paleta de cores (hex), tipografia (Google Fonts), mood/estética, estrutura de layout por seção,
componentes e animações sugeridas (GSAP). Escreva em português brasileiro.`;

async function saveGuideToVault(slug: string, content: string): Promise<void> {
  await fetch('http://localhost:8000/api/vault/knowledge', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      agent_id: 'designer', title: `${slug}-visual-guide`,
      content, ace_type: 'resources', tags: ['design', 'visual-guide'],
    }),
  });
}

startWorker({
  name: 'designer',
  port: 3005,

  onHeartbeat: async (payload) => {
    const guide = await ask(SYSTEM, payload.description, 4096);
    const slug  = String((payload.context?.['slug'] as string | undefined) ?? 'sem-slug');
    await saveGuideToVault(slug, guide).catch(console.error);
    return guide;
  },

  onInvoke: async (payload) => ask(SYSTEM, payload.message, 2048),
});
```

- [ ] **Step 2: Commit**

```bash
git add workers/designer.ts
git commit -m "feat(workers): designer agent"
```

---

## Task 24: workers/dev.ts

**Files:**
- Create: `workers/dev.ts`

Dev: abre Claude Code CLI em uma pasta de projeto.

- [ ] **Step 1: Implement**

```typescript
// workers/dev.ts
import { startWorker } from './shared/base-worker.js';
import { ask } from './shared/llm.js';
import { spawnSync } from 'node:child_process';
import { mkdirSync, existsSync } from 'node:fs';
import { join } from 'node:path';

const SYSTEM = `Você é um Desenvolvedor Full-Stack da Black Elephant especializado em sites imersivos.
Recebe um briefing e descreve o que o Claude Code CLI deve implementar.
Escreva prompts técnicos em inglês para o Claude Code. Responda em português brasileiro.`;

const BASE_DIR = process.env.PROJECTS_BASE_DIR ?? 'C:/Users/v27me/Videos';

startWorker({
  name: 'dev',
  port: 3006,

  onHeartbeat: async (payload) => {
    const slug       = String((payload.context?.['slug'] as string | undefined) ?? 'projeto');
    const projectDir = join(BASE_DIR, slug);
    if (!existsSync(projectDir)) mkdirSync(projectDir, { recursive: true });

    const prompt = await ask(SYSTEM,
      `Gere um prompt técnico completo em inglês para o Claude Code implementar:\n${payload.description}`,
      2048,
    );

    const result = spawnSync(
      'claude', ['--print', prompt],
      { cwd: projectDir, encoding: 'utf-8', timeout: 300_000 },
    );

    if (result.error) throw result.error;
    return result.stdout ?? 'Dev concluído';
  },

  onInvoke: async (payload) => ask(SYSTEM, payload.message),
});
```

- [ ] **Step 2: Commit**

```bash
git add workers/dev.ts
git commit -m "feat(workers): dev agent via Claude Code CLI"
```

---

## Task 25: workers/qa.ts

**Files:**
- Create: `workers/qa.ts`

- [ ] **Step 1: Implement**

```typescript
// workers/qa.ts
import { startWorker } from './shared/base-worker.js';
import { ask } from './shared/llm.js';
import { readdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';

const SYSTEM = `Você é um QA meticuloso da Black Elephant.
Analisa o código do projeto com checklist:
1. HTML: doctype, meta viewport, title, charset
2. Sem texto hardcoded em inglês (exceto código)
3. Dependências externas declaradas
4. README presente
Emite STATUS: APROVADO ou STATUS: REPROVADO com justificativa.
Responde em português brasileiro com relatório estruturado.`;

async function readProjectFiles(projectDir: string): Promise<string> {
  try {
    const entries = await readdir(projectDir);
    const parts: string[] = [`Arquivos: ${entries.join(', ')}`];
    for (const file of ['index.html', 'README.md']) {
      try {
        const content = await readFile(join(projectDir, file), 'utf-8');
        parts.push(`\n--- ${file} (primeiros 500 chars) ---\n${content.slice(0, 500)}`);
      } catch { /* skip */ }
    }
    return parts.join('\n');
  } catch {
    return `Pasta ${projectDir} não encontrada.`;
  }
}

startWorker({
  name: 'qa',
  port: 3007,

  onHeartbeat: async (payload) => {
    const slug       = String((payload.context?.['slug'] as string | undefined) ?? '');
    const projectDir = slug
      ? join(process.env.PROJECTS_BASE_DIR ?? 'C:/Users/v27me/Videos', slug)
      : '';
    const files = projectDir ? await readProjectFiles(projectDir) : payload.description;
    return ask(SYSTEM, `Projeto: ${slug}\n\n${files}`, 2048);
  },

  onInvoke: async (payload) => ask(SYSTEM, payload.message),
});
```

- [ ] **Step 2: Commit**

```bash
git add workers/qa.ts
git commit -m "feat(workers): QA agent"
```

---

## Task 26: workers/devops.ts

**Files:**
- Create: `workers/devops.ts`

- [ ] **Step 1: Implement**

```typescript
// workers/devops.ts
import { startWorker } from './shared/base-worker.js';
import { ask } from './shared/llm.js';
import { pushToGitHub } from './shared/github.js';
import { join } from 'node:path';

const SYSTEM = `Você é o Engenheiro DevOps da Black Elephant.
Nunca deixa código sem versionamento. Reporta a URL do repositório criado.
Responde em português brasileiro.`;

startWorker({
  name: 'devops',
  port: 3008,

  onHeartbeat: async (payload) => {
    const slug       = String((payload.context?.['slug'] as string | undefined) ?? '');
    if (!slug) return ask(SYSTEM, payload.description);

    const projectDir = join(process.env.PROJECTS_BASE_DIR ?? 'C:/Users/v27me/Videos', slug);
    const url        = pushToGitHub(projectDir, slug);
    return `Repositório criado: ${url}`;
  },

  onInvoke: async (payload) => ask(SYSTEM, payload.message),
});
```

- [ ] **Step 2: Commit**

```bash
git add workers/devops.ts
git commit -m "feat(workers): devops agent pushes to GitHub"
```

---

## Task 27: Delete Python files

- [ ] **Step 1: Delete root Python files**

```powershell
Remove-Item "agents.py","tasks.py","main.py","planner_main.py","trello_tool.py" -ErrorAction SilentlyContinue
```

- [ ] **Step 2: Delete server/ directory**

```powershell
Remove-Item -Recurse -Force "server\"
```

- [ ] **Step 3: Delete crewai-studio**

```powershell
Remove-Item -Recurse -Force "supabase\Usersv27mecrewai-studio\"
```

- [ ] **Step 4: Delete Python test files**

```powershell
Remove-Item -Recurse -Force "tests\"
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: remove CrewAI + Python server (migrated to Paperclip + TypeScript)"
```

---

## Task 28: Update vite.config.ts + smoke test

**Files:**
- Modify: `vite.config.ts`

The Vite proxy already points to port 8000 — no change needed. Verify everything runs.

- [ ] **Step 1: Verify vite.config.ts proxy target**

Confirm `target: "http://localhost:8000"` is already set. No change needed.

- [ ] **Step 2: Start all services**

Open 4 terminals:

```powershell
# Terminal 1 — game server
Set-Location "C:\Users\v27me\Videos\be-game\game-server"; npx tsx index.ts

# Terminal 2 — secretario worker
Set-Location "C:\Users\v27me\Videos\be-game\workers"; npx tsx secretario.ts

# Terminal 3 — bibliotecario worker
Set-Location "C:\Users\v27me\Videos\be-game\workers"; npx tsx bibliotecario.ts

# Terminal 4 — Vite (game)
Set-Location "C:\Users\v27me\Videos\be-game"; npm run dev
```

- [ ] **Step 3: Verify endpoints**

```powershell
Invoke-RestMethod http://localhost:8000/api/health
# Expected: { status: "ok" }

Invoke-RestMethod http://localhost:8000/api/agents
# Expected: array of agents from Supabase

Invoke-RestMethod http://localhost:3001/health
# Expected: { worker: "secretario", status: "ok" }

Invoke-RestMethod http://localhost:3002/health
# Expected: { worker: "bibliotecario", status: "ok" }
```

- [ ] **Step 4: Test NPC chat**

```powershell
Invoke-RestMethod -Uri http://localhost:8000/api/chat/secretario `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"message":"oi, tem algo no pipeline?"}'
# Expected: { reply: "...", npc_id: "secretario" }
```

- [ ] **Step 5: Register workers in Paperclip UI**

Open Paperclip UI → Add Company "Black Elephant" → Add Employees:
- Secretário: HTTP webhook → `http://localhost:3001`
- Bibliotecário: HTTP webhook → `http://localhost:3002`
- Planner: HTTP webhook → `http://localhost:3003`
- Copywriter: HTTP webhook → `http://localhost:3004`
- Designer: HTTP webhook → `http://localhost:3005`
- Dev: HTTP webhook → `http://localhost:3006`
- QA: HTTP webhook → `http://localhost:3007`
- DevOps: HTTP webhook → `http://localhost:3008`

Configure LLM no painel Paperclip (você fará isso manualmente).

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "feat: complete migration to Paperclip AI + TypeScript game-server + workers"
```

---

## Env vars necessárias (.env)

```env
# Supabase
SUPABASE_URL=
SUPABASE_ANON_KEY=

# Trello
TRELLO_API_KEY=
TRELLO_TOKEN=
TRELLO_LIST_ID=
TRELLO_DONE_LIST_ID=

# GitHub
GITHUB_TOKEN=
GITHUB_USER=omelleca

# Anthropic (para workers)
ANTHROPIC_API_KEY=

# Paths
OBSIDIAN_VAULT_PATH=C:/Users/v27me/Documents/Ideaverse
AGENT_DB_PATH=agent_messages.db
PROJECTS_BASE_DIR=C:/Users/v27me/Videos

# Worker ports (defaults definidos no código)
# secretario=3001, bibliotecario=3002, planner=3003
# copywriter=3004, designer=3005, dev=3006, qa=3007, devops=3008
```
