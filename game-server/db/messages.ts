import Database from 'better-sqlite3';

const DEFAULT_PATH = process.env.AGENT_DB_PATH ?? 'agent_messages.db';
const _dbCache = new Map<string, Database.Database>();

function getDb(path = DEFAULT_PATH): Database.Database {
  const existing = _dbCache.get(path);
  if (existing) return existing;
  const db = new Database(path);
  _dbCache.set(path, db);
  return db;
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
