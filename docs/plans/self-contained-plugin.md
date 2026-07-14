---
status: completed
date: 2026-07-14
owner: maintainer
depends_on:
  - docs/decisions/native-first-runtime-simplification.md
  - docs/decisions/self-contained-plugin-distribution.md
---

# Tessera 插件自包含与一键安装计划

## 完成定义

- `tessera-core` 缓存副本包含 eval 运行器、案例和 schema。
- 从没有 Tessera checkout 的任意项目运行 dry-run 成功。
- eval 运行时不需要 PyYAML 或 pip。
- Windows 与 macOS/Linux 均有单命令 Codex 安装入口，并验证安装结果。
- core 通过 Codex plugin validator、Skill validator、cachebuster 与重装流程。
- README 和部署文档不再要求终端用户 clone 仓库。

## 执行顺序

1. 迁移运行资产并改为 JSON/标准库。
2. 增加插件内跨平台启动器和隔离缓存测试。
3. 增加一键安装脚本及手动原生命令回退。
4. 更新双宿主文档和发布决策。
5. 运行 plugin-creator 校验、cachebuster、重装及隔离验证。

## 验收结果

- 发布版本：`tessera-core 0.6.0+codex.20260714063655`。
- 插件缓存副本在无仓库 checkout 的临时目录完成 15 个核心案例与 25 个个人案例 dry-run。
- 缓存扫描未发现开发机绝对路径、PyYAML 引用或 `__pycache__`；运行时只依赖 Python 3 标准库。
- 已安装缓存完成 `visual-review` 真实 Codex native 单案例，宿主事件观测到 `taste`，结果为 `verified`。
- PowerShell 一键安装器完成四插件安装；PowerShell 与 POSIX shell 安装器均通过语法测试。
- 仓库校验、16 个单元测试、Codex plugin validator 与 Skill validator 全部通过。
