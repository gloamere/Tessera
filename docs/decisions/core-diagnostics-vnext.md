---
schema: tessera/decision@1
id: core-diagnostics-vnext
status: approved
created: 2026-07-13
approved: 2026-07-13
review: 累积至少 10 次 doctor/status 真实使用后重审诊断项与输出噪音
---

# Core vNext：诊断、升级建议与路由解释

## 决策

在保持纯 skills、无常驻进程、无遥测的前提下扩展 `tessera-core`：新增只读 `tessera-doctor`，由 status 提供保守的版本刷新/升级建议，并让 router 在实际调用时输出简短路由依据。

doctor 不自动修复；status 不自动升级；router 不为明显简单任务增加说明。任何安装、刷新或全局变更仍需用户确认，并复用 setup/trust 的既有安全边界。
