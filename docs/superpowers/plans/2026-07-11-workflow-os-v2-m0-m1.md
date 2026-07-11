# workflow-os v2 M0+M1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 清删 v1 记账系统,交付「拼图市集」核心可用形态:双端(Claude Code + Codex)可安装的 wfos-core 与 bd-tasks 插件,含硬机制不可逆操作门。

**Architecture:** 本仓库即双市集(`.claude-plugin/marketplace.json` + `.agents/plugins/marketplace.json`);每块拼图一个目录(piece.yaml 语义源 + 双 plugin manifest + 共用 skills/);门 = gate-rules.json(数据)+ gate.mjs(零依赖 Node 脚本,Claude PreToolUse ask / Codex PermissionRequest deny)。无数据库、无常驻程序。

**Tech Stack:** Node 24(node:test,零运行时 npm 依赖),Claude Code plugin CLI,Codex plugin CLI(桌面版自带 codex.exe)。

**Spec:** `docs/superpowers/specs/2026-07-11-workflow-os-v2-design.md`(下称 spec)

## Global Constraints

- 所有写入的 JSON/YAML/MD 一律**无 BOM UTF-8**(BOM 会让 `claude plugin validate` 报 Invalid JSON)。用 Write 工具或 Node `fs.writeFileSync` 写;禁止 PowerShell `Out-File`/`Set-Content` 默认编码。
- 零 POSIX 习语:脚本内存在性检查用 Node `fs`,家目录用 `os.homedir()`,不用 `~`、`test -d`。
- hook 命令直接 `node <脚本>`,不套 cmd/bash 包装。
- 运行于插件缓存快照内的脚本(gate.mjs)**零 npm 依赖**——缓存快照不含仓库 node_modules。因此危险规则文件用 **gate-rules.json**(spec §4 原写 gate-rules.yaml,此为已论证的实现细化:hook 运行时无 YAML 解析器)。
- 版本号:所有 plugin manifest 与市集清单条目版本一致,首发 `0.1.0`;市集 metadata.version `2.0.0`。
- commit message 格式 `type: 中文描述`,不加 Co-authored-by。
- Codex CLI 本机不在 PATH:桌面版自带 `C:\Users\Administrator\AppData\Local\OpenAI\Codex\bin\07133f975a59dbd9\codex.exe`(Task 2 决策后按用户选择的方式调用;下文命令写 `codex`,执行时按决策替换)。
- Claude 端已知坑:`claude plugin update` 必须带 `@workflow-os` 全名;安装/更新后需重启会话生效。
- Codex 端已知事实:本地路径市集是活引用,升级 = 重跑 `codex plugin add <名>@workflow-os`;`marketplace upgrade` 仅 Git 市集可用。

---

### Task 1: M0 清仓 —— 删除 v1 工作副本,立 v2 骨架

**Files:**
- Delete: `src/`、`bin/`、`templates/`、`test/`(整目录)
- Create: `legacy/README.md`
- Modify: `README.md`(整体替换)、`package.json`(整体替换)、`.gitignore`
- Create(空目录占位): `pieces/wfos-core/.gitkeep`、`pieces/bd-tasks/.gitkeep`、`pieces/taste/.gitkeep`、`pieces/planner/.gitkeep`、`pieces/knowledge-base/.gitkeep`

**Interfaces:**
- Consumes: 无
- Produces: 干净的 v2 仓库骨架;后续所有任务在 `pieces/` 下工作

- [ ] **Step 1: 确认当前分支与基线**

Run: `git branch --show-current && git log --oneline -1`
Expected: `design/workflow-os-v2`,HEAD 为 f72ef79(spec 提交)

- [ ] **Step 2: 删除 v1 工作副本**

Run: `git rm -r -q src bin templates test package-lock.json`
Expected: 无输出(成功)。注意:`docs/` 与 `.beads/` 不动。

- [ ] **Step 3: 写 legacy/README.md**

```markdown
# v1 实现(已归档)

workflow-os v1(Markdown→SQLite 记账系统,Codex-first)的完整实现保留在 git 历史中,未迁移任何数据(v1 从未实际使用)。

- 最后版本:commit `973a85b`(分支 `main`、`fix/concurrency-and-cli-hardening`)
- 查看:`git show 973a85b:src/index-db.mjs` 等
- v1→v2 功能处置对照:见 `docs/superpowers/specs/2026-07-11-workflow-os-v2-design.md` §14
```

- [ ] **Step 4: 替换 README.md**

```markdown
# workflow-os v2 — 个人能力操作系统(拼图市集)

本仓库同时是 Claude Code 与 Codex 的本地插件市集:注册、路由、安装、升级你的能力拼图(bd、agent-reach、taste、superpowers…)。

## 安装(机器级,一次)

​```text
Claude:claude plugin marketplace add <本仓库路径>
        claude plugin install wfos-core@workflow-os --scope user
Codex: codex plugin marketplace add <本仓库路径>
        codex plugin add wfos-core@workflow-os
​```

重启会话后运行 `/wfos-setup` 按引导安装其余拼图。

## 设计文档

- 设计 spec:`docs/superpowers/specs/2026-07-11-workflow-os-v2-design.md`
- v1 已归档:见 `legacy/README.md`
```

- [ ] **Step 5: 替换 package.json**

```json
{
  "name": "workflow-os",
  "version": "2.0.0-dev",
  "private": true,
  "description": "Personal capability OS: local plugin marketplace for Claude Code & Codex",
  "type": "module",
  "scripts": {
    "test": "node --test tests/"
  },
  "engines": { "node": ">=24" }
}
```

- [ ] **Step 6: 建 pieces 骨架与 .gitignore 更新**

为 `pieces/wfos-core`、`pieces/bd-tasks`、`pieces/taste`、`pieces/planner`、`pieces/knowledge-base` 各建目录并放空文件 `.gitkeep`。`.gitignore` 整体替换为:

```text
node_modules/
*.log
```

- [ ] **Step 7: 验证与提交**

Run: `ls` 确认只剩 `docs/ legacy/ pieces/ README.md package.json .gitignore .beads/`;`git add -A && git commit -m "chore: M0 清删 v1 工作副本,立 v2 骨架"`
Expected: commit 成功;`git show 973a85b:src/index-db.mjs | head -3` 仍可取到旧码(历史完好)。

---

### Task 2: M0 决策文档 —— bd 通道 / Codex CLI 调用方式 / taste 来源

**Files:**
- Create: `docs/decisions/bd-install-channel.md`
- Create: `docs/decisions/codex-cli-access.md`
- Create: `docs/decisions/taste-skill-source.md`

**Interfaces:**
- Consumes: 无
- Produces: 三份决策文件,frontmatter `status: approved`(经负责人拍板);Task 9 按 codex-cli-access 的结论调用 codex;trust.yaml(Task 7)按 bd-install-channel 结论保留 npm 通道

- [ ] **Step 1: 核实 taste-skill 上游存在性**

Run: `gh api repos/Leonxlnx/taste-skill --jq "{name:.name,default_branch:.default_branch,pushed_at:.pushed_at}"`
Expected: 返回 JSON(仓库存在)。若 404:决策文件中记录「来源失效,taste 降级出默认集」,后续任务照常(taste 是 M3 内容,不阻塞本计划)。

- [ ] **Step 2: 写三份决策文件**

`docs/decisions/bd-install-channel.md`:

```markdown
---
schema: wfos/decision@1
id: bd-install-channel
status: pending
created: 2026-07-11
---

# bd 安装通道统一

## 背景
本机双安装:C:\env\beads_0.62.0_windows_amd64\bd.exe(PATH 首位,0.62.0)遮蔽 npm 全局 @beads/bd(1.0.2 shim)。上游已迁 gastownhall/beads,最新 1.1.0。不统一则升级流死循环(npm 升级后 version 探测仍由旧 exe 应答)。

## 选项
- **A(推荐)**:统一到 npm 通道——`npm install -g @beads/bd@latest` 升至 1.x,从 PATH 移除 C:\env\beads_0.62.0_windows_amd64,删除该目录。0.62→1.x 有大版本跨越,升级后跑 `bd doctor` 与 `bd ready` 验证数据无损。
- **B**:维持手解 exe,bd 升级永远 manual,wfos 升级链对 bd 只提醒不执行。

## 结论
(拍板后填写)
```

`docs/decisions/codex-cli-access.md`:

```markdown
---
schema: wfos/decision@1
id: codex-cli-access
status: pending
created: 2026-07-11
---

# Codex CLI 调用方式

## 背景
桌面版自带 codex.exe 位于 C:\Users\Administrator\AppData\Local\OpenAI\Codex\bin\07133f975a59dbd9\codex.exe,不在 PATH;bin 下哈希目录名会随桌面版更新变化。

## 选项
- **A(推荐)**:在 C:\Users\Administrator\.local\bin(已在 PATH)放 codex.cmd shim,内容动态解析 bin 下最新目录:
  `@echo off` / `for /f "delims=" %%i in ('dir /b /ad /o-d "%LOCALAPPDATA%\OpenAI\Codex\bin"') do (set "CODEX_DIR=%%i" & goto :run)` / `:run` / `"%LOCALAPPDATA%\OpenAI\Codex\bin\%CODEX_DIR%\codex.exe" %*`
- **B**:不进 PATH,文档与脚本一律写全路径(桌面版更新后手改)。

## 结论
(拍板后填写)
```

`docs/decisions/taste-skill-source.md`:

```markdown
---
schema: wfos/decision@1
id: taste-skill-source
status: pending
created: 2026-07-11
---

# taste-skill 来源确认

## 背景
本机未安装 taste-skill(全盘无踪影);旧码 DEFAULT_ADAPTERS 记录来源 Leonxlnx/taste-skill。Step 1 核实结果:(执行时填写:存在/404)

## 选项
- **A**:确认收编该仓库为 taste 拼图(M3 执行)。
- **B**:来源失效或不想要 → taste 降级出默认集,pieces/taste 目录删除。

## 结论
(拍板后填写)
```

- [ ] **Step 3: 【检查点】负责人拍板三项决策**

Orchestrator 用 AskUserQuestion 逐项问,把选择写入各文件「结论」节,`status: pending` 改 `approved`。**A 选项被选中时立即执行其动作**(建 shim / 统一 bd 通道)并在结论中记录执行结果。

- [ ] **Step 4: 提交**

Run: `git add docs/decisions && git commit -m "docs: M0 三项决策(bd 通道/codex 调用/taste 来源)"`

---

### Task 3: 门核心 —— gate-rules.json + 命令匹配逻辑(TDD)

**Files:**
- Create: `pieces/wfos-core/gate-rules.json`
- Create: `pieces/wfos-core/scripts/gate.mjs`
- Test: `tests/gate-match.test.mjs`

**Interfaces:**
- Consumes: 无
- Produces: `gate.mjs` 导出 `matchCommand(command: string, rules: object) -> {id, description, claude, codex} | null`、`extractCommand(payload: object) -> string | null`、`loadRules(path?: string) -> object`。Task 4 复用同文件加 main 入口;Task 5 的 hooks 配置调用本脚本。

- [ ] **Step 1: 写 gate-rules.json**

```json
{
  "version": 1,
  "global_install_allowlist": ["npm install -g @beads/bd"],
  "rules": [
    { "id": "recursive-delete-outside", "description": "递归强制删除项目外/盘符/家目录路径", "claude": "ask", "codex": "deny" },
    { "id": "recursive-delete-inside", "description": "项目内递归强制删除", "claude": "ask", "codex": "native" },
    { "id": "force-push-protected", "description": "强推 main/master", "claude": "ask", "codex": "deny" },
    { "id": "force-push-other", "description": "强推分支", "claude": "ask", "codex": "native" },
    { "id": "discard-changes", "description": "丢弃未提交改动(reset --hard / checkout -- / clean -f)", "claude": "ask", "codex": "native" },
    { "id": "untrusted-global-install", "description": "白名单外全局安装", "claude": "ask", "codex": "native" },
    { "id": "self-protect", "description": "改写门配置/白名单自身", "claude": "ask", "codex": "deny" }
  ]
}
```

- [ ] **Step 2: 写失败测试(表驱动,覆盖 Bash+PowerShell 变体与绕过拼写)**

`tests/gate-match.test.mjs`:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { matchCommand, extractCommand, loadRules } from '../pieces/wfos-core/scripts/gate.mjs';

const rules = loadRules(new URL('../pieces/wfos-core/gate-rules.json', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1'));

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
];

for (const [cmd, expected] of CASES) {
  test(`match: ${cmd} -> ${expected}`, () => {
    const m = matchCommand(cmd, rules);
    assert.equal(m ? m.id : null, expected);
  });
}

test('extractCommand: Claude PreToolUse payload', () => {
  assert.equal(extractCommand({ tool_name: 'Bash', tool_input: { command: 'git status' } }), 'git status');
});
test('extractCommand: 常见备选路径', () => {
  assert.equal(extractCommand({ command: 'ls' }), 'ls');
  assert.equal(extractCommand({ params: { command: 'ls' } }), 'ls');
  assert.equal(extractCommand({ arguments: { command: 'ls' } }), 'ls');
  assert.equal(extractCommand({}), null);
});
```

- [ ] **Step 3: 跑测试确认失败**

Run: `node --test tests/`
Expected: FAIL —— `Cannot find module .../gate.mjs`

- [ ] **Step 4: 实现 gate.mjs(匹配核心,零依赖)**

```js
#!/usr/bin/env node
/**
 * 不可逆操作门(spec §7.2)。零 npm 依赖:运行于插件缓存快照内。
 * 匹配是启发式 guardrail,不是安全边界(spec 已如实定性)。
 */
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));

export function loadRules(path = join(here, '..', 'gate-rules.json')) {
  return JSON.parse(readFileSync(path, 'utf8'));
}

const ABS_TARGET = /^([A-Za-z]:[\\/]|[\\/]$|[\\/][^\\/]|~|\$HOME\b|\$env:USERPROFILE\b|%USERPROFILE%)/i;

const words = (cmd) => cmd.trim().split(/\s+/).map((w) => w.replace(/^['"]|['"]$/g, ''));

function matchRecursiveDelete(cmd) {
  const w = words(cmd);
  const lower = w.map((x) => x.toLowerCase());
  let targets = null;
  const rmIdx = lower.indexOf('rm');
  if (rmIdx >= 0) {
    const flags = w.slice(rmIdx + 1).filter((x) => /^-[a-z]+$/i.test(x)).join('');
    if (/r/i.test(flags) && /f/i.test(flags)) targets = w.slice(rmIdx + 1).filter((x) => !x.startsWith('-'));
  }
  const riIdx = lower.findIndex((x) => x === 'remove-item' || x === 'ri');
  if (riIdx >= 0 && lower.some((x) => x.startsWith('-recurse')) && lower.some((x) => x.startsWith('-force'))) {
    targets = w.slice(riIdx + 1).filter((x) => !x.startsWith('-'));
  }
  const rrIdx = lower.indexOf('rimraf');
  if (rrIdx >= 0) targets = w.slice(rrIdx + 1).filter((x) => !x.startsWith('-'));
  if (!targets) return null;
  return targets.some((t) => ABS_TARGET.test(t)) ? 'recursive-delete-outside' : 'recursive-delete-inside';
}

function matchForcePush(cmd) {
  if (!/\bgit\s+push\b/.test(cmd)) return null;
  if (!/(\s--force(-with-lease)?\b|\s-f\b)/.test(cmd)) return null;
  return /\b(main|master)\b/.test(cmd) ? 'force-push-protected' : 'force-push-other';
}

function matchDiscardChanges(cmd) {
  if (/\bgit\s+reset\s+--hard\b/.test(cmd)) return 'discard-changes';
  if (/\bgit\s+checkout\s+--\s/.test(cmd)) return 'discard-changes';
  if (/\bgit\s+clean\s+-[a-z]*f/i.test(cmd)) return 'discard-changes';
  return null;
}

function matchGlobalInstall(cmd, allowlist) {
  const npmGlobal = /\bnpm\s+(install|i|add)\b[^&|;]*(\s-g\b|\s--global\b)/.test(cmd);
  const pipInstall = /\bpip3?\s+install\s/.test(cmd);
  if (!npmGlobal && !pipInstall) return null;
  const normalized = cmd.trim().replace(/\s+/g, ' ');
  if (allowlist.includes(normalized)) return null;
  return 'untrusted-global-install';
}

function matchSelfProtect(cmd) {
  if (!/(trust\.yaml|gate-rules\.json)/i.test(cmd)) return null;
  if (/(>>?|\bset-content\b|\bout-file\b|\bsed\s+-i\b|\btee\b|\brm\b|\bremove-item\b|\bdel\b|\bmv\b|\bmove\b)/i.test(cmd)) return 'self-protect';
  return null;
}

export function matchCommand(command, rules) {
  if (!command || typeof command !== 'string') return null;
  const allow = rules.global_install_allowlist ?? [];
  const id = matchRecursiveDelete(command) ?? matchForcePush(command)
    ?? matchDiscardChanges(command) ?? matchGlobalInstall(command, allow) ?? matchSelfProtect(command);
  return id ? (rules.rules.find((r) => r.id === id) ?? null) : null;
}

export function extractCommand(payload) {
  const candidates = [
    payload?.tool_input?.command,
    payload?.tool_input?.script,
    payload?.command,
    payload?.params?.command,
    payload?.arguments?.command,
  ];
  for (const c of candidates) if (typeof c === 'string' && c.trim()) return c;
  return null;
}
```

- [ ] **Step 5: 跑测试确认通过**

Run: `node --test tests/`
Expected: 全部 PASS(约 37 个用例)。若个别边界用例失败,修匹配器不改用例意图。

- [ ] **Step 6: 提交**

Run: `git add pieces/wfos-core tests && git commit -m "feat: 门核心——gate-rules 数据与命令匹配器(TDD)"`

---

### Task 4: 门平台适配层 —— stdin/输出/退出码(TDD)

**Files:**
- Modify: `pieces/wfos-core/scripts/gate.mjs`(追加 main 入口)
- Test: `tests/gate-io.test.mjs`

**Interfaces:**
- Consumes: Task 3 的 `matchCommand`/`extractCommand`/`loadRules`
- Produces: CLI 行为契约——`node gate.mjs --platform=claude|codex`,stdin 读 JSON payload:
  - claude+ask → stdout `{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"<理由>"}}`,exit 0
  - codex+deny → stderr 理由,exit 2
  - codex+native / 无命中 / payload 解析失败 → 无输出,exit 0(fail-open 但 Claude 端 ask 兜底;门是 guardrail)
  - `WFOS_GATE_DEBUG=1` → 原始 payload 追加写 `os.homedir()/.workflow-os/gate-debug.log`

- [ ] **Step 1: 写失败测试(spawn 子进程)**

`tests/gate-io.test.mjs`:

```js
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `node --test tests/gate-io.test.mjs`
Expected: FAIL(main 入口不存在,子进程无输出/立即退出导致断言失败——具体为 ask 用例的 JSON.parse 失败)

- [ ] **Step 3: 在 gate.mjs 末尾追加 main 入口**

```js
// ---- CLI 入口(hook 调用) ----
import { appendFileSync, mkdirSync } from 'node:fs';
import { homedir } from 'node:os';

const isMain = process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1];
if (isMain) {
  let raw = '';
  process.stdin.setEncoding('utf8');
  for await (const chunk of process.stdin) raw += chunk;

  if (process.env.WFOS_GATE_DEBUG === '1') {
    try {
      const dir = join(homedir(), '.workflow-os');
      mkdirSync(dir, { recursive: true });
      appendFileSync(join(dir, 'gate-debug.log'), `${new Date().toISOString()} ${raw}\n`, 'utf8');
    } catch { /* 调试日志失败不影响裁决 */ }
  }

  const platform = process.argv.includes('--platform=codex') ? 'codex' : 'claude';
  let match = null;
  try {
    const payload = JSON.parse(raw);
    const command = extractCommand(payload);
    if (command) match = matchCommand(command, loadRules());
  } catch { /* fail-open:门是 guardrail,解析失败不阻塞工具 */ }

  if (match) {
    const reason = `[wfos 门] ${match.description}(规则 ${match.id})。请确认后再执行。`;
    const action = match[platform];
    if (platform === 'claude' && action === 'ask') {
      process.stdout.write(JSON.stringify({
        hookSpecificOutput: { hookEventName: 'PreToolUse', permissionDecision: 'ask', permissionDecisionReason: reason },
      }));
    } else if (platform === 'codex' && action === 'deny') {
      process.stderr.write(reason);
      process.exitCode = 2;
    }
    // codex 'native':不裁决 → 原生审批
  }
}
```

注意:文件顶部已有 `fileURLToPath`/`join` 导入,此处仅新增 `appendFileSync, mkdirSync, homedir`。顶层 `for await` 需要文件为 ESM(package.json 已 `"type": "module"`)。

- [ ] **Step 4: 跑全部测试确认通过**

Run: `node --test tests/`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

Run: `git add -A && git commit -m "feat: 门平台适配层——claude ask / codex deny 输出契约"`

---

### Task 5: wfos-core 拼图内容(清单、manifest、hooks、skills、command)

**Files:**
- Create: `pieces/wfos-core/piece.yaml`
- Create: `pieces/wfos-core/.claude-plugin/plugin.json`
- Create: `pieces/wfos-core/.codex-plugin/plugin.json`
- Create: `pieces/wfos-core/hooks/hooks.json`(Claude 默认发现位置)
- Create: `pieces/wfos-core/hooks/codex.hooks.json`
- Create: `pieces/wfos-core/skills/piece-router/SKILL.md`
- Create: `pieces/wfos-core/skills/wfos-setup/SKILL.md`
- Create: `pieces/wfos-core/commands/wfos-status.md`
- Delete: `pieces/wfos-core/.gitkeep`

**Interfaces:**
- Consumes: Task 3/4 的 `scripts/gate.mjs`、`gate-rules.json`
- Produces: 完整可安装的 wfos-core 插件目录;Task 7 的市集清单引用 `./pieces/wfos-core`,版本 `0.1.0`

- [ ] **Step 1: piece.yaml**

```yaml
id: wfos-core
kind: skill
summary: workflow-os 内核:意图路由兜底、安装引导、状态查看与不可逆操作门。
when_to_use:
  - 复合/模糊意图,不确定用哪块拼图 → piece-router
  - 初始化工作流、安装拼图 → wfos-setup
  - 查看拼图与依赖状态 → /wfos-status
avoid_when: 已有明确单一工具触发的任务
platforms: { claude: native, codex: native, gemini: snippet, domestic: snippet }
external_deps: []
upgrade_policy: notify-only
```

- [ ] **Step 2: 双 plugin manifest**

`.claude-plugin/plugin.json`:

```json
{
  "name": "wfos-core",
  "description": "workflow-os 内核:路由兜底、安装引导、状态查看、不可逆操作门",
  "version": "0.1.0",
  "author": { "name": "van" }
}
```

`.codex-plugin/plugin.json`:

```json
{
  "name": "wfos-core",
  "description": "workflow-os 内核:路由兜底、安装引导、状态查看、不可逆操作门",
  "version": "0.1.0",
  "skills": "./skills/",
  "hooks": "./hooks/codex.hooks.json"
}
```

- [ ] **Step 3: 双 hooks 配置(M1 只有门;SessionStart 属 M2)**

`hooks/hooks.json`(Claude):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|PowerShell",
        "hooks": [
          { "type": "command", "command": "node \"${CLAUDE_PLUGIN_ROOT}/scripts/gate.mjs\" --platform=claude", "timeout": 10 }
        ]
      }
    ]
  }
}
```

`hooks/codex.hooks.json`(事件名大小写是 Task 9 冒烟项;先按 PascalCase,冒烟发现 kebab-case 再改):

```json
{
  "hooks": {
    "PermissionRequest": [
      {
        "matcher": "*",
        "hooks": [
          { "type": "command", "command": "node \"${CLAUDE_PLUGIN_ROOT}/scripts/gate.mjs\" --platform=codex", "timeout": 10 }
        ]
      }
    ]
  }
}
```

- [ ] **Step 4: piece-router SKILL.md**

```markdown
---
name: piece-router
description: 当用户提出一项工作但不明确用什么工具、涉及多种能力、或说"新项目""帮我规划""不知道怎么开始"时使用。本 skill 是 workflow-os 的兜底路由表:把意图派发到正确的能力拼图。
---

# 拼图派发表

| 意图 | 拼图 | 调用方式 |
|---|---|---|
| 搜索、调研、查资料、读 URL、看某平台讨论 | agent-reach | Skill 工具调用 agent-reach,二级路由看其 SKILL.md |
| UI/视觉设计评审、审美判断 | taste | Skill 工具调用(未安装则提示 /wfos-setup) |
| 写代码、改功能、修 bug | superpowers 流程链 | brainstorming → writing-plans → 实现 → verification |
| 任务/待办/拆解/追踪 | bd-tasks | 直接执行 bd 命令(见 bd-tasks skill) |
| 游戏策划、方案策划 | planner | Skill 工具调用(孵化中,未装则先走 brainstorming) |
| 拼图状态/安装/升级 | wfos-core 自身 | /wfos-status、wfos-setup skill |

## 门规则(必须遵守)

1. **方向性拍板门**:设计方向、策划方案、UI 风格、技术选型属负责人拍板范围。执行会固化方向的实现前,检查 `docs/decisions/` 下关联决策文件 frontmatter——`status: approved` 才能动工;没有决策文件就先创建(status: pending)并用 AskUserQuestion 请负责人拍板。decisions 文件状态是唯一权威。
2. **不可逆操作**(强推、递归删除、丢弃改动、全局安装)已由 hook 拦截弹确认;被拦时向用户说明原因,不要绕过。

## 多意图命中

命中多块拼图时,先用 AskUserQuestion 让用户选;零命中时正常工作,不硬套拼图。
```

- [ ] **Step 5: wfos-setup SKILL.md**

```markdown
---
name: wfos-setup
description: 当用户要"初始化工作流""安装拼图""装 workflow-os""setup 工作流"或在新机器/新项目上部署能力拼图时使用。引导式安装:列出可装拼图,经用户勾选后逐项安装。
---

# wfos-setup 安装引导

## 流程

1. 定位市集仓库根(本 skill 所在插件的 CLAUDE_PLUGIN_ROOT 上溯,或让用户给出 workflow-os 仓库路径)。
2. 读仓库 `.claude-plugin/marketplace.json`(拼图清单)、`registry.yaml`(外部引用;文件缺失则跳过外部段)、各 `pieces/<id>/piece.yaml`(when_to_use/external_deps)。
3. 用 AskUserQuestion(multiSelect)列出:本地拼图(含版本与 summary)+ 外部引用 + 外部 CLI 依赖,让用户勾选。
4. 逐项安装:
   - 本地拼图(Claude):`claude plugin install <id>@workflow-os --scope user`
   - 本地拼图(Codex):`codex plugin add <id>@workflow-os`
   - template-pack 类:按「只补缺」复制模板到项目 `docs/`(文件已存在一律跳过)
   - 外部 CLI:先跑 piece.yaml 的 version_check 探测;缺失才装;**install 命令必须与仓库根 trust.yaml 对应条目的模板逐词一致(全匹配,含未知 flag 即拒),不一致则拒绝执行并打印命令原文让用户手动判断**
5. 输出安装报告:装了什么、跳过什么、哪些需重启会话、哪些需在 Codex 首次运行时确认 hook 信任。

## 硬规则

- 永不静默安装未勾选项;永不执行 trust.yaml 之外的安装命令。
- 本 skill 只经 plugin 通道安装拼图;`~/.claude/skills/`、`~/.agents/skills/` 散装目录是开发模式专用,不写入。
```

- [ ] **Step 6: commands/wfos-status.md**

```markdown
---
description: 查看 workflow-os 拼图与外部依赖状态
---

对每块拼图输出一行状态表。步骤:

1. 运行 `claude plugin list` 取已装插件与版本(Codex 环境用 `codex plugin list`)。
2. 对市集仓库各 pieces/<id>/piece.yaml 声明的 external_deps 逐个跑 version_check(如 `bd version`)。
3. 输出表:拼图 | 版本 | 已装? | 外部依赖状态。
4. 发现异常(依赖缺失、版本探测失败)时给出对应修复建议(/wfos-setup 或手动命令)。
```

- [ ] **Step 7: 校验与提交**

Run: `claude plugin validate pieces/wfos-core`
Expected: 校验通过(warning 可接受,error 不可)。
Run: `git add pieces/wfos-core && git rm pieces/wfos-core/.gitkeep -q ; git commit -m "feat: wfos-core 拼图——清单/manifest/hooks/skills/command"`

---

### Task 6: bd-tasks 拼图

**Files:**
- Create: `pieces/bd-tasks/piece.yaml`(内容 = spec §5 示例,逐字)
- Create: `pieces/bd-tasks/.claude-plugin/plugin.json`
- Create: `pieces/bd-tasks/.codex-plugin/plugin.json`
- Create: `pieces/bd-tasks/skills/bd-tasks/SKILL.md`
- Delete: `pieces/bd-tasks/.gitkeep`

**Interfaces:**
- Consumes: 无
- Produces: 可安装的 bd-tasks 插件;Task 7 市集清单引用 `./pieces/bd-tasks`,版本 `0.1.0`

- [ ] **Step 1: piece.yaml(spec §5 示例逐字复制)**

见 spec §5 bd-tasks 示例,原样写入。

- [ ] **Step 2: 双 manifest**

`.claude-plugin/plugin.json`:

```json
{
  "name": "bd-tasks",
  "description": "任务追踪拼图:路由到 bd (beads) CLI,替代 TodoWrite",
  "version": "0.1.0",
  "author": { "name": "van" }
}
```

`.codex-plugin/plugin.json`:

```json
{
  "name": "bd-tasks",
  "description": "任务追踪拼图:路由到 bd (beads) CLI,替代 TodoWrite",
  "version": "0.1.0",
  "skills": "./skills/"
}
```

- [ ] **Step 3: skills/bd-tasks/SKILL.md**

```markdown
---
name: bd-tasks
description: 任何"记任务、拆任务、领任务、关任务、查任务、依赖、epic、待办、backlog、回头再做"类意图时使用。任务追踪一律走 bd (beads) CLI——禁止 TodoWrite、禁止 markdown TODO 列表。
---

# bd 任务追踪

## 命令速查

| 意图 | 命令 |
|---|---|
| 快速记一条 | `bd q "描述"`(只回 id) |
| 新建任务 | `bd create "描述"`(加 `-p 0..3` 定优先级) |
| 找可开工任务 | `bd ready` |
| 查看详情 | `bd show <id>` |
| 领取 | `bd update <id> --claim` |
| 完成 | `bd close <id>` |
| 追加备注 | `bd note <id> "内容"` |
| 大活拆解 | `bd epic create` + `bd dep add <child> <parent>` |
| 需负责人异步确认 | `bd gate`(仅作通知载体;权威状态是 docs/decisions/ 文件的 frontmatter status) |

## 规则

- 项目首次使用:先 `bd ready` 探测;报 "no beads database" 时问用户是否 `bd init`(依赖 Dolt)。
- 会话产生的后续工作项必须落 bd,不留在对话里。
- 提交代码前若任务完成,顺手 `bd close <id>`。
```

- [ ] **Step 4: 校验与提交**

Run: `claude plugin validate pieces/bd-tasks`
Expected: 通过。
Run: `git add pieces/bd-tasks && git rm pieces/bd-tasks/.gitkeep -q ; git commit -m "feat: bd-tasks 拼图"`

---

### Task 7: 双市集清单 + trust.yaml + registry.yaml + 仓库级校验测试

**Files:**
- Create: `.claude-plugin/marketplace.json`
- Create: `.agents/plugins/marketplace.json`
- Create: `trust.yaml`(内容 = spec §5 trust 示例,逐字)
- Create: `registry.yaml`
- Test: `tests/repo-hygiene.test.mjs`

**Interfaces:**
- Consumes: Task 5/6 的两个拼图目录(版本 0.1.0)
- Produces: 可被 `claude plugin marketplace add` / `codex plugin marketplace add` 接入的市集;Task 8/9 直接消费

- [ ] **Step 1: .claude-plugin/marketplace.json**

```json
{
  "name": "workflow-os",
  "owner": { "name": "van" },
  "metadata": { "description": "个人工作流操作系统:本地拼图市集", "version": "2.0.0" },
  "plugins": [
    { "name": "wfos-core", "source": "./pieces/wfos-core", "description": "内核:路由兜底、安装、状态、不可逆操作门", "version": "0.1.0", "strict": true },
    { "name": "bd-tasks", "source": "./pieces/bd-tasks", "description": "任务追踪:bd CLI 路由", "version": "0.1.0", "strict": true }
  ]
}
```

- [ ] **Step 2: .agents/plugins/marketplace.json(Codex 市集,schema 按本机 openai-bundled 实测样本)**

```json
{
  "name": "workflow-os",
  "interface": { "displayName": "workflow-os" },
  "plugins": [
    { "name": "wfos-core", "source": { "source": "local", "path": "./pieces/wfos-core" }, "category": "workflow" },
    { "name": "bd-tasks", "source": { "source": "local", "path": "./pieces/bd-tasks" }, "category": "workflow" }
  ]
}
```

- [ ] **Step 3: trust.yaml(spec §5 示例逐字)与 registry.yaml**

`registry.yaml`:

```yaml
version: 1
external:
  - id: superpowers
    kind: plugin-ref
    summary: 代码流程链(brainstorming/TDD/debugging/验证)
    per_platform:
      claude: "claude plugin install superpowers@superpowers-marketplace"
      codex: "M3 择优:codex plugin marketplace add obra/superpowers-marketplace 或 skills symlink 到 ~/.agents/skills"
    trust_ref: superpowers
  - id: agent-reach
    kind: plugin-ref
    summary: 全网搜索调研(17 平台);含机器级 CLI 生态,不收编
    per_platform:
      claude: "已装于 ~/.claude/skills/agent-reach(散装)"
      codex: "M3 评估 symlink 到 ~/.agents/skills"
```

- [ ] **Step 4: 写仓库卫生测试**

`tests/repo-hygiene.test.mjs`:

```js
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
```

- [ ] **Step 5: 跑测试(先失败后过)**

Run: `node --test tests/repo-hygiene.test.mjs` —— 若清单未写完则 FAIL;补齐后 PASS。
Run: `claude plugin validate .`
Expected: 市集与两个插件全部通过。

- [ ] **Step 6: 提交**

Run: `git add -A && git commit -m "feat: 双市集清单 + trust/registry + 仓库卫生测试"`

---

### Task 8: Claude 端安装与门冒烟(需要 orchestrator/负责人参与)

**Files:** 无新文件(操作性任务);结果记入 `docs/superpowers/plans/2026-07-11-m1-smoke-results.md`(Create)

**Interfaces:**
- Consumes: Task 7 完成的市集
- Produces: Claude 端已装 wfos-core + bd-tasks;冒烟结果文档

- [ ] **Step 1: 接入市集并安装**

Run:
```
claude plugin marketplace add G:\Claude\workflow-os
claude plugin install wfos-core@workflow-os --scope user
claude plugin install bd-tasks@workflow-os --scope user
claude plugin list
```
Expected: 两插件 enabled;list 显示版本 0.1.0。

- [ ] **Step 2: 【手动】重启会话后验证 skill/command 可见**

新 Claude Code 会话:skills 列表含 piece-router / wfos-setup / bd-tasks;`/wfos-status`(实际名可能带命名空间 `/wfos-core:wfos-status`)可执行。记录实际呼出名。

- [ ] **Step 3: 【手动】门触发验证(表 1/3/7 → ask;表 2/5 → 不拦或原生)**

在新会话让 Claude 执行(无害环境:临时目录 git 仓库,无 remote):
1. `git push --force origin main` → 期望弹出确认,理由含 `force-push-protected`
2. `rm -rf C:\Users\Administrator\AppData\Local\Temp\wfos-gate-test`(先建该目录)→ 期望弹确认(recursive-delete-outside)
3. `echo x >> trust.yaml`(在仓库根)→ 期望弹确认(self-protect)
4. `git status` → 期望不弹
若 hook 未触发:检查 `claude plugin list` hooks 加载、开 `WFOS_GATE_DEBUG=1` 看 `~/.workflow-os/gate-debug.log` 是否收到 payload,按实际 payload 字段修 `extractCommand`(改代码须回跑 Task 3/4 测试)。

- [ ] **Step 4: 记录结果并提交**

写 `docs/superpowers/plans/2026-07-11-m1-smoke-results.md`(Claude 节:各步实际输出/呼出名/payload 差异与修正),`git add -A && git commit -m "test: Claude 端 M1 安装与门冒烟结果"`

---

### Task 9: Codex 端安装与四项准入冒烟(需要 orchestrator/负责人参与)

**Files:** Modify: `docs/superpowers/plans/2026-07-11-m1-smoke-results.md`(追加 Codex 节);视冒烟结果 Modify `pieces/wfos-core/hooks/codex.hooks.json`

**Interfaces:**
- Consumes: Task 2 的 codex-cli-access 决策(codex 调用方式)、Task 7 市集
- Produces: Codex 端已装两拼图;spec §16 四项准入冒烟结论(①插件 hooks 生效性 ②全局 hooks.json 路径/事件命名 ③CLI 调用方式 ④PermissionRequest deny 显示)

- [ ] **Step 1: 接入市集并安装**

Run(按 Task 2 决策的调用方式):
```
codex plugin marketplace add G:\Claude\workflow-os
codex plugin add wfos-core@workflow-os
codex plugin add bd-tasks@workflow-os
codex plugin list
```
Expected: 两插件 installed/enabled;缓存出现 `~/.codex/plugins/cache/workflow-os/wfos-core/0.1.0/`。

- [ ] **Step 2: skill 注入验证(无 API 消耗)**

Run: 在临时 git 仓库执行 `codex debug prompt-input "hello"`
Expected: 输出的 `<skills_instructions>` 段含 piece-router / wfos-setup / bd-tasks 及其 description。

- [ ] **Step 3: 【手动】冒烟① 插件 hooks 生效性**

Codex Desktop 新会话,执行一条 deny 规则命令(临时仓库 `git push --force origin main`):
- 生效 → 期望被拒且显示 `[wfos 门] 强推 main/master…` 理由(同时完成冒烟④)。首次可能要求信任 hook,记录信任流程。
- 不生效(plugin_hooks flag 疑点坐实)→ 走 Step 4 回退。

- [ ] **Step 4: 【条件】冒烟② 全局 hooks.json 回退**

若 Step 3 不生效:把 `codex.hooks.json` 内容写到 `~/.codex/hooks.json`(command 换成仓库绝对路径),重启 Codex 重试。若仍不生效,事件名改 kebab-case(`permission-request`)再试(二进制迹象)。记录最终可用的路径+命名,回写 `pieces/wfos-core/hooks/codex.hooks.json` 与 smoke-results;若 Codex 需要 `[features] codex_hooks = true`(config.toml),记录并加入 wfos-setup skill 的安装报告提示。

- [ ] **Step 5: native 路径验证**

Codex 会话执行 `git reset --hard HEAD`(有未提交改动的临时仓库)→ 期望走 Codex 原生审批(不是 wfos deny)。

- [ ] **Step 6: 记录与提交**

smoke-results 追加 Codex 节(四项冒烟逐项结论 + 修改点),`git add -A && git commit -m "test: Codex 端 M1 安装与四项准入冒烟结果"`

---

### Task 10: bd 路由验收 + M1 收尾

**Files:** Modify: `docs/superpowers/plans/2026-07-11-m1-smoke-results.md`(追加路由节)

**Interfaces:**
- Consumes: Task 8/9 装好的双端环境
- Produces: spec §17 M1 验收闭环;bd 任务状态更新

- [ ] **Step 1: 显式调用验收(要求 100%)**

Claude:`/wfos-status`(或带命名空间名)正常输出状态表;Codex:`$skill bd-tasks` 可显式调用。记录。

- [ ] **Step 2: 隐式触发冒烟(3~5 条固定 prompt,记录命中,不设硬阈值)**

在任一已装项目的新会话逐条输入,记录是否路由到 bd(而非 TodoWrite/markdown):
1. 「记一下:回头把 README 安装节补上」→ 期望 `bd q`/`bd create`
2. 「有什么可以开工的任务?」→ 期望 `bd ready`
3. 「把这次重构拆成可跟踪的任务」→ 期望 `bd epic` + `bd dep`
4. 「帮我看下任务 workflow-os-e3f 的详情」→ 期望 `bd show workflow-os-e3f`
5. 「不知道从哪开始,帮我规划一下这个项目」→ 期望 piece-router 触发并给派发建议

- [ ] **Step 3: 全量测试回归**

Run: `node --test tests/`
Expected: 全部 PASS

- [ ] **Step 4: 收尾提交与任务更新**

smoke-results 补路由节;`git add -A && git commit -m "test: M1 bd 路由验收记录"`;`bd note workflow-os-e3f "M0+M1 完成:双端市集安装、门、bd-tasks 落地;冒烟结果见 plans/2026-07-11-m1-smoke-results.md"`。M1 验收(spec §17)逐项核对,未达项开 bd 任务跟踪。

---

## Self-Review 记录(计划作者自查)

- **Spec 覆盖**:M0 三验收项 → Task 1/2;M1 验收(双端 install、门表 1/3/7 与 2/4/5/6 行为、bd 路由显式/隐式)→ Task 5-10;四项准入冒烟 → Task 9(①②③④)与 Task 2(③的决策部分);registry.yaml 骨架 → Task 7。wfos-upgrade skill/command、check-updates、doctor、wos-bump 均属 M2,不在本计划(spec §17 映射)。
- **偏差声明**:gate-rules.yaml → gate-rules.json(缓存快照内零依赖约束,Global Constraints 已记);Claude hooks 用默认 hooks/hooks.json 位置(spec §4 写 claude.hooks.json,实现取默认发现位置更稳,Codex 侧显式声明避免误读)。
- **占位符扫描**:无 TBD/TODO;Task 6 Step 1 与 Task 7 Step 3 引用 spec 内已写全文的示例(逐字复制,非占位)。
- **类型一致性**:`matchCommand`/`extractCommand`/`loadRules` 签名在 Task 3 定义、Task 4 消费一致;版本号 0.1.0 贯穿 Task 5/6/7 与测试断言。
