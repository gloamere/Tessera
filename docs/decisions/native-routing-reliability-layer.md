---
schema: tessera/decision@1
id: native-routing-reliability-layer
status: superseded
created: 2026-07-14
approved: 2026-07-14
review: 原生调用评测连续不可观测，或30/90天个人数据证明该控制层没有净收益时重审
superseded_by: current-runtime-architecture
---

# Tessera 采用宿主原生路由优先的可靠性控制层

## 决策

Claude Code 与 Codex 负责普通 Skill 的发现、按需加载和调用。Tessera 不再把 `piece-router` 作为所有任务的前置网关；router 只处理模糊、多个独立交付物、高风险或不可逆方向决策，以及新增能力准入。

Tessera 的核心价值依次是：验证原生调用、统一跨宿主状态与诊断、根据本地使用数据精简个人工作流。明确的 `taste`、`planner`、`knowledge-base` 等请求直接由宿主调用。

## 评测证据

路由政策分类与原生调用必须分开报告。前者可以向模型提供分类定义，只证明政策一致性；后者不得泄露路由清单或预期答案，并只把宿主事件或可信 transcript 计为 `verified`。模型自报、CI 假宿主和不可观测结果不得冒充真实调用准确率。

现有 25/25 Codex 结果重新定性为 policy baseline。只有 native 报告才能形成可观测调用基线。

## 提示边界优化

提示优化只针对 Skill `description`、router 边界和评测指令。同一 native 失败至少三次中稳定复现两次才进入人工修改；工具只给结构化建议，不自动写回，不优化用户日常提示词，也不建设通用 Prompt Lab。

## 保持不变

`setup`、marketplace、生命周期、remediation、trust、准入量表和 recipe 继续冻结扩张。本地日志仍默认关闭、仅本机、fail-open；指令式 start/finish 是 best-effort，不等同于宿主级完整遥测。本轮不引入 hooks、daemon 或联网分析。

本决策取代 `tessera-routing-principles`，并补充而不取代 `personal-workflow-mainline`。
