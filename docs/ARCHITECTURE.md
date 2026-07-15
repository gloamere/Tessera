# 当前架构索引

本页只描述当前事实；历史演进保留在 `docs/decisions/`，不得从较早 ADR 推断现行运行时。

## 当前发布面

| Module | Interface | 状态 |
| --- | --- | --- |
| `tessera-core` / `tessera-eval` | policy/native 路由评测与 JSON 报告 | 核心、自包含 |
| `frontend-design` | 本地设计知识检索、设计系统与技术栈实现约束 | 可选，独立安装 |
| `taste` | UI、视觉、排版、配色与文案审美评审 | 可选，独立安装 |
| `knowledge-base` | Markdown 原子笔记与双链知识沉淀 | 可选，独立安装 |
| Claude/Codex 原生能力 | 普通任务、策划、计划、确认、委派、插件生命周期与外部能力 | 宿主负责 |
| `experiments/eval-lab` | 维护者运行的真实任务质量对照 | 实验，不发布 |

双宿主 marketplace 与安装器构成发布 seam；`scripts/validate_marketplace.py` 验证它们和 `pieces/` 的插件集合一致。插件之间没有硬运行时依赖。组合前端任务通过流程 seam 串联：`frontend-design` 负责构建设计系统与实现约束，`taste` 只在成品阶段负责审美复核。

## 当前有效 ADR

- [frontend-design-core-admission](decisions/frontend-design-core-admission.md)：当前 Module、Interface 与前端组合边界的事实来源。
- [professional-skill-portfolio](decisions/professional-skill-portfolio.md)：`taste`、`knowledge-base` 保留与 `planner` 删除的价值证据。
- [self-contained-plugin-distribution](decisions/self-contained-plugin-distribution.md)：插件自包含与安装 seam。
- [eval-lab-incubation](decisions/eval-lab-incubation.md)：质量实验保持仓库内，不进入 core。
- [remove-heavy-pieces](decisions/remove-heavy-pieces.md)：不引入重型任务后端或语义代码服务。
- [tessera-context-hygiene](decisions/tessera-context-hygiene.md)：Skill 上下文成本边界。
- [taste-skill-source](decisions/taste-skill-source.md)：`taste` 来源记录。
- [codex-cli-access](decisions/codex-cli-access.md)：Codex CLI 调用约束。

## 已被取代的决策链

`phase-1-scope` → `tessera-routing-principles` → `native-routing-reliability-layer` → `native-first-runtime-simplification` → `current-runtime-architecture` → `frontend-design-core-admission`。

setup/status/doctor/capability registry、piece admission router、个人控制层和仓库内旧 eval 的 ADR 都已标记 `superseded`。阅读这些文件只能用于理解历史，不能恢复已删除 Interface。

## 维护规则

1. 新增或恢复插件必须先证明相对宿主原生能力的净收益。
2. 删除 Module 时同步 marketplace、安装器、运行案例、schema、文档与验证器。
3. 改变当前运行时后新增 ADR，并把被取代 ADR 显式标记为 `superseded`。
4. 真实失败 evidence 保留；产品删除不删除历史实验记录。
