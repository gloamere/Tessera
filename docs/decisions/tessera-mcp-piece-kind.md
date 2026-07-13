---
schema: tessera/decision@1
id: tessera-mcp-piece-kind
status: superseded
created: 2026-07-12
approved: 2026-07-12
review: 2026-07-13 因首个试点过重而撤回，见 remove-heavy-pieces
---

# 引入 `kind: mcp-server` 拼图类型

## 背景

Tessera 现有拼图以 `skill`（纯指令，如 taste/planner）为主。调研曾认为 **MCP** 是 Claude Code 与 Codex 两端都原生支持的工具协议，可以作为即插即用的能力拼图。

## 决策

新增拼图类型 **`kind: mcp-server`**,承接 Tessera 薄组织器定位:

- 拼图本体仍是一块 **SKILL.md(路由 + 文档)**,不由 Tessera 自动安装 MCP server；用户按文档在宿主里挂载。
- `piece.yaml` 的 `external_deps` 记录前置、安装命令与两端注册命令。
- SKILL.md 必须**如实交代状态**:未挂载时先 `/mcp` 检查、说明"未挂载"并给安装步骤,不假装其工具已可用(承接 [[tessera-routing-principles]] 的诚实原则)。
- `platforms` 用 `{ claude: mcp, codex: mcp, gemini: unsupported, domestic: unsupported }`。

## 试点

首个语义代码 MCP 试点在实际使用中被认为过重，已于 2026-07-13 从市集与路由中撤下。该结果同时否定了本决策中“先落地再评估重量”的顺序。

`playwright-mcp`(Web,官方,MCP 原生——优于 browser-use 子进程方案)、`github-mcp-server`(仓库/PR/issue,官方)先登记进 `registry.yaml` 作候选,不实装。

## 不采纳(同期调研)

- 记忆层 mem0/letta/cognee:与"长期记忆用 Claude 内置 auto memory、无需外部 KB"决策冲突。
- 可观测 langfuse/promptfoo、网关 litellm/new-api:生产 LLM 服务基础设施或用户 cc_proxy 层,非能力拼图。
- 其余 agent 运行时/前端(goose/open-interpreter/LibreChat…):竞品 harness 或重型平台,非拼图。

## 演进

本决策已被 `remove-heavy-pieces` 取代。MCP 能力仍可作为候选研究，但必须先证明相对宿主原生能力有明确净收益且足够轻量，才能进入拼图市集。
