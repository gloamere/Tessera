---
schema: tessera/decision@1
id: self-contained-plugin-distribution
status: approved
created: 2026-07-14
approved: 2026-07-14
review: eval 需要非 Python 环境运行，或宿主提供正式的插件内脚本运行时后重审
supersedes:
  - core-routing-eval
---

# Tessera 插件必须自包含运行资产

## 决策

`tessera-core` 将 eval 运行器、案例和输出 schema 全部放在 `skills/tessera-eval/` 内。安装后的 Skill 从自身绝对路径启动，不定位 Tessera 仓库，也不从仓库根读取脚本或测试数据。

案例采用 JSON，运行器只使用 Python 3 标准库。插件安装不执行 pip；报告写入用户当前项目的 `eval-results/`，不写插件缓存。

仓库根的 `scripts/run_routing_eval.py` 只作为开发期薄包装器，插件内运行器是唯一实现。CI 必须把插件复制到与仓库无关的临时目录并从另一个工作目录运行 dry-run，以证明安装缓存可独立工作。

## 一键安装

仓库提供 PowerShell 与 POSIX shell 安装器。安装器只编排 Codex 原生 `plugin marketplace add`、`plugin add` 和 `plugin list --json`，默认安装 `tessera-core`，显式 `--all` / `-All` 才安装三个专业插件。

远程一键安装必须来自已发布的 `main`。不希望执行远程脚本的用户始终可以使用文档中的两条原生 Codex 命令。

## 边界

插件安装只要求 Codex。运行 `tessera-eval` 仍要求系统可调用 Python 3；本轮不分发多平台二进制、不静默安装解释器，也不引入 Node、Go、daemon 或联网依赖。
