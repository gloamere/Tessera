<div align="center">

# 🧩 Tessera

**面向个人项目的能力操作系统**
一个 Git 仓库,把 Claude Code / Codex 的可复用能力组织成「能力拼图」,并守好一道不可逆操作安全门。

[![CI](https://github.com/gloamere/Tessera/actions/workflows/ci.yml/badge.svg)](https://github.com/gloamere/Tessera/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/gloamere/Tessera?include_prereleases&label=release)](https://github.com/gloamere/Tessera/releases)
![Go](https://img.shields.io/badge/Go-1.23%2B-00ADD8?logo=go&logoColor=white)
![Platforms](https://img.shields.io/badge/platform-Windows%20·%20macOS%20·%20Linux-8a8a8a)
![Deps](https://img.shields.io/badge/dependencies-zero-2ea44f)

</div>

---

> **Tessera** —— 马赛克镶嵌块。每一块能力是一片 tessera,按需拼装成你的工作流,不要求每个项目都走完整流程。适合软件开发、游戏私服、策划、调研与 UI 协作。

核心是一个**零第三方依赖的 Go 单二进制** `tessera`:它是危险命令的门、是新机安装器、是项目初始化器、是状态体检工具——全部收在一个可执行文件里。项目的事实、决策与研究仍留在项目自己的 Markdown 里;插件和 hooks 只负责协作与执行辅助。

## ✨ 特性

| | |
|---|---|
| 🛡️ **不可逆操作门** | 每次工具调用前拦截危险命令——强推保护分支、项目外递归删除、丢弃未提交改动、白名单外全局安装、改写门自身。**按命令段精确匹配**,几乎无跨段误伤;是 fail-open 护栏而非最终安全边界。 |
| 🧩 **能力拼图** | skills / 插件 / 安装规则组织成可按需拼装的 piece;同一仓库即 Claude 与 Codex **双市集**。 |
| ⚡ **单二进制 · 零依赖** | 纯 Go,冷启动毫秒级;目标机**无需 Node、无需构建**。 |
| 🌍 **跨平台** | Windows / macOS / Linux × amd64 / arm64,CI 三平台持续验证。 |
| 📦 **一条命令分发** | GitHub Releases 发布,`tessera update` 下载 + `sha256` 校验 + 原子替换。 |

## 🚀 快速开始

### 新机器(Windows)

先下载固定版本引导脚本再执行——不把远程内容直接 pipe 进 shell,脚本走 GitHub Release 资产(`raw.githubusercontent.com` 在部分网络不可达)。

```powershell
$script = Join-Path $env:TEMP 'tessera-bootstrap.ps1'
Invoke-WebRequest https://github.com/gloamere/Tessera/releases/download/v2.0.0-beta.1/bootstrap-machine.ps1 -OutFile $script
powershell -ExecutionPolicy Bypass -File $script -InstallCodexPlugin
```

macOS / Linux 用 [`scripts/bootstrap-machine.sh`](scripts/bootstrap-machine.sh)。脚本会 clone 固定 tag、构建/取得门二进制、跑测试,并以 `tessera setup`(dry-run)展示六阶段计划与**信任复核**,审阅无误后再 `--register` 注册市集。它拒绝覆盖已有非空目录。

### 新项目初始化(只补缺,不覆盖)

```powershell
tessera init --target D:\Projects\my-game --name "My Game"   # 先加 --dry-run 可预览
```

```text
my-game/
├─ AGENTS.md               # 人工规则 + 一块带边界标记的托管区
├─ .tessera/project.yaml
└─ docs/
   ├─ PROJECT.md   目标与约束     ├─ NOW.md    当前状态
   ├─ INBOX.md     临时想法反馈    ├─ decisions/  需负责人拍板的方向
   └─ research/    可追溯的研究资料
```

## 🛡️ 门:不可逆操作护栏

门在 hook 的 `PreToolUse` 阶段读命令,按分隔符(`; && || |` 换行)**切段逐段匹配**,命中即按平台裁决:

| 规则 | 触发 | Claude | Codex |
|---|---|:---:|:---:|
| `force-push-protected` | 强推 `main` / `master` | 🚫 deny | 🚫 deny |
| `force-push-other` | 强推其它分支 | ⚠️ ask | 原生 |
| `recursive-delete-outside` | 递归删除项目外 / 盘符 / 家目录 | 🚫 deny | 🚫 deny |
| `recursive-delete-inside` | 项目内递归强制删除 | ⚠️ ask | 原生 |
| `discard-changes` | `reset --hard` / `checkout --` / `clean -f` | ⚠️ ask | 原生 |
| `untrusted-global-install` | 白名单外 `npm -g` / `pip install` | ⚠️ ask | 原生 |
| `self-protect` | 改写门配置 / 白名单自身 | 🚫 deny | 🚫 deny |

- **切段匹配**消除了跨段误伤:另一段 `echo` 里的 `main` 不再触发强推保护;一段提及受保护文件、另一段有写操作也不会被合并误判。
- **fail-open**:解析失败或异常时不阻塞工具——门是护栏,不是安全边界。
- **逃生舱**:`gate-rules.json` 的 `exempt_commands` 可精确放行特定命令;规则为数据,加规则不改代码。

> ⚠️ 门是启发式 guardrail,不能替代真正的安全边界。请同时为 GitHub `main` 启用禁止 force-push 的 ruleset。

## 🧰 CLI

```text
tessera gate --platform=claude|codex [--event=NAME]   hook 入口(读 stdin,输出裁决)
tessera setup [--root .] [--register] [--codex]       新机六阶段安装(默认 dry-run)
tessera init  --target <path> [--name <n>] [--dry-run] 为项目补齐骨架
tessera update [--version <tag>]                       下载 + 校验 + 替换门二进制
tessera doctor        仓库 / 安装环境体检
tessera piece list    列出拼图与外部依赖
tessera selftest      门内置断言自检
tessera version
```

## 🧩 能力拼图

| Piece | 说明 | 状态 |
|---|---|---|
| `tessera-core` | 内核:意图路由兜底、安装引导、状态查看、不可逆操作门 | ✅ 可用 |
| `bd-tasks` | 任务追踪:管理现有 [Beads](https://github.com/gastownhall/beads) CLI | ✅ 可用 |
| `planner` · `taste` · `knowledge-base` | 规划 / 审美 / 知识库 | 🚧 规划中 |

外部能力(Superpowers、agent-reach 等)在 [`registry.yaml`](registry.yaml) 里显式引用,**不会被静默安装**。

## 📐 工作流约定

- 方向性的 UI / 数值 / 活动 / 技术选型,先写入 `docs/decisions/`,负责人确认后再实施。
- 调研、策划、实现可并行;同一文件或存在依赖的任务不并行改。
- 外部 CLI / 插件 / Python 包必须先说明来源与影响并取得授权。

## 🛠️ 开发

```bash
go test ./...                          # 门 / CLI / 仓库校验,全 Go
make build                             # 构建本机二进制到 pieces/tessera-core/bin/
make dist                              # 交叉编译全平台 → dist/ + checksums
# Windows 无 make:scripts/build-gate.ps1 [-All]
```

发布:推 `v*` tag → GitHub Actions 服务器端交叉编译六平台、生成 checksums、发布 Release。

## 📚 文档

- [部署手册](docs/DEPLOYMENT.md) —— 机器安装、项目初始化、升级与回退
- [迁移决策](docs/decisions/go-tessera-migration.md) —— 为什么是 Go 单二进制、改名 Tessera
- [v1 归档](legacy/README.md)

<div align="center"><sub>个人能力操作系统 · 当前版本 <code>v2.0.0-beta.1</code></sub></div>
