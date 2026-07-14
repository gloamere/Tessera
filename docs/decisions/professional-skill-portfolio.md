---
schema: tessera/decision@1
id: professional-skill-portfolio
status: approved
created: 2026-07-14
approved: 2026-07-14
review: Skill 内容、目标模型发生变化，或累计 30 次真实使用后重审
---

# 专业 Skill 组合保留 taste 与 knowledge-base，删除 planner

## 决策

- **删除 `planner`**：两轮 R3 分别为 `-0.375`、`-0.250`，稳定丢失成功指标与风险分析；产品、活动和游戏策划交回宿主原生能力。
- **保留 `taste` 为独立可选插件**：五个代表案例中 1 个 improvement、4 个 no_change、0 regression；技术文档首页达到 `+0.250`，其余三个案例为正向原始变化。
- **保留 `knowledge-base` 为独立可选插件**：五个代表案例中 1 个 improvement、4 个 no_change、0 regression；冲突资料综合达到 `+0.250`，另两个案例为正向原始变化。

保留不表示所有任务都更好。两个 Skill 都继续 opt-in，默认安装仍只有 core。

## 适用范围

`taste` 的最强证据来自需要克制视觉语言、排版与明确优先级的页面评审。营销文案案例虽净增 `+0.125`，但局部丢失受众与决断项；移动引导也局部丢失用户语境。因此它不应扩张为通用产品评审或 UX 研究 Module。

`knowledge-base` 的最强证据来自需要拆分原子文件、frontmatter、双链和认知状态的研究综合。会议记录局部丢失 tags，已有笔记去重局部丢失去重表述；它不应替代任务跟踪、会议执行管理或通用文档编辑。

## 评审口径

案例、逐案例 `minimum_delta=0.200` 和 Skill 内容在提交 `b6d22ce` 中预注册。Codex `gpt-5.6-sol`、medium reasoning、受控注入，每个条件重复 3 次。组合层保留规则没有在运行前单独写入 ADR，因此本决策只采用保守解释：至少一个代表案例达到 improvement、没有任何净 regression，且局部损失被显式限制在适用范围内。

未来如果新增案例出现可复现 regression，或宿主原生能力追平全部有效差异，应优先收窄或删除 Skill，而不是降低阈值。

## 证据

完整汇总和原始报告位于 `experiments/eval-lab/evidence/2026-07-14-professional-skill-value-review.md`。
