import { describe, it, expect } from 'vitest';
import { buildFrontmatter, vaultFilePath } from './vault.js';

describe('vault helpers', () => {
  it('builds YAML frontmatter with agent tag', () => {
    const fm = buildFrontmatter({ agentId: 'copywriter', aceType: 'atlas', tags: ['test'] });
    expect(fm).toContain('agent: copywriter');
    expect(fm).toContain('- agente');
    expect(fm).toContain('- copywriter');
  });

  it('resolves atlas/notes path', () => {
    const p = vaultFilePath('/vault', {
      agentId: 'copywriter', title: 'Minha Nota',
      aceType: 'atlas', aceSubtype: 'notes',
    });
    expect(p).toContain('Atlas');
    expect(p).toContain('Copywriter');
    expect(p).toContain('Minha Nota.md');
  });

  it('resolves atlas/moc path', () => {
    const p = vaultFilePath('/vault', {
      agentId: 'planner', title: 'Projeto MOC',
      aceType: 'atlas', aceSubtype: 'moc',
    });
    expect(p).toContain('Maps');
    expect(p).toContain('Projeto MOC MOC.md');
  });
});
