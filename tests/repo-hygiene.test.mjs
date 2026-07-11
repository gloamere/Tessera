import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

function* walk(dir) {
  for (const e of readdirSync(dir)) {
    if (['node_modules', '.git', '.beads', '.superpowers'].includes(e)) continue;
    const p = join(dir, e);
    if (statSync(p).isDirectory()) yield* walk(p);
    else yield p;
  }
}

test('所有 JSON/MD/YAML 无 BOM', () => {
  for (const f of walk(root)) {
    if (!/\.(json|md|ya?ml)$/.test(f)) continue;
    const buf = readFileSync(f);
    assert.ok(!(buf[0] === 0xef && buf[1] === 0xbb && buf[2] === 0xbf), `BOM found: ${f}`);
  }
});

test('联网 bootstrap 固定版本且不使用远程 pipe 执行', () => {
  const bootstrap = readFileSync(join(root, 'scripts', 'bootstrap-machine.ps1'), 'utf8');
  assert.match(bootstrap, /v2\.0\.0-beta\.1/);
  assert.match(bootstrap, /Refusing to overwrite/);
  assert.doesNotMatch(bootstrap, /Invoke-Expression|\biex\b/i);
  assert.match(bootstrap, /InstallCodexPlugin/);
});

test('两份市集清单的拼图名与版本和 plugin.json 一致', () => {
  const claude = JSON.parse(readFileSync(join(root, '.claude-plugin/marketplace.json'), 'utf8'));
  const codex = JSON.parse(readFileSync(join(root, '.agents/plugins/marketplace.json'), 'utf8'));
  assert.deepEqual(claude.plugins.map((p) => p.name).sort(), codex.plugins.map((p) => p.name).sort());
  for (const entry of claude.plugins) {
    const manifest = JSON.parse(readFileSync(join(root, entry.source, '.claude-plugin/plugin.json'), 'utf8'));
    assert.equal(manifest.version, entry.version, `${entry.name} 版本漂移`);
    const codexManifest = JSON.parse(readFileSync(join(root, entry.source, '.codex-plugin/plugin.json'), 'utf8'));
    assert.equal(codexManifest.version, entry.version, `${entry.name} codex manifest 版本漂移`);
    const codexEntry = codex.plugins.find((p) => p.name === entry.name);
    assert.equal(codexEntry.policy?.installation, 'AVAILABLE');
    assert.equal(codexEntry.policy?.authentication, 'ON_INSTALL');
    assert.ok(typeof codexEntry.category === 'string' && codexEntry.category !== '');
    assert.equal(codexEntry.source.path, entry.source, `${entry.name} 两市集 source 路径漂移`);
  }
});
