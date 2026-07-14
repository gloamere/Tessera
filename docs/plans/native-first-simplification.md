---
status: completed
date: 2026-07-14
owner: maintainer
depends_on:
  - docs/decisions/native-routing-reliability-layer.md
  - docs/decisions/remove-heavy-pieces.md
---

# Tessera 原生优先精简改造计划

## 1. 目标

把 `native-routing-reliability-layer` 已批准的方向落实到代码和发布面：Codex / Claude 负责 Skill 发现、任务规划、用户确认、子代理委派及插件生命周期；Tessera 只保留宿主没有直接提供、且能证明净收益的能力。

改造完成后，默认运行时能力面收敛为：

| 能力 | 定位 | 发布方式 |
|---|---|---|
| `tessera-eval` | 验证原生 Skill 调用、稳定性与边界退化 | `tessera-core` 唯一运行时 Skill |
| `taste` | UI、视觉、排版和文案审美评审 | 独立可选插件 |
| `planner` | 非代码的游戏、内容和产品方案策划 | 独立可选插件；后续按真实使用决定保留 |
| `knowledge-base` | Markdown + 双链知识沉淀 | 独立可选插件；后续按真实使用决定保留 |
| 双宿主一致性检查 | manifest、marketplace 和 Skill frontmatter 的仓库校验 | CI / 维护者脚本，不进入会话 Skill 列表 |

## 2. 非目标

- 不重写 `tessera-eval` 的评测模型，也不把 policy 结果重新解释成原生调用证据。
- 不在本轮新增 MCP、hook、daemon、数据库、任务后端或新的宿主。
- 不替 Codex / Claude 包装新的插件安装 UI 或生命周期命令。
- 不因本次精简自动删除 `taste`、`planner`、`knowledge-base`；它们单独依据真实使用价值评审。
- 不保持已删除 Skill 名称的永久兼容代理。迁移说明替代空壳 Skill。

## 3. 目标边界

### 3.1 交回宿主原生能力

以下职责不再由 Tessera 实现：

- 根据普通任务、模糊程度或多意图选择执行层级。
- 生成会话计划、recipe、确认门和子代理编排规则。
- 插件安装、刷新、升级、启用、禁用和卸载。
- 枚举当前会话已安装或已启用插件。
- 用 Tessera Skill 再包装宿主已经提供的状态和生命周期命令。

### 3.2 Tessera 保留能力

- 区分 policy 分类与 native 调用证据。
- 从 Codex 事件或可信适配器 transcript 观察 Skill 调用。
- 对稳定复现的漏调、误调和冲突生成边界建议。
- 在 CI 中验证 Tessera 自身的双宿主发布物一致性。
- 保留具有明确输出契约的可选专业 Skill。

## 4. 分阶段实施

### 阶段 0：冻结基线

目的：确保删除工作建立在可重复的当前状态上。

1. 记录当前版本、插件清单和工作区状态。
2. 运行：

   ```powershell
   python scripts/validate_marketplace.py
   python scripts/run_routing_eval.py --host codex --mode policy --dry-run
   python scripts/run_routing_eval.py --host codex --mode native --cases pieces/tessera-core/skills/tessera-eval/references/personal-routing-cases.json --dry-run
   python -m unittest discover -s tests -p 'test_*.py'
   ```

3. 保存一份改造前 native 实测报告；若受环境限制无法实测，只保存 dry-run，并明确标记为不可比较基线。

完成条件：基线命令成功，报告中 policy/native 证据类型没有混淆。

### 阶段 1：移除运行时 router

目的：让宿主成为唯一的日常 Skill 选择器和任务编排者。

删除：

- `pieces/tessera-core/skills/piece-router/`
- `scripts/admission_score.py`
- `tests/test_admission_score.py`
- `tests/admission-cases.yaml`
- `tests/recipe-cases.yaml`

迁移：

- 把 `piece-admission.md` 中仍有价值的七维准入量表移到 `docs/reference/piece-admission.md`，作为维护者评审参考，不再通过 router 自动执行。
- 删除多意图 recipe 契约；计划、依赖顺序和委派使用宿主原生能力。
- 从个人场景案例删除对 `piece-router` 的期待。高风险、架构、多意图请求改为期待空 Skill 集合；只有明确专业请求继续期待专业 Skill。案例随后迁入插件内 `references/personal-routing-cases.json`。
- 从 README 和 `piece.yaml` 删除 router 入口；受影响的历史 ADR 保留正文，并在阶段 5 通过新决策建立 superseded 关系。

完成条件：任何普通、高风险、多意图或新增 Skill 请求都不要求加载 `piece-router`；native dry-run 中只剩直接处理、专业 Skill 和 `tessera-eval` 相关案例。

### 阶段 2：移除生命周期包装层

目的：插件生命周期完全使用 Codex / Claude 原生命令和界面。

删除：

- `pieces/tessera-core/skills/tessera-setup/`
- `scripts/lifecycle_policy.py`
- `scripts/remediation_policy.py`
- `scripts/doctor_status.py`
- `tests/test_lifecycle_policy.py`
- `tests/remediation-cases.yaml`
- `tests/doctor-cases.yaml`
- `pieces/tessera-core/commands/tessera-doctor.md`
- 与 setup/status/doctor/capabilities 对应、已无调用方的 Claude 命令包装

替换：

- README 直接链接并列出宿主原生命令：Codex 使用插件浏览器及 `codex plugin ...`；Claude 使用 `/plugin`、`claude plugin ...` 和 `/reload-plugins`。
- 部署文档只说明 Tessera 市集的添加和首次安装，不再维护第二套动作矩阵。
- 外部插件安装不再由 `trust.yaml` 命令白名单代理执行；交给宿主 marketplace、权限和确认机制。

完成条件：仓库中不存在会执行或生成宿主生命周期动作的 Tessera Skill/脚本；安装文档仍能让新用户完成首次安装。

### 阶段 3：把状态与诊断收缩为维护期 CI

目的：保留跨宿主发布一致性，不再把原生插件状态重新建模成 Tessera 运行时目录。

删除：

- `pieces/tessera-core/skills/tessera-status/`
- `pieces/tessera-core/skills/tessera-capabilities/`
- `pieces/tessera-core/skills/tessera-doctor/`
- `scripts/resolve_capabilities.py`
- `tests/test_capability_resolution.py`
- 只服务动态目录的 schema、fixture 和文档段落

重构：

- 将 `scripts/validate_marketplace.py` 缩减为维护者检查器，只验证：
  - Claude/Codex 市集包含相同的首方插件集合。
  - 每个插件 manifest 的 name/version 与市集一致。
  - 每个 Skill frontmatter 存在有效的 name/description。
  - `tessera-eval` 案例和输出 schema 可加载。
- 不再定义 `catalog_state`、`runtime_state`、`enabled_state` 等宿主状态镜像。
- `registry.yaml`、`trust.yaml` 若只剩外部候选说明则删除；候选研究移到普通文档，不作为可执行目录。

完成条件：CI 能发现 Tessera 发布物漂移，但用户会话中不再出现 status/capabilities/doctor Skill。

### 阶段 4：移除指令式本地使用记录

目的：删除默认关闭、观测不完整且要求每个 Skill 主动调用的自建遥测路径。

删除：

- `scripts/usage_events.py`
- `tests/test_usage_events.py`
- 所有 Skill 中的“可选本地使用记录”段落
- README 和 ADR 中把该日志描述为当前能力的内容

保留原则：历史 ADR 不改写，只新增 superseded 说明；将来的使用分析优先采用宿主可验证事件或人工维护的短期评测样本，不构建新的后台采集层。

完成条件：Skill 执行不再额外启动记录脚本，`~/.tessera` 不再是运行时依赖。删除前需在发布说明中提示用户自行备份或删除已有本地数据；本轮代码不主动删除用户目录。

### 阶段 5：收口发布面与文档

1. 将 `tessera-core` manifest 收敛为只发布 `tessera-eval`。
2. 更新两个 marketplace、`piece.yaml`、README 和 `docs/DEPLOYMENT.md`。
3. 新增一份替代原有控制层的决策记录，并把以下 ADR 标为 superseded：
   - `core-lifecycle-recipes-remediation.md`
   - `dynamic-capability-resolution.md`
   - `piece-admission-rubric.md`
   - `personal-workflow-mainline.md` 中依赖本地 usage events 的部分
4. 保留 `native-routing-reliability-layer.md`，新决策作为它的实现收口，不推翻 eval 证据原则。
5. 版本升级应明确标记为包含 Skill 删除的破坏性变更；发布说明列出原生替代入口。

完成条件：新会话只暴露目标能力面，旧 Skill 名称不再出现，安装与卸载路径均可验证。

## 5. 建议提交切片

每个提交保持单一可验证目标：

1. `docs: add native-first simplification plan`
2. `refactor: remove piece router and native planning wrappers`
3. `refactor: delegate plugin lifecycle to host tooling`
4. `refactor: collapse runtime status into CI parity checks`
5. `refactor: remove instruction-driven usage events`
6. `docs: publish slim runtime architecture and migration notes`

不要在同一个提交里同时删除 eval 和控制层，也不要把三个专业 Skill 的去留混入核心精简。

## 6. 验证矩阵

| 验证项 | Codex | Claude | 通过标准 |
|---|---|---|---|
| 市集可发现 | 本机实测 | CLI/环境可用时实测 | 四个目标插件均可发现 |
| core 安装 | 本机实测 | CLI/环境可用时实测 | 新会话只暴露 `tessera-eval` |
| 专业 Skill 选择 | native eval | 可信适配器；否则 unavailable | 明确请求命中，普通请求不误调 |
| 直接任务 | native eval | 同上 | 不加载已删除的 router/control Skill |
| 生命周期 | 原生插件管理器 | 原生 `/plugin` / CLI | 安装、刷新、卸载无需 Tessera 包装 |
| 仓库一致性 | CI | CI | 双 manifest/marketplace parity 通过 |
| 回归测试 | unittest | unittest | 零失败、无孤儿 fixture/schema |

Claude CLI 或可信适配器不可用时，不得把 dry-run、fixture 或模型自报记为 Claude 实测通过。

## 7. 风险与控制

| 风险 | 控制 |
|---|---|
| 用户仍使用旧 Skill 名称 | 发布说明提供原生替代命令；不保留会继续占上下文的空壳 Skill |
| 删除动态目录后失去跨宿主视图 | CI 保留发布物 parity；运行时状态由各宿主原生界面负责 |
| 删除 router 后专业 Skill 漏调 | 以 native eval 三次稳定复现为准，只调整专业 Skill description |
| 删除 usage events 后缺少长期数据 | 保留评测报告和人工案例；未来仅在有可观察宿主事件时重建 |
| 一次删除过多导致定位困难 | 按阶段和提交切片执行，每阶段独立跑完整测试 |
| 历史文档与当前行为矛盾 | 历史 ADR 标记 superseded，不直接改写批准时的内容 |

## 8. 完成定义

- `tessera-core` 运行时只包含 `tessera-eval`。
- Codex / Claude 原生负责 Skill 路由、计划、确认、委派和插件生命周期。
- 仓库不再维护宿主插件状态镜像、动作矩阵或运行时能力目录。
- 指令式本地 usage events 已移除，且不会删除用户已有数据。
- 双宿主 marketplace/manifest parity 仍由 CI 验证。
- 所有测试通过；Codex native eval 形成改造后基线；Claude 证据边界如实披露。
- README、部署文档、marketplace 和实际可调用 Skill 完全一致。

## 9. 开工门槛

计划获维护者确认后，从阶段 0 开始。每完成一个阶段先提交验证结果，再进入下一阶段；如果 `tessera-eval` 的 native 可验证通过率下降，停止后续删除并优先定位 Skill description 或测试案例是否仍引用旧控制层。

## 10. 实施结果

2026-07-14 已完成全部阶段：

- `tessera-core` 从 6 个运行时 Skill 收敛为只包含 `tessera-eval`。
- 删除 router、生命周期包装、动态能力目录、doctor/remediation、registry/trust 和指令式 usage events。
- 三个专业插件去除对自建记录和外部流程链的硬编码，改用宿主原生能力。
- 双宿主 marketplace/manifest 校验通过；本机 Codex 已刷新到 core 0.5.0、专业插件 0.2.0。
- 单元测试 11/11 通过；CI 确定性 policy/native 适配器均为 100%。
- Codex native 个人场景从改造前 23/25（92%）提升到改造后 24/25（96%），零执行错误。
- 最终单次失败的软件架构案例随后复跑 3/3 通过；另一个模糊项目候选 3 次只误调 1 次，均未达到修改 Skill description 的稳定失败门槛。
- Claude CLI 在本机不可用，因此只声明发布物结构和适配器契约通过，不声明 Claude 原生调用实测。
