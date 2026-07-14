---
schema: tessera/decision@1
id: eval-lab-incubation
status: approved
created: 2026-07-14
approved: 2026-07-14
review: 只有宿主提供可自包含的跨插件 Skill 内容接口，或 core 明确扩展到任务质量评测时重审
---

# Eval Lab 完成准入评审，继续留在实验区

## 决策

保留 `experiments/eval-lab/` 作为仓库维护实验，不把 runner、案例或命令包装进 `tessera-core`，也不作为用户安装 Tessera 后的默认能力。本决策已在两轮 `repeat=3` 真实 Codex 复跑后确认，不再只是等待证据的暂缓状态。

Eval Lab 的评测能力成立：`planner` 两轮分别得到 `-0.375` 和 `-0.250`，均达到预注册的 `0.200` regression 门槛；两轮合并后 `success-metrics` 从 baseline 的 6/6 降到 skill 的 1/6，`risks` 从 6/6 降到 0/6。它能发现真实且可复现的退化。

但准入对象是 Eval Lab 自身，而不是“是否能产出任意显著结果”。它不进入 core，理由是：

- 现有 `tessera-eval` 的发布边界是路由评测，不执行案例任务，并明确不建设 Prompt Lab；
- 受控注入依赖其他插件仓库中的精确 `SKILL.md`，并入 core 后无法在不复制内容或探测兄弟插件缓存的前提下保持自包含；
- 两轮共 36 次真实调用约耗时 28.9 分钟，适合维护者按需评审，不适合作为用户默认插件能力；
- `taste` 和 `knowledge-base` 都没有达到净 improvement 门槛，当前主要产出是定位 `planner` 退化，而不是证明 core 集成的持续用户收益。

## 已完成的准入检查

本轮检查结果：

1. **完成**：三个去泄露案例各完成两轮 `repeat=3`；
2. **完成**：`planner` regression 在两轮均达到阈值；
3. **完成**：报告逐标准增益和损失；`planner` 退化不可接受，不能用局部结构收益抵消目标、指标和风险缺失；
4. **完成**：报告逐次耗时、真实 token 用量、注入内容哈希与大小；fixture 结果没有混入质量结论；
5. **不适用**：本轮只声明 Codex 证据，不作 Claude 或跨宿主声明。

满足这些检查证明准入评审有效，不自动推导出准入通过。自包含边界和产品收益仍不满足，因此最终结论是不进入 core。

## 后果

- Tessera 的安装和日常使用不增加依赖或命令面。
- Eval Lab 可以继续快速修改案例与评分契约，不受 core 兼容性承诺约束。
- `planner` 的真实退化已触发删除决策；历史原始证据继续保留，不从实验记录中抹去。
- 完整证据见 `experiments/eval-lab/evidence/2026-07-14-admission-r3.md`。
