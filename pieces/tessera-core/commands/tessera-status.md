---
description: 查看 Tessera 拼图与外部依赖状态
---

对每块拼图输出一行状态表。步骤:

1. 运行 `claude plugin list` 取已装插件与版本(Codex 环境用 `codex plugin list`)。
2. 对市集仓库各 pieces/<id>/piece.yaml 声明的 external_deps 逐个跑 version_check(如 `bd version`)。
3. 输出表:拼图 | 版本 | 已装? | 外部依赖状态。
4. 发现异常(依赖缺失、版本探测失败)时给出对应修复建议(/tessera-setup 或手动命令)。
