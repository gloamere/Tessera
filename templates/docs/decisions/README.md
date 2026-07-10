# 决策模板

本目录记录需要负责人拍板，以及已经确认、拒绝或被替代的策划、UI 与功能决策。推荐用 `workflow-os decision create "<名称>" --work-item <work-id>` 新建记录；本文件是说明和示例，不是决策记录，索引器应忽略它。

决策的 YAML frontmatter 只保存可查询状态；方案理由、对比材料、截图、投票或反馈原文保留在 Markdown 正文。决策从 `pending` 变为 `confirmed` 前，不得把其方向当作正式实现依据。

```markdown
---
schema: workflow-os/decision@1
id: decision-mall-ui-visual-20260710
work_item: work-mall-ui-20260710
status: pending
updated_at: "2026-07-10T13:30:00+08:00"
---

# 决策：确认商城视觉方向

## 需要负责人确认

- [ ] 选择方案 A：深色金属 + 强分类层级
- [ ] 选择方案 B：低装饰 + 高信息密度
- [ ] 选择方案 C：主题插画 + 分区卡片

## 比较依据

- 1080p 下的可读性与操作路径。
- 客户端现有组件和实现成本。
- 与当前游戏世界观的一致性。

## 最终结论

确认后记录选择、确认人、日期及需要回传给工作包的约束。
```

## 字段说明

| 字段 | 说明 |
| --- | --- |
| `schema` | 固定为 `workflow-os/decision@1`，用于让索引器识别此文件。 |
| `id` | 稳定且项目内唯一的决策 ID；推荐 `decision-<短名>-<日期>`。 |
| `work_item` | 关联工作包的 ID，必须指向 `docs/work/` 中存在的工作包。 |
| `status` | `pending`、`confirmed`、`rejected` 或 `superseded`。 |
| `updated_at` | ISO 8601 时间戳，表示最近一次有意义的状态或结论更新。 |

负责人确认后，更新本文件和关联工作包的 `approval_state`，再由总指挥运行 `workflow-os sync --render-now`。若新决策替代旧决策，将旧记录标记为 `superseded`，不要删除历史。
