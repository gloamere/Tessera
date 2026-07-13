---
status: approved
date: 2026-07-13
---

# 动态能力解析采用证据合并目录

## 决策

Tessera 不再把 router 的静态派发表当作能力安装与激活状态的事实来源。新增轻量解析器，从宿主对应市集、`piece.yaml`、skill frontmatter、`registry.yaml`、`trust.yaml` 和可选的宿主 CLI 只读探测合并能力目录。

能力目录分离：

- `catalog_state`：能力在当前宿主是否 `installable`、`reference-only`、`unverified` 或 `unsupported`。
- `runtime_state`：能力在当前会话/机器是 `active`、`installed`、`available`、`unknown` 或 `unsupported`。

schema v2 在不改变上述语义的前提下，为本地能力增加 `installed_version` 和 `enabled_state`。探测优先使用宿主 `plugin list --json`；文本回退只能证明安装时，启用状态保持 `unknown`。

当前会话明确暴露的 skill 是 active 的最高优先级证据；CLI 已安装证据不能代替会话激活证据。探测失败保持 unknown，不推断为未安装。

## 消费者

`piece-router`、`tessera-setup` 与 `tessera-status` 读取同一动态目录。静态派发表只保留为意图示例和仓库不可见时的降级提示。

## 边界

解析器是按需运行的 Python 脚本，不引入 daemon、MCP、数据库、遥测或自动安装。外部能力仍需同时满足宿主 `installable`、有效 `trust_ref` 和安装命令完全匹配，才能进入安装候选。
