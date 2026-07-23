# Gloamere Workflows 路由准入套件

`admission-v1.json` 是 `gloamere-workflows` 首发四个稳定 Skill 的路由准入基线。它只定义输入、预期和禁止命中，不包含也不暗示任何实际运行结果。

## 覆盖范围

每个 Skill 在每种语言中都包含：

- 6 个正例：任务应只命中目标 Skill；
- 8 个相邻负例：覆盖最容易误路由的相邻任务与明确边界；
- 3 个多意图例：分别与另外三个稳定 Skill 组合，要求一次完整命中全部意图。

每个相邻负例还带有 `risk:ordinary` 或 `risk:high` 标签。涉及付费投放、
公开发布活动、外部受访者执行或财务审批流程的越界按高风险统计；其余边界
按普通风险统计。

中文与英文案例按相同 ID 主干镜像，只有 `.zh` / `.en` 后缀不同。提示词不点名 Skill，预期直接使用稳定 ID：

- `gloamere-ui-system`
- `gloamere-visual-review`
- `gloamere-knowledge-capture`
- `gloamere-product-decision`

每个案例都显式携带 `plugin_id: "gloamere-workflows"`，避免脱离插件身份解释同名 Skill。

## 执行约定

正式准入必须在两个彼此独立的新任务批次运行，每个案例在每批使用 `repeat=3`。两个批次不得复用同一任务上下文、缓存事件或目标锁文件；每批都应重新检查已安装插件版本、完整 Skill 路径和 SHA-256。

推荐的发布门槛为：

- 受支持环境的身份可验证率为 100%；
- verified exact-match 不低于 95%；
- 高风险越界为零；
- 普通 over-route 不高于 2%；
- 多意图完整命中率不低于 90%。

`unobservable`、`unavailable`、`identity_conflict` 和 `execution_error` 不是通过证据，不得计入 conditional accuracy 的分母或伪装成 `verified`。

## 证据有效期

本文件是案例定义，不是证据文件。任何报告都必须绑定当次目标锁中的插件 ID、插件版本、完整 Skill 路径和 SHA-256。Skill 内容或路径变化后，旧报告不能跨 SHA 继承；应在当前 SHA 上重新完成两个批次和全部重复运行。
