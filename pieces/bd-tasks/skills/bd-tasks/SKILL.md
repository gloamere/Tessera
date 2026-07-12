---
name: bd-tasks
description: 用户明确要持久任务追踪、依赖图或跨会话协作时使用:路由到 bd (Beads) CLI。
---

# bd 任务追踪

## 命令速查

| 意图 | 命令 |
|---|---|
| 快速记一条 | `bd q "描述"`(只回 id) |
| 新建任务 | `bd create "描述"`(加 `-p 0..4` 定优先级(0 最高)) |
| 找可开工任务 | `bd ready` |
| 查看详情 | `bd show <id>` |
| 领取 | `bd update <id> --claim` |
| 完成 | `bd close <id>` |
| 追加备注 | `bd note <id> "内容"` |
| 大活拆解 | `bd create "标题" --type epic` + `bd dep add <child> <parent>` |
| 需负责人异步确认 | `bd gate`(仅作通知载体;权威状态是 docs/decisions/ 文件的 frontmatter status) |

## 规则

- 会话内计划优先使用宿主 agent 的计划能力;不要为单一明确任务自动创建 bd issue。
- 项目首次选择 Beads 时,先 `bd ready` 探测;报 "no beads database" 时问用户是否 `bd init`(依赖 Dolt)。
- 用户明确要求追踪、任务跨会话、存在依赖图或需要协作时,才创建或更新 bd issue。
- 若本次工作关联 bd issue,提交代码前更新或关闭它。
