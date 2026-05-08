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
