---
schema: tessera/eval-lab-evidence@1
date: 2026-07-14
host: codex-cli-0.144.1
model: gpt-5.6-sol
reasoning_effort: medium
repeat: 3
activation: injected
preregistered_commit: b6d22ce
cases_sha256: bb90ac5e6d2eeacb9891cb4115dacfe66d37cb0b9f31b2d5b7fff07076fdd7e9
decision: keep-taste-and-knowledge-base-retire-planner
---

# 三个专业 Skill 价值评审

## 组合结论

| Skill | 代表案例 | improvement | no_change | regression | 决策 |
| --- | ---: | ---: | ---: | ---: | --- |
| `taste` | 5 | 1 | 4 | 0 | 保留，独立 opt-in |
| `knowledge-base` | 5 | 1 | 4 | 0 | 保留，独立 opt-in |
| `planner` | 1 个案例、两轮 R3 | 0 | 0 | 2 | 删除 |

`taste` 与 `knowledge-base` 本轮共执行 60 次真实 Codex 调用，没有 unverified 或 execution error。`planner` 使用前一轮已提交的两组 R3 证据；没有为了删除结论重复消耗同一案例。

## taste

Skill SHA-256：`035bd3dbfe6031b968026dda0227fc116e488b30c3a17bb298831c7b478b2aa2`。

| 案例 | baseline | skill | delta | verdict | 局部变化 |
| --- | ---: | ---: | ---: | --- | --- |
| SaaS 落地页 | 0.750 | 0.875 | +0.125 | no_change | 增：模板诊断、优先行动；无损失 |
| 运营仪表盘 | 1.000 | 1.000 | 0.000 | no_change | 优先级通过率上升；天花板明显 |
| AI 营销文案 | 0.500 | 0.625 | +0.125 | no_change | 增：语气、原句诊断、三类替换；失：受众、决断 |
| 移动新手引导 | 0.875 | 1.000 | +0.125 | no_change | 增：流程长度、优先级；失：用户语境 |
| 技术文档首页 | 0.750 | 1.000 | +0.250 | improvement | 增：排版、结论；无损失 |

五案例 delta 中位数 `+0.125`。保留范围是视觉/排版/反模板审美评审，不扩张为通用产品策划或用户研究。

## knowledge-base

Skill SHA-256：`b2bcfaa832ed625219489849ce65d4287a3840dbcbc3e336b039fd485b821573`。

| 案例 | baseline | skill | delta | verdict | 局部变化 |
| --- | ---: | ---: | ---: | --- | --- |
| 散落研究笔记 | 0.875 | 1.000 | +0.125 | no_change | 增：展开章节；无损失 |
| 会议决策 | 0.875 | 1.000 | +0.125 | no_change | 增：多文件；失：tags |
| 故障复盘 | 1.000 | 1.000 | 0.000 | no_change | 根因边界通过率上升；天花板明显 |
| 冲突资料综合 | 0.750 | 1.000 | +0.250 | improvement | 增：多文件、frontmatter；无损失 |
| 已有笔记去重 | 0.875 | 0.875 | 0.000 | no_change | 增：双链、安装边界；失：去重表述 |

五案例 delta 中位数 `+0.125`。保留范围是个人 Markdown 原子笔记和双链沉淀，不替代任务跟踪、会议执行或通用文档系统。

## planner

`planner` 两轮 R3 分别为 `-0.375`、`-0.250`，且 `success-metrics` 从 baseline 6/6 降到 skill 1/6，`risks` 从 6/6 降到 0/6。证据见 `2026-07-14-admission-r3.md`。这不是适用范围可接受的局部取舍，已从发布面删除。

## 成本

`taste` 批次累计模型耗时约 21.36 分钟，`knowledge-base` 约 20.99 分钟，共约 42.35 分钟。全量质量评审适合版本或 Skill 内容变化时人工运行，不进入普通 CI。

真实 token usage 受回答路径影响：

- `taste` baseline/skill input tokens：621,482 / 258,699；
- `knowledge-base` baseline/skill input tokens：543,533 / 242,151。

负差不表示注入没有静态上下文成本；Skill 文件大小与 SHA 应单独记录。

## 原始证据

- `codex-value-review-taste-r3.json`
- `codex-value-review-knowledge-base-r3.json`

两个文件保留全部 60 次回答、逐标准结果、宿主事件、token usage 与耗时。
