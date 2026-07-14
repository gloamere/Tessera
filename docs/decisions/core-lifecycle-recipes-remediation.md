---
schema: tessera/decision@1
id: core-lifecycle-recipes-remediation
status: superseded
created: 2026-07-13
approved: 2026-07-13
review: 累积至少 10 次生命周期变更、recipe 与 remediation 真实使用后重审安全边界和输出噪音
superseded_by: native-first-runtime-simplification
---

# Core 0.2：完整生命周期、轻量 Recipe 与引导修复

## 决策

在保持纯 skills、无常驻进程、无遥测和无持久任务后端的前提下，将 setup 扩展为拼图生命周期的单一执行入口；status 报告安装版本、启用状态与宿主可用动作；router 对具有多个独立交付物的请求输出依赖有序 recipe。

doctor 默认继续只读。只有用户明确进入 remediation 模式时，才为每项修复展示完整命令、影响与验证方式，逐项确认后委托 setup 执行。可执行范围仅限宿主原生生命周期动作和 trust 完全匹配的安装动作；仓库结构、trust 修改与回滚保持 plan-only。

## 安全与宿主差异

- Claude 原生支持安装、更新、启用、禁用与卸载；Codex 仅使用公开的 add/remove，不用卸载冒充禁用，也不修改私有配置。
- 回滚必须使用用户提供且可验证的 Git tag/commit，不依赖缓存、不切换当前工作树、不自动重配 marketplace。
- 多意图失败只阻断依赖链；独立步骤可以继续并披露缺失产物。Recipe 只存在于当前会话，不成为编排引擎。

本决策取代 `core-diagnostics-vnext` 中“doctor 永不修复”的绝对边界；其诊断严重度、保守版本比较与默认只读原则继续有效。
