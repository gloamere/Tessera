---
name: piece-router
description: 当用户提出一项工作但不明确用什么工具、涉及多种能力、或说"新项目""帮我规划""不知道怎么开始"时使用。本 skill 是 Tessera 的兜底路由表:把意图派发到正确的能力拼图。
---

# 拼图派发表

| 意图 | 拼图 | 调用方式 |
|---|---|---|
| 搜索、调研、查资料、读 URL、看某平台讨论 | agent-reach | Skill 工具调用 agent-reach,二级路由看其 SKILL.md |
| UI/视觉设计评审、审美判断 | taste | Skill 工具调用(未安装则提示 /tessera-setup) |
| 写代码、改功能、修 bug | superpowers 流程链 | brainstorming → writing-plans → 实现 → verification |
| 任务/待办/拆解/追踪 | bd-tasks | 直接执行 bd 命令(见 bd-tasks skill) |
| 游戏策划、方案策划 | planner | Skill 工具调用(孵化中,未装则先走 brainstorming) |
| 拼图状态/安装/升级 | tessera-core 自身 | /tessera-status、tessera-setup skill |

## 门规则(必须遵守)

1. **方向性拍板门**:设计方向、策划方案、UI 风格、技术选型属负责人拍板范围。执行会固化方向的实现前,检查 `docs/decisions/` 下关联决策文件 frontmatter——`status: approved` 才能动工;没有决策文件就先创建(status: pending)并用 AskUserQuestion 请负责人拍板。decisions 文件状态是唯一权威。
2. **不可逆操作**(强推、递归删除、丢弃改动、全局安装)已由 hook 拦截弹确认;被拦时向用户说明原因,不要绕过。

## 多意图命中

命中多块拼图时,先用 AskUserQuestion 让用户选;零命中时正常工作,不硬套拼图。
