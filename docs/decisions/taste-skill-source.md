---
schema: wfos/decision@1
id: taste-skill-source
status: approved
created: 2026-07-11
approved: 2026-07-11
---

# taste-skill 来源确认

## 背景
本机未安装 taste-skill(全盘无踪影);旧码 DEFAULT_ADAPTERS 记录来源 Leonxlnx/taste-skill。Step 1 核实结果: 存在(name: taste-skill, default_branch: main, pushed_at: 2026-07-04T22:02:55Z)

## 选项
- **A**:确认收编该仓库为 taste 拼图(M3 执行)。
- **B**:来源失效或不想要 → taste 降级出默认集,pieces/taste 目录删除。

## 结论
选 **A**:确认收编,M3 执行。上游 `Leonxlnx/taste-skill` main 分支活跃(pushed_at 2026-07-04T22:02:55Z,核实时约 7 天内),来源有效,无需降级出默认集。本项无需本机执行动作,留待 M3 任务落地拼图收编。
