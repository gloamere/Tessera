---
name: tessera-setup
description: 当用户要安装、刷新、升级、启用、禁用、卸载、回滚或初始化 Tessera 拼图时使用。所有变更先展示影响并逐项确认；回滚只生成基于显式 Git ref 的计划。
---

# Tessera 生命周期引导

管理拼图的安装、刷新、升级、启用、禁用和卸载；回滚只生成可验证计划。所有无法证实的状态保持 `unknown`，不得猜测或用另一动作冒充。

## 统一流程

1. 识别 Codex/Claude 和 Tessera 仓库根；优先运行 `scripts/resolve_capabilities.py --host <host> --probe --format json`。脚本不可见时按 `tessera-status` 的宿主降级规则探测。
2. 让用户选择目标拼图和动作。没有明确选择时只展示候选，不执行任何变更。
3. 对每项展示：当前状态、目标状态、完整命令、影响范围、可逆性、恢复方式、验证命令和是否需重载。
4. 使用宿主原生确认能力逐项确认。一次确认只授权当前展示的一个动作；跳过项记为 `skipped`。
5. 仅执行下述白名单命令；执行后立即重新运行能力解析或宿主 `plugin list --json`，以实际状态判定成功，不能只看退出码。
6. 输出 `succeeded / failed / skipped / blocked / plan-only` 报告。动作失败只阻断依赖它的后续动作，不影响独立项。

## 候选与安装安全

- 本地拼图只取动态目录中 `catalog_state: installable` 且运行时为 `available`、`installed` 或 `active` 的来源拼图；已安装项不重复作为“新安装”。
- 外部能力只有当前宿主为 `installable`、存在 `trust_ref` 且 `trust.yaml` 安装命令逐词完全匹配时才可安装。
- `not-integrated`、candidate、`reference-only`、`unverified`、`unsupported` 只能作为信息，不进入可执行选择项。
- template-pack 仍只补缺，已有文件一律跳过；不得写入散装 skill 目录。

## 宿主动作矩阵

| 动作 | Claude | Codex |
|---|---|---|
| install | `claude plugin install <id>@tessera --scope user` | Windows: `codex.cmd plugin add <id>@tessera`；其它：`codex plugin add <id>@tessera` |
| refresh / update | `claude plugin update <id>@tessera --scope user` | 与 install 相同，由 add 刷新 |
| enable | `claude plugin enable <id>@tessera --scope user` | `unsupported` |
| disable | `claude plugin disable <id>@tessera --scope user` | `unsupported`；不得改用 remove |
| uninstall | `claude plugin uninstall <id>@tessera --scope user` | Windows: `codex.cmd plugin remove <id>@tessera`；其它：`codex plugin remove <id>@tessera` |
| rollback | 仅计划 | 仅计划 |

- Claude 变更后提示 `/reload-plugins`；Codex 变更后提示新开会话。
- 卸载不默认传 `--prune`，不移除 marketplace。卸载 `tessera-core` 前必须说明：当前会话可能仍保留旧能力，但新会话将无法调用 core。
- Codex 没有公开插件级 enable/disable 时如实报告 `unsupported`，不直接编辑私有配置。

## 回滚指导

1. 必须由用户提供明确 tag 或 commit；`latest`、`previous`、缓存目录和“上一个版本”均不够明确。
2. 仓库可见时运行：`python scripts/lifecycle_policy.py --host <host> --action rollback --piece <id> --ref <ref>`。该命令只读验证 commit、双宿主 manifest 和目标版本。
3. 展示当前 marketplace 来源、目标 commit/version、可能受影响的其它拼图以及恢复到当前 ref 的步骤。
4. 只输出宿主对应的 pinned marketplace/reinstall 人工步骤；不得切换当前工作树、使用旧缓存、自动移除或重配 marketplace。

## 硬规则

- 所有可执行变更逐项确认；永不静默安装、刷新、启停或卸载。
- 外部安装命令必须与 `trust.yaml` 完全匹配；未知 flag 或差异一律拒绝。
- 回滚、仓库结构修复和 trust 修改永远是 `plan-only`。
