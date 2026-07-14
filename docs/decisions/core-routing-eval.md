---
status: superseded
date: 2026-07-13
superseded_by: self-contained-plugin-distribution
---

# tessera-eval 采用仓库内可复跑评测集

## 决策

在 `tessera-core` 内增加 `tessera-eval` skill，以 `tests/routing-cases.yaml` 作为路由行为案例的单一事实来源，由 `scripts/run_routing_eval.py` 调用宿主并生成逐案例 JSON 报告。

Codex 使用本机 CLI 已验证的无交互、临时、只读执行接口。Claude 在 CLI 接口未验证或未安装时不假定可用；通过受约束的 stdin/stdout 适配器接入，并显式报告不可用状态。

CI 使用确定性假宿主验证评测基础设施，不将其结果当作模型质量。真实行为验收仍需分别在 Codex/Claude 新会话运行。

## 指标

同时保留整套通过率和已完成案例的路由正确率。错误至少分为误调用、漏调用、多意图错误、其他路由错误和执行错误，避免基础设施失败被模型准确率掩盖。

## 边界

本轮只评测路由，不执行案例任务，不增加遥测、常驻进程、数据库或自动线上门禁。评测输出默认不进入版本控制。
