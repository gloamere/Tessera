# 业务工作流插件准入记录

## 范围

2026-07-15 新增四个 opt-in Skill：`finance-ops`、`growth-ops`、`product-planning`、`business-ops`。它们均为轻量文本工作流，不包含 MCP、hooks、数据库或任务后端。

静态验证覆盖双宿主 manifest、piece 元数据、Skill frontmatter、最新 Codex 插件 manifest、关键输出契约和高风险边界。核心路由集从 18 个扩展到 23 个案例，并加入四个业务正例、财务投资边界和产品策划组合任务。

## Product planning R3

运行命令使用 `gpt-5.6-sol`、`activation: injected`、每个条件重复 3 次。三个任务分别为团队账号/隐私 PRD、新手研究综合和资源受限路线图。阈值 `minimum_delta=0.200`，案例与标准在运行前写入 `experiments/eval-lab/cases.json`。

| 案例 | baseline | Skill | delta | verdict | lost criteria |
| --- | ---: | ---: | ---: | --- | --- |
| team accounts | 0.375 | 0.750 | +0.375 | improvement | 无 |
| onboarding research | 0.500 | 0.750 | +0.250 | improvement | 无 |
| roadmap tradeoff | 0.625 | 0.750 | +0.125 | no-change | 无 |

汇总：2 improvement、1 no-change、0 regression、0 execution error，三个案例均为 `verified-injection`。风险标准在三个案例都由 0 提升为 1.0；成功指标在路线图案例由 0 提升到 0.333。另两个案例的严格组合标准仍为 0，说明“基线+目标+时间窗口+护栏”的稳定性仍需通过真实使用继续观察，但没有发生相对 baseline 的标准丢失。

原始报告：`codex-product-planning-r3.json`，包含 18 次回答、逐标准通过率、Skill SHA-256、耗时与 token usage。

## 准入结论

四个插件进入可选发布面。`product-planning` 通过当前准入规则：至少一个显著 improvement、无净 regression、无局部丢失，并修复旧 `planner` 的风险退化。该结论不扩展到活动策划；活动及增长闭环由 `growth-ops` 负责。财务结论始终要求专业人员复核，插件不得执行付款、过账、申报或审批。
