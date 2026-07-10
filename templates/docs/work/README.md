# 工作包模板

每个跨会话、需要协作或值得复盘的事项都创建为本目录下的一份 Markdown 文件。推荐使用 `workflow-os work create "<名称>"` 生成它；本文件只是说明和示例，不是工作包，索引器应忽略它。

工作包的 YAML frontmatter 是稳定、可查询的摘要。`id` 创建后不得改变；每次实质修改状态、依赖或下一步时，更新 `updated_at`。完整背景、方案、反馈和验收记录写在正文，不写入 SQLite。

```markdown
---
schema: workflow-os/work-item@1
id: work-mall-ui-20260710
type: ui
status: waiting_approval
priority: high
updated_at: "2026-07-10T13:30:00+08:00"
next_action: "负责人从三套视觉方向中确认一套"
depends_on: []
approval_state: pending
clarification_summary: null
---

# 工作包：商城 UI 改造

## 目标

- 让玩家在 1080p 下能快速找到分类、余额和购买入口。

## 待澄清

- [ ] 改造范围是商城主界面、商品详情，还是后台配置？
  - 为什么重要：三者的客户端组件、发布路径和验收方式不同。
  - 建议默认：先做玩家客户端主界面。

## 已确认

- 保留现有深色金属主题。

## 待负责人拍板

- [ ] 视觉方向：方案 A / B / C。

## 范围与约束

- 修改范围：商城主界面与分类组件。
- 不修改范围：商品定价与服务端协议。

## 结果与验收

- [ ] 方案对比已完成
- [ ] 方向已确认
- [ ] 实现和截图复查已完成
```

## 字段说明

| 字段 | 说明 |
| --- | --- |
| `schema` | 固定为 `workflow-os/work-item@1`，用于让索引器识别此文件。 |
| `id` | 稳定且项目内唯一的工作包 ID；推荐 `work-<短名>-<日期>`。 |
| `type` | 事项类型，例如 `ui`、`activity`、`feature`、`operations`、`research` 或 `bugfix`。 |
| `status` | `planned`、`in_progress`、`blocked`、`waiting_clarification`、`waiting_approval`、`completed` 或 `cancelled`。 |
| `priority` | `low`、`medium`、`high` 或 `critical`。 |
| `updated_at` | ISO 8601 时间戳，表示最近一次有意义的状态更新。 |
| `next_action` | 可以直接执行的一句下一步，而不是模糊愿望。 |
| `depends_on` | 所依赖工作包的 ID 数组；没有依赖时写 `[]`。 |
| `approval_state` | `not_required`、`pending`、`approved` 或 `rejected`。UI、策划和功能方向通常从 `pending` 开始。 |
| `clarification_summary` | 描述当前最关键的待澄清点。仅在 `status: waiting_clarification` 时必填。 |

描述存在高影响歧义时，先将状态改为 `waiting_clarification`，写明 `clarification_summary` 与正文中的最少问题；总指挥提问并等待回答。被阻塞、等待澄清、等待拍板或状态不一致时，先修正 Markdown，再由总指挥运行 `workflow-os sync --render-now`。子 agent 不直接同步本地索引。
