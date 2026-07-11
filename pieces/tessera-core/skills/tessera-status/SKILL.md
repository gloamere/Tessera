---
name: tessera-status
description: 查看 Tessera 拼图与外部依赖的安装/版本状态。当用户问"拼图状态""装了哪些能力""依赖是否就绪""tessera status"或想体检已装能力时使用。Codex/Claude 两端通用(Codex 无 slash 命令,走本 skill)。
---

对每块拼图输出一行状态表。步骤:

1. 取已装插件与版本:Claude 跑 `claude plugin list`;Codex 跑 `codex plugin list`。
2. 对市集仓库各 `pieces/<id>/piece.yaml` 声明的 `external_deps`,逐个跑其 `version_check`(如 `bd version`)。
3. 输出表:拼图 | 版本 | 已装? | 外部依赖状态。
4. 发现异常(依赖缺失、版本探测失败)时,给出修复建议(tessera-setup skill,或手动命令)。
