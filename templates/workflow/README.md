# 工作流操作手册

## 知识与索引的边界

`docs/` 下的 Markdown 是项目的唯一事实源：它供人阅读、由 Obsidian 浏览、提交到 Git，并保存完整的设计理由、反馈和决策正文。

`.workflow/index.sqlite` 只是本机可删除、可重建的派生索引。它只保存工作包、决策、依赖和状态的结构化摘要，用来加快总指挥的状态查询与上下文组装。

- 数据只从 **Markdown → SQLite**；不要编辑 SQLite，也不要用 SQLite 覆盖 Markdown。
- `.workflow/.gitignore` 忽略 `index.sqlite`、其边车文件和 `index.lock`；它们不得提交。
- 数据库丢失、切换分支或迁移设备时，由总指挥执行 `workflow-os rebuild --render-now` 恢复。

## 每次开始

1. 总指挥读取 `docs/PROJECT.md`、`docs/NOW.md`，然后运行 `workflow-os status`。
2. 若处理已有工作包，运行 `workflow-os context <work-id>`，只读取该上下文包和必要的简报/决策。
3. 判断请求属于即时改动、工作包延续、新工作包、收集箱记录、需要先澄清的事项，还是必须先由负责人拍板的方向性事项。
4. 跨会话、需要协作或值得复盘的事项用 `workflow-os work create "<名称>"` 建立工作包；方向性事项用 `workflow-os decision create "<名称>" --work-item <work-id>` 建立决策记录。

## 工作包规则

- 小改动可直接完成；若改变当前优先级、依赖或下一步，则同时更新相应 Markdown 和 `docs/NOW.md` 的人工区。
- 设计、策划、功能方向在实现前必须进入待拍板状态，等待负责人确认。
- 一个工作包结束时记录结果、未竟事项与下一步，不记录冗长聊天过程。
- 工作包和决策的 YAML frontmatter 是可查询摘要；原因、方案、截图链接和反馈原文保留在 Markdown 正文。

## 澄清门

总指挥先读取项目文档、代码和已有 brief；能查到的事实不得反问负责人。然后按风险处理：

- 请求明确且可逆：直接执行。
- 只有低影响歧义：说明默认假设并继续执行，把假设写入工作包。
- 对范围、目标、验收、上线风险或实现方向有高影响歧义：将工作包设为 `waiting_clarification`，提出一个问题；只有一个问题无法消除关键不确定性时才增加到最多三个。
- 目标清楚但 UI、策划或功能方向有多个可行方案：建立待拍板决策，而不是把它当作澄清问题。

每个澄清问题必须说明“为什么重要”和“推荐默认值”。负责人回答后，将答案写入 `## 已确认`，清空 `clarification_summary`，恢复到 `planned`、`in_progress` 或 `waiting_approval`。

## 多 agent 调度与同步

仅在子任务能够独立推进时并行。每位子 agent 必须得到：目标、输入文件、不可修改范围、产物位置与验收标准。

- 可并行：现状盘点、资料调研、参考方案、素材清单、互不重叠文件的实现。
- 不可并行：未确定方向的实现、同一文件修改、依赖前一项输出的任务。
- 子 agent 只编辑被分配的 Markdown；不得运行 `sync`、`rebuild` 或直接操作 SQLite。
- 总指挥汇总结果、请求负责人拍板，并在状态稳定后独占运行 `workflow-os sync --render-now`。该命令只重写 `docs/NOW.md` 的自动总览区，人工备注必须保留。
- 总指挥在交付前运行 `workflow-os validate`；索引损坏、首次克隆或切换分支后使用 `workflow-os rebuild --render-now`。

## 升级与预算守卫

- `.workflow/manifest.yaml` 记录本项目已安装的工作流版本、托管模板哈希和适配器来源。运行 `workflow-os upgrade --plan` 查看可安全更新项；只有 `workflow-os upgrade --apply` 才会修改文件。
- 手工修改过的模板会被识别为本地覆盖，升级计划只报告，不覆盖。`AGENTS.md` 只更新 `workflow-os` 标记之间的托管块。
- `.workflow/agent-budget.yaml` 限制子 agent 并发、轮次、重复错误和无进展次数。总指挥每个 agent 回合后运行 `workflow-os guard`；返回 `stop` 后必须暂停并交给负责人或诊断流程。

## 常用查询

```powershell
workflow-os status
workflow-os status --json
workflow-os context <work-id>
workflow-os context <work-id> --json
workflow-os validate
```

机器可读输出优先提供给总指挥或自动化；项目负责人应主要查看 Markdown 简报、待拍板决策和 `docs/NOW.md`。
