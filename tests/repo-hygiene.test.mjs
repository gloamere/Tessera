import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

function* walk(dir) {
  for (const e of readdirSync(dir)) {
    if (['node_modules', '.git', '.beads'].includes(e)) continue;
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

test('两份市集清单的拼图名与版本和 plugin.json 一致', () => {
  const claude = JSON.parse(readFileSync(join(root, '.claude-plugin/marketplace.json'), 'utf8'));
  const codex = JSON.parse(readFileSync(join(root, '.agents/plugins/marketplace.json'), 'utf8'));
  assert.deepEqual(claude.plugins.map((p) => p.name).sort(), codex.plugins.map((p) => p.name).sort());
  for (const entry of claude.plugins) {
    const manifest = JSON.parse(readFileSync(join(root, entry.source, '.claude-plugin/plugin.json'), 'utf8'));
    assert.equal(manifest.version, entry.version, `${entry.name} 版本漂移`);
    const codexManifest = JSON.parse(readFileSync(join(root, entry.source, '.codex-plugin/plugin.json'), 'utf8'));
    assert.equal(codexManifest.version, entry.version, `${entry.name} codex manifest 版本漂移`);
  }
});
