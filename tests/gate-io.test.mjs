import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const SCRIPT = fileURLToPath(new URL('../pieces/wfos-core/scripts/gate.mjs', import.meta.url));

function run(platform, payload) {
  return spawnSync(process.execPath, [SCRIPT, `--platform=${platform}`], {
    input: JSON.stringify(payload), encoding: 'utf8', timeout: 5000,
  });
}

const bash = (command) => ({ tool_name: 'Bash', tool_input: { command } });

test('claude: 命中 ask 规则 → stdout JSON + exit 0', () => {
  const r = run('claude', bash('git push --force origin main'));
  assert.equal(r.status, 0);
  const out = JSON.parse(r.stdout);
  assert.equal(out.hookSpecificOutput.hookEventName, 'PreToolUse');
  assert.equal(out.hookSpecificOutput.permissionDecision, 'ask');
  assert.match(out.hookSpecificOutput.permissionDecisionReason, /force-push-protected/);
});

test('claude: 未命中 → 无输出 + exit 0', () => {
  const r = run('claude', bash('git status'));
  assert.equal(r.status, 0);
  assert.equal(r.stdout.trim(), '');
});

test('codex: deny 规则 → stderr 理由 + exit 2', () => {
  const r = run('codex', bash('git push --force origin main'));
  assert.equal(r.status, 2);
  assert.match(r.stderr, /force-push-protected/);
  assert.equal(r.stdout.trim(), '');
});

test('codex: native 规则 → 不裁决,exit 0', () => {
  const r = run('codex', bash('git reset --hard HEAD~1'));
  assert.equal(r.status, 0);
  assert.equal(r.stdout.trim(), '');
  assert.equal(r.stderr.trim(), '');
});

test('坏 payload → exit 0(fail-open)', () => {
  const r = spawnSync(process.execPath, [SCRIPT, '--platform=claude'], { input: 'not json', encoding: 'utf8' });
  assert.equal(r.status, 0);
});
