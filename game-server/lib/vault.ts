import { readdir, readFile, writeFile, mkdir, unlink, stat } from 'node:fs/promises';
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
      const s = await stat(full);
      if (s.isDirectory()) await _walkMd(full, fn);
      else if (entry.endsWith('.md')) await fn(full);
    } catch { /* skip */ }
  }
}
