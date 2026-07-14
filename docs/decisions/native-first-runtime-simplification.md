---
schema: tessera/decision@1
id: native-first-runtime-simplification
status: approved
created: 2026-07-14
approved: 2026-07-14
review: 宿主移除关键原生能力，或 native eval 证明精简后持续退化时重审
supersedes:
  - phase-1-scope
  - core-lifecycle-recipes-remediation
  - dynamic-capability-resolution
  - piece-admission-rubric
  - personal-workflow-mainline
---

# Tessera 删除原生能力包装层

## 决策

Tessera 运行时只保留 `tessera-eval` 和三个独立可选专业 Skill：`taste`、`planner`、`knowledge-base`。Claude/Codex 原生负责 Skill 发现、计划、Goal、确认、子代理委派、插件生命周期、安装状态和外部能力选择。

删除 `piece-router`、`tessera-setup`、`tessera-status`、`tessera-capabilities`、`tessera-doctor`，以及只服务这些入口的动态能力目录、动作矩阵、remediation、registry/trust 和 recipe 实现。

## 理由

两端宿主已经直接提供插件管理、Skill 自动调用和任务协调。继续包装会产生第二份状态模型、重复确认和额外上下文税，并让评测把“是否触发 Tessera 控制层”误当成任务正确性。

改造前 Codex native 个人场景基线为 23/25（92%）：竞品调研只加载 `planner` 而没有加载 router；未验证外部能力请求加载了 setup 而不是 router。这两个失败反映旧预期与宿主原生选择冲突，而不是专业 Skill 能力不足。

## 保留边界

- `tessera-eval` 继续区分 policy 与 native 证据；模型自报不能成为 verified。
- CI 继续检查双宿主 marketplace、manifest、piece 和 Skill frontmatter 一致性，但不探测或镜像运行时插件状态。
- 七维准入量表保留为维护者 reference，不再作为自动路由门。
- 三个专业 Skill 保持独立 opt-in，后续按真实任务质量单独评审。

## 本地记录

删除指令式 usage events。它默认关闭、无法观察外部 Skill，且要求每个 Skill 主动执行脚本。已有 `~/.tessera` 数据不自动删除。未来使用 native eval 报告和人工维护的代表案例判断边界，不引入新的后台采集层。

## 迁移

0.5 是包含 Skill 删除的破坏性版本。旧 router、setup、status、capabilities 和 doctor 请求应改用宿主原生能力；不保留会继续占用上下文的兼容空壳。
