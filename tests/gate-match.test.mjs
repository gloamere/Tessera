import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { matchCommand, extractCommand, loadRules } from '../pieces/wfos-core/scripts/gate.mjs';

const rules = loadRules(fileURLToPath(new URL('../pieces/wfos-core/gate-rules.json', import.meta.url)));

const CASES = [
  // [command, expectedRuleId | null]
  ['rm -rf C:\\Users\\Administrator\\proj', 'recursive-delete-outside'],
  ['rm -fr /', 'recursive-delete-outside'],
  ['rm -r -f ~/stuff', 'recursive-delete-outside'],
  ['rm -rf node_modules', 'recursive-delete-inside'],
  ['rm -rf ./build dist', 'recursive-delete-inside'],
  ['Remove-Item -Recurse -Force C:\\env\\old', 'recursive-delete-outside'],
  ['Remove-Item -Recurse -Force .\\build', 'recursive-delete-inside'],
  ['Remove-Item -Recurse -Force $env:USERPROFILE\\tmp', 'recursive-delete-outside'],
  ['rimraf dist', 'recursive-delete-inside'],
  ['rm -r src', null],                          // 无 -f,交给平台原生
  ['git push --force origin main', 'force-push-protected'],
  ['git push -f origin master', 'force-push-protected'],
  ['git push --force-with-lease origin main', 'force-push-protected'],
  ['git push --force origin feature/x', 'force-push-other'],
  ['git push -f', 'force-push-other'],          // 无 refspec,按保守档
  ['git push origin main', null],
  ['git reset --hard HEAD~1', 'discard-changes'],
  ['git checkout -- .', 'discard-changes'],
  ['git clean -fd', 'discard-changes'],
  ['git clean -xfd', 'discard-changes'],
  ['git checkout main', null],
  ['npm install -g typescript', 'untrusted-global-install'],
  ['npm i -g @foo/bar', 'untrusted-global-install'],
  ['npm install -g @beads/bd', null],           // 白名单命中
  ['pip install requests', 'untrusted-global-install'],
  ['npm install typescript', null],             // 非全局
  ['echo hi > trust.yaml', 'self-protect'],
  ['Set-Content gate-rules.json x', 'self-protect'],
  ['sed -i s/a/b/ pieces/wfos-core/gate-rules.json', 'self-protect'],
  ['cat trust.yaml', null],                     // 只读不拦
  ['ls -la', null],
  ['bd show gate-rules.json 2>&1', null],       // fd 重定向 ≠ 写受保护文件
  ['cat gate-rules.json 2>/dev/null', null],
  ['git log trust.yaml 1>&2', null],
  ['echo x > gate-rules.json', 'self-protect'], // 真写入仍拦
  ['echo x &> gate-rules.json', 'self-protect'],
];

for (const [cmd, expected] of CASES) {
  test(`match: ${cmd} -> ${expected}`, () => {
    const m = matchCommand(cmd, rules);
    assert.equal(m ? m.id : null, expected);
  });
}

test('exempt_commands: 精确命令(规范化后)完全放行', () => {
  const exempt = { ...rules, exempt_commands: ['rm -rf C:\\Go'] };
  assert.equal(matchCommand('rm  -rf   C:\\Go', exempt), null);           // 规范化后一致 → 放行
  assert.equal(matchCommand('rm -rf C:\\Windows', exempt).id, 'recursive-delete-outside'); // 未豁免仍拦
});

test('extractCommand: Claude PreToolUse payload', () => {
  assert.equal(extractCommand({ tool_name: 'Bash', tool_input: { command: 'git status' } }), 'git status');
});
test('extractCommand: 常见备选路径', () => {
  assert.equal(extractCommand({ command: 'ls' }), 'ls');
  assert.equal(extractCommand({ params: { command: 'ls' } }), 'ls');
  assert.equal(extractCommand({ arguments: { command: 'ls' } }), 'ls');
  assert.equal(extractCommand({}), null);
});
