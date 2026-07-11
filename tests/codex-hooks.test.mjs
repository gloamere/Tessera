import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const HOOKS = fileURLToPath(new URL('../pieces/wfos-core/hooks/codex.hooks.json', import.meta.url));

test('Codex hooks guard Bash before execution and retain PermissionRequest fallback', () => {
  const hooks = JSON.parse(readFileSync(HOOKS, 'utf8')).hooks;
  assert.equal(hooks.PreToolUse[0].matcher, '^Bash$');
  assert.equal(hooks.PermissionRequest[0].matcher, '^Bash$');
  for (const event of ['PreToolUse', 'PermissionRequest']) {
    const handler = hooks[event][0].hooks[0];
    assert.match(handler.command, /\$\{PLUGIN_ROOT\}/);
    assert.match(handler.command, new RegExp(`--event=${event}`));
    assert.match(handler.commandWindows, /\$env:PLUGIN_ROOT/);
    assert.match(handler.commandWindows, new RegExp(`--event=${event}`));
  }
});
