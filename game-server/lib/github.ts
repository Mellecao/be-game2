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
