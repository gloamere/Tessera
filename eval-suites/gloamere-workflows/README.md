# Gloamere Workflows 评测套件

本目录只覆盖官方 skills-only 包中的三个工作流：

- `gloamere-product-decision`
- `gloamere-visual-review`
- `gloamere-knowledge-capture`

`admission-v2.json` 包含 102 个中英文路由案例。每个 Skill、每种语言包含
6 个正例、8 个相邻负例和 3 个多意图例。案例只定义输入和期望，不代表已
产生执行证据。

`risk-tiered-v2.json` 是调用预算与选择规则的事实来源：

- PR 仅在 Skill 或路由元数据变化时，每个变更 Skill 选择 4 例，最多 12 次；
- release 使用 16 个基础案例，每个变更 Skill 增加 4 例，失败复验后仍不得
  超过 40 次；
- exhaustive 首次目录提交或兼容边界变化时，先覆盖全部 102 个唯一案例且
  每例只跑一次；只有初始覆盖全部完成后才复验异常，硬上限 120 次，最多为
  9 个异常各容纳两次复验。超出预算的异常保持 `pending`。

同一异常最多形成三次尝试；2/3 重现才是确认失败，1/3 为 `pending`。持续
不可观测、基础设施错误或预算耗尽同样不得自动放行。旧的固定
`repeat=3 × independent_batches=2` 规则已废止，因为重复相同输入会消耗
816 次调用，却没有扩大行为边界覆盖。

`quality-v1.json` 另外预注册每个 Skill 的中英文黄金任务。它使用证据忠实度、
可执行性、边界遵守和无虚构四项语义 rubric；精确子串或关键词命中不能作为
发布证据。fixture 必须复制到隔离工作区后执行，不能原地修改。

报告必须绑定 Skill、suite、policy、target lock、模型和 Codex CLI 兼容身份。
完全匹配的未变更 Skill 证据可以复用；任一身份字段变化都必须重新评测相应
范围。
