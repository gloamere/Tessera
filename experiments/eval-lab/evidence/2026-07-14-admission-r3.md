---
schema: tessera/eval-lab-evidence@1
date: 2026-07-14
host: codex-cli-0.144.1
model: gpt-5.6-sol
reasoning_effort: medium
repeat: 3
rounds: 2
activation: injected
decision: keep-experimental
---

# Eval Lab R3 准入复跑

## 结论

准入评审完成，Eval Lab 继续作为仓库维护实验，不进入 `tessera-core`。

两轮各自对三个案例执行 baseline 3 次、skill 3 次，共 36 次真实 Codex 调用。`planner` 的净 regression 在两轮均超过预注册阈值，证明 Eval Lab 能发现可复现的真实退化；但它依赖仓库内精确 Skill 文件、与 core 现有纯路由评测边界冲突，并且运行成本较高。

## 两轮净结果

| 案例 | R3-A baseline → skill | R3-B baseline → skill | 阈值 | 结论 |
| --- | --- | --- | ---: | --- |
| taste | 1.000 → 1.000 (`0.000`) | 0.889 → 1.000 (`+0.111`) | 0.200 | 两轮均 `no_change` |
| planner | 0.625 → 0.250 (`-0.375`) | 0.625 → 0.375 (`-0.250`) | 0.200 | 两轮均 `regression` |
| knowledge-base | 0.875 → 1.000 (`+0.125`) | 0.875 → 1.000 (`+0.125`) | 0.200 | 两轮均 `no_change` |

全部案例都是 `verified-injection`，没有 execution error。阈值在实验前固定，没有根据结果下调。

## 两轮合并的逐标准变化

每个条件每个案例共有 6 个真实样本：

- `taste`：`prioritized-actions` 从 4/6 升到 6/6；其他标准相同。属于局部增益，但净变化没有过线。
- `planner`：`audience` 从 6/6 降到 4/6，`success-metrics` 从 6/6 降到 1/6，`tradeoffs` 从 6/6 降到 5/6，`risks` 从 6/6 降到 0/6。约束和落地边界的变化跨轮不稳定，不能抵消核心信息退化。
- `knowledge-base`：`frontmatter-tags` 从 5/6 升到 6/6，`expansion-sections` 从 1/6 升到 6/6；没有损失项，但总分增益只有 `+0.125`。

因此，本实验既检测到稳定局部增益，也检测到超过实用显著性阈值的稳定净退化。

## 第二轮成本

第二轮由加入 usage 采集后的 runner 生成；数值为每个条件 3 次调用的累计 token，以及单次耗时中位数：

| 案例 | baseline / skill 耗时中位数 | baseline / skill input tokens | input delta | 注入 Skill 大小 |
| --- | --- | --- | ---: | --- |
| taste | 53.4s / 36.9s | 172,553 / 48,825 | -123,728 | 742 字符 / 1,570 bytes |
| planner | 82.3s / 30.0s | 115,821 / 64,595 | -51,226 | 735 字符 / 1,707 bytes |
| knowledge-base | 40.6s / 30.4s | 117,056 / 48,297 | -68,759 | 855 字符 / 1,672 bytes |

负 input delta 不表示 Skill 注入没有成本。Codex 的 usage 包含完整生成路径，baseline 在本轮产生了更长的回答、推理或缓存交互；静态注入成本应以 Skill 内容大小单独理解。第一轮总运行时间约 15.2 分钟，第二轮约 13.6 分钟，共约 28.9 分钟。

## 原始证据

- `codex-admission-taste-r3-a.json`、`codex-admission-taste-r3-b.json`
- `codex-admission-planner-r3-a.json`、`codex-admission-planner-r3-b.json`
- `codex-admission-kb-r3-a.json`、`codex-admission-kb-r3-b.json`

这些文件保留完整回答、逐次标准、宿主事件计数、耗时及可用的 token usage。A 轮生成时 runner 尚未采集 usage；B 轮包含该字段。

## 后续

本轮不自动修改 `planner`。若后续重写该 Skill，应预注册修复目标，以同样的案例和阈值复跑，并确认 `success-metrics` 与 `risks` 的回归消失且没有新增损失。
