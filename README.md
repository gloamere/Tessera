# Tessera

`Tessera` 是面向个人项目的能力操作系统：用一个 Git 仓库组织 Codex / Claude 可复用的 skills、插件、安装规则和安全门。

它适合软件开发、游戏私服、策划、调研和 UI 协作。能力可以按需安装，不要求每个项目走完整流程。

> 当前版本：`v2.0.0-beta.1`。项目事实、决策与研究资料仍保留在项目自己的 Markdown 中；插件和 hooks 只负责协作与执行辅助。

## 快速开始：新机器

在联网 Windows 机器上，先下载固定版本脚本，再执行。不要把远程内容直接 pipe 到 shell。脚本从 GitHub Release 资产下载（`raw.githubusercontent.com` 在部分网络不可达，Release 资产可达）。

```powershell
$script = Join-Path $env:TEMP 'tessera-bootstrap.ps1'
Invoke-WebRequest https://github.com/gloamere/Tessera/releases/download/v2.0.0-beta.1/bootstrap-machine.ps1 -OutFile $script
powershell -ExecutionPolicy Bypass -File $script -InstallCodexPlugin
```

脚本会检查 Git 与 Go、clone 固定 tag、构建门二进制、运行测试，并跑 `tessera setup`（dry-run）展示六阶段计划与信任复核。它拒绝覆盖已有非空目录。传入 `-InstallCodexPlugin` 则计划里包含 Codex 注册命令。

审阅信任复核无误后，执行注册（`--register`），再在 Codex/Claude 新开会话启用 `tessera-core`。

## 新项目初始化

每个项目只需初始化一次：

```powershell
& $HOME\tessera\pieces\tessera-core\bin\tessera.exe init `
  --target D:\Projects\my-game `
  --name "My Game"
```

先加 `--dry-run` 可预览。初始化器只补缺，不覆盖已有代码、文档或人工 `AGENTS.md` 规则。

它会建立：

```text
my-game/
  AGENTS.md
  .tessera/project.yaml
  docs/
    PROJECT.md       # 目标与约束
    NOW.md           # 当前状态
    INBOX.md         # 临时想法与反馈
    decisions/       # 需要负责人拍板的方向
    research/        # 可追溯的研究资料
```

## 能力拼图

- `tessera-core`：路由、安装引导、状态入口与不可逆命令门。
- `bd-tasks`：基于 Beads CLI 的任务追踪能力。
- `registry.yaml`：外部能力引用，例如 Superpowers、agent-reach、Taste；它们不会被静默安装。

## 安全边界

- 方向性 UI、数值、活动和技术选型必须先写入 `docs/decisions/`，负责人确认后再实施。
- Codex 的 `PreToolUse` 会拒绝明确禁止的危险 Bash 命令；`PermissionRequest` 只是原生权限审批的后备，不能把普通命令强行变成弹窗。
- hooks 是 guardrail，不是最终安全边界。对 GitHub `main` 启用禁止 force push 的 ruleset。
- 外部 CLI、插件和 Python 包必须先说明来源与影响，并取得负责人授权。

## 文档

- [部署手册](docs/DEPLOYMENT.md)：机器安装、项目初始化、升级和回退。
- [v2 设计规格](docs/superpowers/specs/2026-07-11-workflow-os-v2-design.md)
- [v1 归档说明](legacy/README.md)

## 本地验证

```powershell
go test ./...   # 门、CLI、仓库/hook 校验(全 Go)
```
