// workers/shared/base-worker.ts
import express from 'express';

export interface HeartbeatPayload {
  task_id:     string;
  run_id?:     string;
  description: string;
  context?:    Record<string, unknown>;
  agent_id?:   string;
  company_id?: string;
}

export interface InvokePayload {
  message: string;
  agentId: string;
}

export interface WorkerConfig {
  name:        string;
  port:        number;
  apiKey?:     string;
  onHeartbeat: (payload: HeartbeatPayload) => Promise<string>;
  onInvoke:    (payload: InvokePayload)    => Promise<string>;
}

/** Call Paperclip REST API authenticated as this agent */
export async function callPaperclip(
  path: string,
  method: 'GET' | 'POST' | 'PATCH',
  body: unknown,
  apiKey: string,
): Promise<unknown> {
  const base = (process.env.PAPERCLIP_API_URL ?? 'http://localhost:3100').replace(/\/$/, '');
  const res  = await fetch(`${base}${path}`, {
    method,
    headers: {
      'Content-Type':  'application/json',
      'Authorization': `Bearer ${apiKey}`,
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Paperclip ${method} ${path} → ${res.status}`);
  return res.json();
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
