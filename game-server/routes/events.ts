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
