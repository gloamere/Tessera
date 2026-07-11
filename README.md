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

## Codex 门的边界

`wfos-core` 在 Codex 使用两层 hook：`PreToolUse` 对明确禁止的 Bash 命令直接拒绝，`PermissionRequest` 仅在 Codex 本来准备请求权限时作为拒绝后备。它不会把普通命令强制变成审批弹窗；方向性决定仍必须通过工作流中的决策记录确认。GitHub 受保护分支规则才是阻止远端强推的最终边界。

## 正式部署

部署步骤已固定为“新机器安装市场一次 + 每个新项目初始化一次”。完整命令、hooks 信任与升级/回退说明见 [部署手册](docs/DEPLOYMENT.md)。新项目可直接运行：

```powershell
node <workflow-os-repo>\scripts\init-project.mjs --target <project-path> --name "项目名"
```

## 设计文档

- 设计 spec:`docs/superpowers/specs/2026-07-11-workflow-os-v2-design.md`
- v1 已归档:见 `legacy/README.md`
