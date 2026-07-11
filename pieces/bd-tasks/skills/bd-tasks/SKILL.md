---
name: bd-tasks
description: 任何"记任务、拆任务、领任务、关任务、查任务、依赖、epic、待办、backlog、回头再做"类意图时使用。任务追踪一律走 bd (beads) CLI——禁止 TodoWrite、禁止 markdown TODO 列表。
---

# bd 任务追踪

## 命令速查

| 意图 | 命令 |
|---|---|
| 快速记一条 | `bd q "描述"`(只回 id) |
| 新建任务 | `bd create "描述"`(加 `-p 0..3` 定优先级) |
| 找可开工任务 | `bd ready` |
| 查看详情 | `bd show <id>` |
| 领取 | `bd update <id> --claim` |
| 完成 | `bd close <id>` |
| 追加备注 | `bd note <id> "内容"` |
| 大活拆解 | `bd epic create` + `bd dep add <child> <parent>` |
| 需负责人异步确认 | `bd gate`(仅作通知载体;权威状态是 docs/decisions/ 文件的 frontmatter status) |

## 规则

- 项目首次使用:先 `bd ready` 探测;报 "no beads database" 时问用户是否 `bd init`(依赖 Dolt)。
- 会话产生的后续工作项必须落 bd,不留在对话里。
- 提交代码前若任务完成,顺手 `bd close <id>`。
