---
schema: tessera/decision@1
id: personal-workflow-mainline
status: superseded
created: 2026-07-13
approved: 2026-07-13
review: 累积 30/90 天本地使用数据后重审拼图保留、触发边界与是否公开
superseded_by: native-first-runtime-simplification
---

# Tessera 以个人跨 Agent 工作流为主线

## 决策

Tessera 当前是维护者自己的跨 Agent 工作流控制层。核心入口收束为 router、status/doctor 与 eval；开发场景约占六成，产品策划、调研、UI 和知识沉淀约占四成。Codex 负责近期真实验收；Claude 保持 manifest 与 skill 兼容，但 CLI 或真实适配器不可用时不声称完成双端实测。

setup、生命周期、remediation、marketplace、trust、准入量表与 recipe 保留现状并冻结扩张。taste、planner、knowledge-base 保持可选，是否保留由真实使用数据决定。当前不建设 SaaS、公共排行榜、团队权限、私有注册表、通用安装器或新宿主支持。

## 本地使用数据

过去决策中的“无遥测”继续约束联网采集、后台服务和默认记录。本决策允许用户显式启用一个本地使用日志：只写 `~/.tessera`，不联网，不记录 prompt、回复、用户名、真实路径或项目名；项目只保存带本机随机 salt 的哈希。记录失败必须 fail-open，不影响原任务。外部 skill 的直接调用不可观测并需在摘要中披露。

默认保留 90 天。90 天无触发的能力进入卸载候选；持续失败或负反馈的能力先修正再决定删除；低频但高影响的诊断、恢复与安全能力可以例外。新拼图通常需要至少三次真实需求，准入评分退为参考检查而非日常仪式。

## 个人回归

核心机制案例与个人场景分开维护。个人场景固定在 20–30 条，初始为 15 个开发场景与 10 个产品场景；只因真实失败或新的高频任务替换、增加。CI 假宿主只证明基础设施闭环，模型行为结论必须来自对应宿主新会话。

## 决策纪律

这是一次高影响方向决策。此后普通功能、规则微调和拼图维护不新增 ADR；只有难逆转的产品边界、数据行为、安全模型或宿主策略变化才记录新决策。
