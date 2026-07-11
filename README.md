# workflow-os v2 — 个人能力操作系统(拼图市集)

本仓库同时是 Claude Code 与 Codex 的本地插件市集:注册、路由、安装、升级你的能力拼图(bd、agent-reach、taste、superpowers…)。

## 安装(机器级,一次)

```text
Claude:claude plugin marketplace add <本仓库路径>
        claude plugin install wfos-core@workflow-os --scope user
Codex: codex plugin marketplace add <本仓库路径>
        codex plugin add wfos-core@workflow-os
```

重启会话后运行 `/wfos-setup` 按引导安装其余拼图。

## 设计文档

- 设计 spec:`docs/superpowers/specs/2026-07-11-workflow-os-v2-design.md`
- v1 已归档:见 `legacy/README.md`
