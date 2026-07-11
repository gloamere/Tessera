import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const SCRIPT = fileURLToPath(new URL('../scripts/init-project.mjs', import.meta.url));

function run(target, ...args) {
  return execFileSync(process.execPath, [SCRIPT, '--target', target, ...args], { encoding: 'utf8' });
}

test('init-project creates only the missing project workflow files', () => {
  const root = mkdtempSync(join(tmpdir(), 'workflow-os-project-'));
  mkdirSync(join(root, 'docs'), { recursive: true });
  writeFileSync(join(root, 'docs', 'PROJECT.md'), '# Existing project\n');
  writeFileSync(join(root, 'AGENTS.md'), '# Human rules\n');
  run(root, '--name', 'Test Project');
  assert.equal(readFileSync(join(root, 'docs', 'PROJECT.md'), 'utf8'), '# Existing project\n');
  assert.equal(existsSync(join(root, '.workflow-os', 'project.yaml')), true);
  assert.equal(existsSync(join(root, 'docs', 'research', 'README.md')), true);
  const guidance = readFileSync(join(root, 'AGENTS.md'), 'utf8');
  assert.match(guidance, /# Human rules/);
  assert.match(guidance, /workflow-os:v2:start/);
  const repeat = run(root, '--name', 'Test Project');
  assert.match(repeat, /skip/);
});

test('init-project dry-run does not write files', () => {
  const root = mkdtempSync(join(tmpdir(), 'workflow-os-project-'));
  const output = run(root, '--dry-run');
  assert.match(output, /Preview/);
  assert.equal(existsSync(join(root, 'docs')), false);
  assert.equal(existsSync(join(root, 'AGENTS.md')), false);
});
