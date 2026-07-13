---
name: tessera-status
description: 查看 Tessera 拼图与外部依赖的安装/版本状态。当用户问"拼图状态""装了哪些能力""依赖是否就绪""tessera status"或想体检已装能力时使用。Codex/Claude 两端通用(Codex 无 slash 命令,走本 skill)。
---

对每块拼图输出一行状态表。步骤:

1. 取已装插件与版本:
   - Claude 跑 `claude plugin list`。
   - Codex 在 Windows 跑 `codex.cmd plugin list`；不要跑裸 `codex plugin list`，它可能解析到受 ExecutionPolicy 拦截的 `codex.ps1`。其他平台跑 `codex plugin list`。
   - 如果 Codex 命令失败，或在当前会话中只返回 `No marketplace plugins found.`，不能据此把拼图标为“未安装”。本 skill 已从插件缓存加载时，`tessera-core` 必须标为“已安装（当前会话已加载）”，版本从该 skill 所在插件根目录的 `.codex-plugin/plugin.json`（或缓存路径）读取；其他无法确认的拼图标为“未知（CLI 状态不可用）”。
2. 对市集仓库各 `pieces/<id>/piece.yaml` 声明的 `external_deps`,只执行其中明确给出的 `version_check`；没有声明就标为“无外部依赖”，不得自行猜测命令。
3. 按 `tessera-doctor` 的保守规则比较已装版与市集/manifest 版：完全相同为 `current`；基础版本相同但 build metadata 不同为 `refresh-available`；可可靠比较的市集高版本为 `update-available`；已装更高为 `ahead`；其余为 `unknown`。
4. 输出表:拼图 | 市集版本 | 已装版本 | 安装状态 | 版本状态 | 外部依赖状态。某端拿不到市集版本时标为“未提供”，版本状态必须为 `unknown`。
5. 对 `refresh-available` / `update-available` 只给当前宿主的安全重装命令：Claude 用 `claude plugin install <id>@tessera --scope user`；Codex Windows 用 `codex.cmd plugin add <id>@tessera`，其它平台用 `codex plugin add <id>@tessera`。不得自动执行；`ahead` 不建议降级。
6. 发现异常(依赖缺失、版本探测失败)时,给出修复建议(tessera-setup 或 tessera-doctor)。任何无法证实的状态都标为 `unknown`，不能标成“未安装”。
