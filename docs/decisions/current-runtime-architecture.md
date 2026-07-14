---
schema: tessera/decision@1
id: current-runtime-architecture
status: approved
created: 2026-07-14
approved: 2026-07-14
review: 宿主原生能力或专业 Skill 价值评审出现新证据时重审
supersedes:
  - native-first-runtime-simplification
  - native-routing-reliability-layer
---

# Tessera 当前运行时架构

## 决策

Tessera 运行时只发布三个独立插件：核心 `tessera-eval`，以及可选的 `taste`、`knowledge-base`。普通任务、产品与活动策划、计划、确认、委派、插件生命周期和外部能力选择均由 Claude/Codex 原生完成。

`planner` 因两轮真实质量评审分别得到 `-0.375` 与 `-0.250` 的稳定 regression，从双宿主 marketplace、安装器、路由案例和发布目录删除。历史 evidence 保留，避免删除失败证据。

`taste` 与 `knowledge-base` 各在五个代表案例的 R3 评审中得到一个 improvement、零 regression，继续保持独立 opt-in；详细范围和限制以 `professional-skill-portfolio` 为准。

## Module 与 seam

- **宿主原生选择 Module**：Interface 是用户请求与已安装 Skill description；Implementation 由 Claude/Codex 提供，Tessera 不复制。
- **`tessera-eval` Module**：Interface 是 policy/native 案例与 JSON 报告；Implementation 自包含在插件中，只评测路由和可观察调用。
- **专业 Skill Module**：`taste`、`knowledge-base` 各自独立安装，删除任一 Module 不影响 core 或另一专业 Skill。
- **发布 seam**：Claude marketplace、Codex marketplace、安装器与校验器必须声明同一插件集合。
- **维护者质量实验**：`experiments/eval-lab` 执行真实任务质量对照，不进入 core，不扩大用户运行时 Interface。

## 不再存在的运行时 Interface

`piece-router`、`tessera-setup`、`tessera-status`、`tessera-capabilities`、`tessera-doctor`、`planner`、私有任务后端、usage events、hooks、daemon 和数据库均不属于当前产品。

## 证据规则

路由结论只接受宿主事件或可信 transcript；fixture、dry-run、policy 分类和模型自报不能冒充 native 证据。专业 Skill 是否保留则使用预注册案例的真实 baseline/skill 对照，显著退化直接进入删除或重写评审。
