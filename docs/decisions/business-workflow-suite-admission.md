---
schema: tessera/decision@1
id: business-workflow-suite-admission
status: approved
created: 2026-07-15
approved: 2026-07-15
review: 累计 20 次真实使用、财务边界变化、路由冲突或产品策划质量出现稳定退化时重审
supersedes:
  - frontend-design-core-admission
---

# 纳入四个轻量业务工作流插件

## 决策

Tessera 发布八个独立插件：核心 `tessera-eval`；设计与知识类 `frontend-design`、`taste`、`knowledge-base`；业务工作流 `finance-ops`、`growth-ops`、`product-planning`、`business-ops`。全部保持 opt-in，没有 MCP、hooks、常驻服务、数据库或私有任务后端。

四个业务插件借鉴 Anthropic `knowledge-work-plugins` 的 finance、marketing、product-management 与 operations 工作流，但按 Tessera 的双宿主、短上下文和原生能力边界重新编写，不复制 Claude 专属命令、连接器配置或完整上游包装。文件、表格、知识库、浏览器、计划和任务追踪继续由宿主及已安装专业能力负责。

## 路由边界

- `finance-ops`：预算、预测、对账、月结、现金流、财务报表和差异分析。默认只读，只准备待审批产物；付款、过账、报税、申报、投资/税务/审计意见不属于它。
- `growth-ops`：增长活动、内容日历、运营周报、漏斗诊断、实验和复盘。普通文案不强制加载；供应商、SOP 和容量不归它。
- `product-planning`：产品机会、用户研究综合、竞品、PRD、路线图和需要取舍的产品决策。代码实施计划、增长活动、简单清单和会话任务规划不归它。
- `business-ops`：供应商、SOP/runbook、RACI、变更、容量、资源和运营风险。它不处理增长、会计或产品方向。

组合任务按工作产物串联，而不是因插件同时安装就一起加载：产品定方向后可进入 PRD/原型/拆票；增长经验或 SOP 需要长期沉淀时再进入知识库；涉及表格或文档时调用宿主对应能力。四个业务 Skill 不复制这些下游工具。

## 安全与可评测契约

`finance-ops` 强制记录实体、期间、币种、来源、假设、异常、勾稽和审批点；不得执行高风险财务动作。`growth-ops` 强制绑定基线、指标定义、护栏、成功阈值和复盘决策。`product-planning` 强制保留不做/延后选项、成功指标、风险、开放问题和下一验证动作。`business-ops` 强制包含负责人、审批人、回退、证据与升级路径。

仓库单测锁定这些字段、无连接器边界和双宿主 manifest；核心路由集新增正例及财务投资边界反例。完整检查同时覆盖四个新路由。

## 产品策划真实质量证据

`product-planning` 使用三个预注册真实任务——团队账号/隐私 PRD、新手研究综合、资源受限路线图——进行 baseline/Skill 注入 R3，共 18 次真实 Codex 调用。结果为 2 improvement、1 no-change、0 regression、0 execution error，三个案例均为 `verified-injection`，且 `lost_criteria` 全为空。

风险标准由 baseline 的三个 0/3 提升为 Skill 的三个 3/3；成功指标在路线图案例获得正向变化，没有复现旧 `planner` 稳定丢失成功指标与风险的退化。严格要求同时出现“基线、目标、时间窗口、护栏”的标准在另外两个案例仍不稳定，因此保留为后续真实使用复测重点，不据此宣称每次输出都完整。原始报告位于 `experiments/eval-lab/evidence/codex-product-planning-r3.json`，摘要位于 `experiments/eval-lab/evidence/2026-07-15-business-workflow-admission.md`。

## 当前 Module 与 seam

- **宿主原生能力**：普通任务、计划、确认、委派、插件生命周期、文件工具和外部连接器。
- **八个独立插件**：每个插件一个主要 Skill，可单独安装和删除，无硬运行时依赖。
- **发布 seam**：Claude/Codex marketplace、安装器、manifest、piece 元数据、路由 schema 和验证器声明同一插件集合。
- **质量 seam**：静态契约进入 CI；真实 baseline/Skill 对照保留在 eval-lab evidence，不冒充普通 CI。

`piece-router`、setup/status/doctor、私有任务后端、usage events、hooks、daemon 和数据库仍不属于产品。
