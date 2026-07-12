---
name: serena
description: 需要语义级代码能力(大型/陌生代码库按符号找定义与引用、跨文件精确重构、符号级编辑)时使用。serena 是经 MCP 挂载的外部工具,不是宿主自带 skill——未挂载时如实说明并给安装命令,不假装其工具已可用。
---

# serena(语义代码 MCP)

serena 通过 **MCP** 给 Claude Code / Codex 加语义代码工具(符号检索、引用查找、精确符号编辑),适合大型或陌生代码库。它是**外部 MCP server**,不是本仓库 skill。

## 何时路由到它

- 按符号 / 定义 / 引用导航,而非纯文本 grep
- 跨文件重构、精确到符号的编辑
- 陌生大仓库的结构化理解

小改动、单文件、grep 够用时**不必**用它——宿主自带 read/grep/edit,省 token。

## 如实交代 + 安装(未挂载时)

先确认宿主是否已连 serena(运行 `/mcp` 查看)。**未连则说明"serena 未挂载"**,并按当前宿主给安装步骤,不假定其工具已存在。

前置:装 [uv](https://docs.astral.sh/uv/),然后安装 serena:

```bash
uv tool install -p 3.13 serena-agent
```

**Claude Code**(全局):

```bash
claude mcp add --scope user serena -- serena start-mcp-server --context claude-code --project-from-cwd
```

**Codex CLI**:

```bash
serena setup codex
# 或手动加到 ~/.codex/config.toml:
# [mcp_servers.serena]
# command = "serena"
# args = ["start-mcp-server", "--project-from-cwd", "--context=codex"]
```

`--context claude-code` / `--context=codex` 会裁掉与宿主重复的工具(文件读 / shell / 行编辑),避免 token 预算浪费。装好后用 `/mcp` 确认连接。
