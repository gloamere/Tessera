---
name: tessera-status
description: 查看 Tessera 拼图的安装版本、启用状态、升级状态、可用生命周期动作与外部依赖。Codex/Claude 两端通用。
---

# Tessera Status

对每块拼图输出一行可验证状态；`unknown` 不得解释成未安装或禁用。

## 日常视图与本地使用记录

- 默认运行 `scripts/resolve_capabilities.py --host <host> --probe --view quick --format json`，只显示首方拼图、已安装/可用能力和异常项。用户明确要求“详细/全部能力”时改用 `--view all`。
- 常用能力目录已经并入 status；`tessera-capabilities` 只作为兼容入口，不应优先引导。
- 用户明确要求启用、停用、汇总、反馈或清空本地使用记录时，调用 `scripts/usage_events.py` 的 `enable / disable / summary / feedback / purge`。执行前说明配置位于 `~/.tessera/config.json`、事件位于 `~/.tessera/usage/events.jsonl`，且不记录提示正文或真实项目路径。
- `summary --days 30|90` 输出触发数、完成/失败/未完成、完成率、显式有效反馈、项目数和按 skill/host 汇总，并注明无法观测外部 skill 的直接调用。
- 本 status 自身也先尝试 `start --host <host> --skill tessera-status --project <cwd>`；只有返回事件 id 时，结束前运行 `finish --event-id <id> --host <host> --skill tessera-status --outcome completed|failed --project <cwd>`。未启用或记录失败时静默跳过。

## 探测

1. 能定位仓库时优先运行上面的 quick 命令，读取 schema v2 的 `runtime_state`、`installed_version` 与 `enabled_state`。
2. 脚本不可见时运行宿主 `plugin list --json`。Codex Windows 使用 `codex.cmd`；JSON 不可用才回退纯文本列表，此时只能证明安装，启用状态必须为 `unknown`。
3. CLI 失败但当前 skill 已加载时，`tessera-core` 记为已安装且当前会话 active；CLI 能见度与无法证实的安装版本/启用状态记为 `unknown`。
4. 对 `piece.yaml` 声明的外部依赖只运行明确的 `version_check`；未声明即“无外部依赖”。

## 状态与输出

- 版本比较保持：`current / refresh-available / update-available / ahead / unknown`。
- 启用状态保持：`enabled / disabled / not-installed / unknown / unsupported / not-applicable`。当前会话 active 是 enabled 的更强证据。
- 输出列：`拼图 | 市集版本 | 已装版本 | 安装状态 | 启用状态 | 版本状态 | 可用动作 | 外部依赖`。
- 可用动作按宿主矩阵计算：Claude 可 install/update/enable/disable/uninstall；Codex 可 add/remove，但 enable/disable 为 unsupported；rollback 始终是 plan-only。
- `disabled` 仍是已安装，不能列入新安装候选；`unknown` 不得给出破坏性动作建议。

对 refresh/update 只给 setup 的安全动作，不自动执行；`ahead` 不建议降级。异常时引导 `tessera-doctor`，需要变更时引导 `tessera-setup`。
