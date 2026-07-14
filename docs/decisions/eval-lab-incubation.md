---
schema: tessera/decision@1
id: eval-lab-incubation
status: approved
created: 2026-07-14
approved: 2026-07-14
review: Codex 配额恢复后完成去泄露案例的 repeat>=3 复跑
---

# Eval Lab 暂留实验区，不进入 tessera-core

## 决策

保留 `experiments/eval-lab/` 作为独立实验，不把 runner、案例或命令包装进 `tessera-core`，也不作为用户安装 Tessera 后的默认能力。

初次真实 Codex 对照证明它能发现同一次 Skill 应用中的具体增益与退化，但三个案例均未达到预注册的 `0.200` 净变化阈值；两个案例还有 baseline 天花板效应。当前证据足以验证实验方向，不足以证明 core 集成的持续收益。

## 准入门槛

进入 core 前必须同时满足：

1. 对去除答案结构泄露的案例以 `repeat >= 3` 真实复跑；
2. 至少一个案例在预注册阈值下得到可归因且稳定的 improvement 或 regression；
3. 报告所有 `lost_criteria`，任何接受的退化都有明确取舍说明；
4. 报告运行时间与上下文开销，不把确定性假宿主结果当作质量证据；
5. 若宣称支持 Claude 或跨宿主，先增加并验证对应真实宿主适配器。

## 后果

- Tessera 的安装和日常使用不增加依赖或命令面。
- Eval Lab 可以继续快速修改案例与评分契约，不受 core 兼容性承诺约束。
- 配额恢复后的复跑是下一次准入评审的输入，不自动触发集成。
