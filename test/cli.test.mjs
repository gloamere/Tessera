import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, existsSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

test('init preview does not write files', () => {
  const dir = mkdtempSync(join(tmpdir(), 'workflow-os-'));
  const cli = join(process.cwd(), 'bin', 'workflow-os.mjs');
  execFileSync(process.execPath, [cli, 'init', '--codex', '--obsidian', '--dry-run'], { cwd: dir });
  assert.equal(existsSync(join(dir, 'docs')), false);
});

test('init creates portable project files', () => {
  const dir = mkdtempSync(join(tmpdir(), 'workflow-os-'));
  const cli = join(process.cwd(), 'bin', 'workflow-os.mjs');
  execFileSync(process.execPath, [cli, 'init', '--codex'], { cwd: dir });
  assert.equal(existsSync(join(dir, '.workflow', 'templates', 'ui-brief.md')), true);
  assert.equal(existsSync(join(dir, 'docs', 'NOW.md')), true);
  assert.equal(existsSync(join(dir, 'AGENTS.md')), true);
});

test('Superpowers adapter records an update candidate without installing or changing project rules', () => {
  const dir = mkdtempSync(join(tmpdir(), 'workflow-os-'));
  const cli = join(process.cwd(), 'bin', 'workflow-os.mjs');
  execFileSync(process.execPath, [cli, 'init', '--codex'], { cwd: dir });
  execFileSync(process.execPath, [cli, 'adapter', 'check', 'superpowers', '--version', 'v6.1.1', '--release-url', 'https://github.com/obra/superpowers/releases/tag/v6.1.1'], { cwd: dir });
  const output = execFileSync(process.execPath, [cli, 'adapter', 'status', 'superpowers', '--json'], { cwd: dir, encoding: 'utf8' });
  const status = JSON.parse(output);
  assert.equal(status.adapters[0].state.available_version, 'v6.1.1');
  assert.equal(status.adapters[0].state.action, 'awaiting_user_confirmation');
  assert.equal(existsSync(join(dir, '.workflow', 'extensions', 'superpowers', 'README.md')), true);
  assert.match(readFileSync(join(dir, '.workflow', 'manifest.yaml'), 'utf8'), /superpowers/);
});

test('adapter doctor detects tools without downloading or installing them', () => {
  const dir = mkdtempSync(join(tmpdir(), 'workflow-os-'));
  const cli = join(process.cwd(), 'bin', 'workflow-os.mjs');
  execFileSync(process.execPath, [cli, 'init'], { cwd: dir });
  const output = execFileSync(process.execPath, [cli, 'adapter', 'doctor', '--json'], { cwd: dir, encoding: 'utf8' });
  const status = JSON.parse(output);
  assert.ok(['available', 'missing'].includes(status.markitdown.availability));
  assert.ok(['available', 'missing'].includes(status.superpowers.availability));
  assert.equal(existsSync(join(dir, '.workflow', 'runtime', 'adapters.json')), true);
  assert.match(readFileSync(join(dir, '.workflow', 'adapters.yaml'), 'utf8'), /id: markitdown/);
  assert.equal(existsSync(join(dir, 'docs', 'sources', 'README.md')), true);
});
