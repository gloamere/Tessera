---
name: tessera-capabilities
description: 当用户要动态解析、列出或解释 Tessera 当前可用能力，询问某个 skill 是当前可调用、仅已安装、可安装还是未验证时使用。合并宿主会话、市集、piece、skill、registry 与 trust 证据，不安装或启用能力。
---

# Tessera Capabilities

生成当前宿主的动态能力目录。只读解析，不安装、刷新、启用插件或修改配置。

## 解析流程

1. 定位 Tessera 仓库根，必须能看到 `scripts/resolve_capabilities.py`。仓库不可见时，只能报告当前会话明确暴露的 skills，其余为 `unknown`。
2. 从宿主当前会话的 skill 列表收集实际可见的 Tessera skill 名称，作为 `--active-skill` 证据；不得仅因市集存在就标为 active。
3. 运行当前宿主的解析命令。Codex 示例：

```powershell
python scripts/resolve_capabilities.py --host codex --probe --active-skill piece-router --format table
```

每个当前可见 skill 都分别追加一个 `--active-skill <id>`。Claude 使用 `--host claude`；CLI 不可用时脚本保留 `unknown`，不得改写成未安装。
4. 解释两个独立状态：
   - `catalog_state`：`installable`、`reference-only`、`unverified`、`unsupported`。
   - `runtime_state`：`active`、`installed`、`available`、`unknown`、`unsupported`。
5. schema v2 还提供 `installed_version` 与 `enabled_state`。启用状态只允许 `enabled`、`disabled`、`not-installed`、`unknown`、`unsupported`、`not-applicable`；文本回退不得猜测 enabled/disabled。

## 消费规则

- `active`：当前会话可直接路由。
- `installed`：宿主已安装但当前会话未提供 active 证据；建议新开会话，不假装已经调用。
- `available`：本宿主市集可安装；需要时交给 `tessera-setup`，不得自动安装。
- `unknown`：证据不足；说明缺失证据，不降格成“未安装”。
- `reference-only` / `unverified` / `unsupported`：不可进入可调用或安装候选。

输出至少包含：能力、来源拼图、目录状态、运行时状态、启用状态、已装版本、证据。若用户只问某项能力，可以过滤展示，但状态判断仍须使用完整解析结果。
