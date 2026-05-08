import { describe, it, expect } from 'vitest';
import request from 'supertest';
import { createApp } from './index.js';

const app = createApp();

describe('game-server health', () => {
  it('GET /api/health returns ok', async () => {
    const res = await request(app).get('/api/health');
    expect(res.status).toBe(200);
    expect(res.body.status).toBe('ok');
  });

  it('GET / returns service name', async () => {
    const res = await request(app).get('/');
    expect(res.status).toBe(200);
    expect(res.body.service).toBe('be-game-server');
  });
});
