# M1 冒烟结果(Task 8/9/10)

日期:2026-07-11。自动化部分由 orchestrator 执行;「待人工」小节需负责人在新会话完成后回填。

## Claude 端(Task 8)

| 项 | 结果 |
|---|---|
| `claude plugin marketplace add G:/Claude/workflow-os` | ✅ Successfully added(user settings) |
| `claude plugin install wfos-core@workflow-os --scope user` | ✅ 0.1.0, user scope |
| `claude plugin install bd-tasks@workflow-os --scope user` | ✅ 0.1.0, user scope |
| 缓存快照完整性 | ✅ `~/.claude/plugins/cache/workflow-os/wfos-core/0.1.0/` 含 commands/gate-rules.json/hooks(两份)/piece.yaml/scripts/skills |
| **真实缓存路径端到端:claude ask** | ✅ `echo <force-push payload> \| node <cache>/scripts/gate.mjs --platform=claude` → 正确 ask JSON,exit 0 |
| **WFOS_GATE_DEBUG 分支** | ✅ payload 落盘 `~/.workflow-os/gate-debug.log` |

### 人工验收结果(2026-07-11,0.1.1)——**Claude 端:绿**
- [x] skills 可见:Desktop agent 会话技能清单含 `wfos-core:piece-router`、`wfos-core:wfos-setup`、`wfos-core:wfos-status`、`bd-tasks:bd-tasks`(命名空间形式 `插件名:名称`;**commands/*.md 在 Desktop 以 skill 形态暴露**,显式调用走 Skill 工具)
- [x] 门(deny 形态,负责人实测):`git push --force origin main` 被 **PreToolUse deny 在执行前拦截**(Bash 调用整体中止,git 从未运行——无 remote 的 fatal 都没出现),理由原文:`[wfos 门] 强推 main/master(规则 force-push-protected)。请确认后再执行。`
- [x] 反例:`git status` 无拦截(首轮会话已证)
- [ ] rm-rf 项目外 / trust.yaml 改写:与 force-push 同机制(deny),未单独复测,留待日常使用观察
- 备注:门在 agent 会话的正确形态 = deny + 对话内确认(ask 会被静默放行,见「遗留」根因条目);终端 harness 中其余四条 ask 规则仍会弹窗

## Codex 端(Task 9)

| 项 | 结果 |
|---|---|
| shim(M0 决策 A) | ✅ `~/.local/bin/codex.cmd` → codex-cli 0.138.0-alpha.7 |
| `codex plugin marketplace add G:/Claude/workflow-os` | ✅ Installed marketplace root: G:\Claude\workflow-os(活引用) |
| `codex plugin add wfos-core@workflow-os` / `bd-tasks@…` | ✅ 装入 `~/.codex/plugins/cache/workflow-os/<id>/0.1.0`(与 spec 附录 A 预测逐字一致) |
| **skill 注入(冒烟②相关)** | ✅ `codex debug prompt-input` 的 skills 表含 `wfos-core:piece-router`、`wfos-core:wfos-setup`、`bd-tasks:bd-tasks`(带完整中文 description);plugins 表含两插件。Codex 端 skill 命名为 `插件名:skill名` |
| **真实缓存路径端到端:codex deny** | ✅ `--platform=codex` force-push payload → stderr 理由,exit 2 |
| commands/ 在 Codex 不生效 | 预期内(commands 为 Claude 专有;Codex 用 `$skill` 显式调用) |

### 待人工(Codex Desktop 新会话)
- [ ] 冒烟①:首次会话是否要求信任 wfos-core hooks?记录信任流程:______
- [ ] 冒烟④:临时仓库执行 `git push --force origin main` → 应被拒绝且显示 `[wfos 门] 强推 main/master…`(若未触发→回报现象,走全局 `~/.codex/hooks.json` 回退,即冒烟②)
- [ ] native 路径:有未提交改动时 `git reset --hard HEAD` → 应走 Codex 原生审批而非 wfos 拒绝

## bd 路由验收(Task 10,待人工,任一端新会话)

- [ ] 显式:`/wfos-status`(Claude)或 `$skill bd-tasks`(Codex)100% 生效
- [ ] 隐式冒烟(记录命中,不设硬阈值):
  1. 「记一下:回头把 README 安装节补上」→ 期望 bd q/create
  2. 「有什么可以开工的任务?」→ 期望 bd ready
  3. 「把这次重构拆成可跟踪的任务」→ 期望 bd create --type epic + bd dep
  4. 「帮我看下任务 workflow-os-e3f 的详情」→ 期望 bd show
  5. 「不知道从哪开始,帮我规划一下这个项目」→ 期望 piece-router 触发

## 遗留

- bd 升级 1.0.2→1.1.0 因 github.com 不可达暂缓(升级链 M2 落地后经 /wfos-upgrade 补)。
- Codex `codex features list`:`hooks stable true` 但 **`plugin_hooks removed false`**——插件内嵌 hooks 疑似在该版本被运行时禁用(全局 hooks 不受影响),与 spec 附录 A 疑点吻合;若 Codex 会话实测门未触发,按计划走全局 `~/.codex/hooks.json` 回退(脚本指向仓库源路径而非版本化缓存)。
- Claude 端首轮门测试(用户新会话)显示 PreToolUse 未触发;官方文档确认:无 hooks 同意步骤、无需重启应用、Desktop 支持 PreToolUse。诊断路径:会话内 `/hooks` 看 wfos 是否注册(来源 Plugin)→ 未注册则 `/reload-plugins` 后复查 → 再跑门测试。`claude plugin details` 子命令在本机 2.1.132 尚不存在。
- 首轮「Codex 冒烟」误跑在 Claude 会话内(结果对 Codex 无效,但作为 Claude 阴性结果触发了上述诊断)。
- Desktop agent 模式实测:`/hooks`、`/reload-plugins` 面板不可用(与终端 harness 不同);终端 `claude -p` headless 在本机 403(无法用 CLI 判别)。待判别变量:**完全退出并重启 Desktop 应用**后插件 PreToolUse 是否加载(superpowers 的 hook 是应用启动前装好的,wfos 是运行中装的)。若重启后仍不触发 → 按 spec §7.2 落地原生 permissions ask 规则作为该 harness 的门载体(需负责人批准规则清单)。
- **Claude 门根因定案**:hook 正常触发,`ask` 在自治 agent 会话被静默放行、`deny` 可拦(负责人实测,2026-07-11)。已改三条硬止损规则(recursive-delete-outside / force-push-protected / self-protect)为 deny(0.1.1);原生 permissions ask 预案作废(同根:自治 agent 会话下原生 ask 弹窗同样无人可应答)。
