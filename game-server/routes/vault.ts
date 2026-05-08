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
