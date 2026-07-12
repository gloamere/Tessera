---
schema: tessera/decision@1
id: tessera-mcp-piece-kind
status: approved
created: 2026-07-12
approved: 2026-07-12
review: 多块 MCP 拼图落地后重审注册方式是否需自动化
---

# 引入 `kind: mcp-server` 拼图类型

## 背景

Tessera 现有拼图类型:`skill`(纯指令,如 taste/planner)、`cli-wrapper`(路由到外部 CLI,如 bd-tasks 路由到 `bd`)。调研发现 **MCP** 是 Claude Code 与 Codex **两端都原生支持**的工具协议——一个 MCP server 就是一块即插即用的能力拼图,比 langchain/crewAI 那类重型运行时贴合 Tessera 的"能力拼图"定位得多。

## 决策

新增拼图类型 **`kind: mcp-server`**,承接 Tessera 薄组织器定位:

- 拼图本体仍是一块 **SKILL.md(路由 + 文档)**,不由 Tessera 自动安装 MCP server;和 `cli-wrapper` 路由到外部 `bd` 同构,只是外部依赖从 CLI 换成 MCP server,用户按文档在宿主里挂载。
- `piece.yaml` 的 `external_deps` 记录:前置(如 uv)、安装命令、**两端注册命令**(Claude `claude mcp add`;Codex `serena setup codex` 或 `~/.codex/config.toml`)。
- SKILL.md 必须**如实交代状态**:未挂载时先 `/mcp` 检查、说明"未挂载"并给安装步骤,不假装其工具已可用(承接 [[tessera-routing-principles]] 的诚实原则)。
- `platforms` 用 `{ claude: mcp, codex: mcp, gemini: unsupported, domestic: unsupported }`。

## 试点

首块:**`serena`**(语义代码 MCP:符号级检索/引用/跨文件重构),对编码为主的工作流收益最大。

`playwright-mcp`(Web,官方,MCP 原生——优于 browser-use 子进程方案)、`github-mcp-server`(仓库/PR/issue,官方)先登记进 `registry.yaml` 作候选,不实装。

## 不采纳(同期调研)

- 记忆层 mem0/letta/cognee:与"长期记忆用 Claude 内置 auto memory、无需外部 KB"决策冲突。
- 可观测 langfuse/promptfoo、网关 litellm/new-api:生产 LLM 服务基础设施或用户 cc_proxy 层,非能力拼图。
- 其余 agent 运行时/前端(goose/open-interpreter/LibreChat…):竞品 harness 或重型平台,非拼图。

## 演进

若 MCP 拼图增多且手动注册繁琐，再评估提供宿主原生的安装引导或独立、可选的工具；核心插件仍保持纯 skills，不引入二进制前置依赖。当前保持文档化即可。
