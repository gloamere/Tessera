---
schema: tessera/decision@1
id: piece-admission-rubric
status: superseded
created: 2026-07-13
approved: 2026-07-13
review: 累积至少 20 次真实准入评审后复核权重与等级阈值
superseded_by: native-first-runtime-simplification
---

# 七级拼图准入体系

## 决策

任何新增、引入、拆分或独立发布拼图的请求，先由 `piece-router` 按需加载准入量表，给出满分 100 的七维评分、S/A/B/C/D/E/F 等级、封顶原因和标准建议。

评分是可解释的产品建议，不剥夺用户做临时原型的选择；但未达到正式市集门槛的方案不得被描述为成熟拼图。没有真实使用记录的方案最高为 B，只能先原型或限定范围试用。

详细分值、封顶与输出契约以 `pieces/tessera-core/skills/piece-router/references/piece-admission.md` 为单一事实来源，仓库测试案例必须与该规则一致。
