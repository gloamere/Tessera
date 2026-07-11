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
  const r = run('claude', bash('git reset --hard HEAD~1'));
  assert.equal(r.status, 0);
  const out = JSON.parse(r.stdout);
  assert.equal(out.hookSpecificOutput.hookEventName, 'PreToolUse');
  assert.equal(out.hookSpecificOutput.permissionDecision, 'ask');
  assert.match(out.hookSpecificOutput.permissionDecisionReason, /discard-changes/);
});

test('claude: deny 规则 → stdout JSON(permissionDecision deny)+ exit 0', () => {
  const r = run('claude', bash('git push --force origin main'));
  assert.equal(r.status, 0);
  const out = JSON.parse(r.stdout);
  assert.equal(out.hookSpecificOutput.hookEventName, 'PreToolUse');
  assert.equal(out.hookSpecificOutput.permissionDecision, 'deny');
  assert.match(out.hookSpecificOutput.permissionDecisionReason, /force-push-protected/);
});

test('claude: 未命中 → 无输出 + exit 0', () => {
  const r = run('claude', bash('git status'));
  assert.equal(r.status, 0);
  assert.equal(r.stdout.trim(), '');
});

test('codex PreToolUse: deny 规则 → stdout deny JSON + exit 0', () => {
  const r = run('codex', bash('git push --force origin main'));
  assert.equal(r.status, 0);
  const out = JSON.parse(r.stdout);
  assert.equal(out.hookSpecificOutput.hookEventName, 'PreToolUse');
  assert.equal(out.hookSpecificOutput.permissionDecision, 'deny');
  assert.match(out.hookSpecificOutput.permissionDecisionReason, /force-push-protected/);
  assert.equal(r.stderr.trim(), '');
});

test('codex PreToolUse: native 规则 → 不裁决,exit 0', () => {
  const r = run('codex', bash('git reset --hard HEAD~1'));
  assert.equal(r.status, 0);
  assert.equal(r.stdout.trim(), '');
  assert.equal(r.stderr.trim(), '');
});

test('codex PermissionRequest: deny 规则 → PermissionRequest deny JSON + exit 0', () => {
  const r = spawnSync(process.execPath, [SCRIPT, '--platform=codex', '--event=PermissionRequest'], {
    input: JSON.stringify(bash('git push --force origin main')), encoding: 'utf8', timeout: 5000,
  });
  assert.equal(r.status, 0);
  const out = JSON.parse(r.stdout);
  assert.equal(out.hookSpecificOutput.hookEventName, 'PermissionRequest');
  assert.deepEqual(out.hookSpecificOutput.decision, {
    behavior: 'deny',
    message: out.hookSpecificOutput.decision.message,
  });
  assert.match(out.hookSpecificOutput.decision.message, /force-push-protected/);
});

test('codex PermissionRequest: native 规则 → 不裁决,exit 0', () => {
  const r = spawnSync(process.execPath, [SCRIPT, '--platform=codex', '--event=PermissionRequest'], {
    input: JSON.stringify(bash('git reset --hard HEAD~1')), encoding: 'utf8', timeout: 5000,
  });
  assert.equal(r.status, 0);
  assert.equal(r.stdout.trim(), '');
  assert.equal(r.stderr.trim(), '');
});

test('坏 payload → exit 0(fail-open)', () => {
  const r = spawnSync(process.execPath, [SCRIPT, '--platform=claude'], { input: 'not json', encoding: 'utf8' });
  assert.equal(r.status, 0);
});
