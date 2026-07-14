# Eval Lab（实验性）

Eval Lab 用成对运行比较“宿主原生回答”和“应用指定 Skill 后的回答”，回答一个比路由评测更窄的问题：某个 Skill 是否真的改善了任务结果。

它目前是仓库级实验，不属于 `tessera-core`，也不会随 Tessera 插件安装。确定性适配器只验证评测器本身；质量结论必须来自真实宿主运行。

## 方法

- 同一案例先运行 baseline，再运行 skill 条件；`--repeat` 对每个条件重复运行并取总分中位数。
- `activation: injected` 会在两个条件都禁用目标插件，只在 skill 条件注入目标 `SKILL.md` 的原文，并记录 SHA-256。这能隔离 Skill 内容的效用，但不证明宿主会正确路由到它。
- `activation: native` 通过每次调用的插件开关形成对照；只有宿主事件证明 baseline 未加载而 skill 条件已加载目标 Skill 时才标记为可归因。
- 评分标准和 `minimum_delta` 在运行前写入案例。`direction` 表示原始方向，`verdict` 只有在达到预设阈值后才判为 improvement 或 regression。
- 报告同时保存逐标准通过率、`gained_criteria` 和 `lost_criteria`，避免净分掩盖局部退化。
- 真实 Codex 运行汇总每个条件的 input、cached input、output 和 reasoning tokens，并记录注入 Skill 的字符数与 UTF-8 字节数。总 token 差会受回答路径影响，不能单独视为静态提示开销。
- 超时、配额和宿主失败记为 `execution_error`，不会被误判为质量退化。

## 运行

在一个不会写入项目的隔离工作区运行真实 Codex：

```powershell
python experiments/eval-lab/run_eval_lab.py `
  --cases experiments/eval-lab/cases.json `
  --repeat 3 `
  --workspace D:\path\to\isolated-workspace `
  --output eval-results/eval-lab.json
```

只复跑一个案例：

```powershell
python experiments/eval-lab/run_eval_lab.py `
  --cases experiments/eval-lab/cases.json `
  --case knowledge-base-incident-learning `
  --repeat 3 `
  --output eval-results/knowledge-base-incident.json
```

`response.schema.json` 限制宿主结构化输出；`cases.json` 是当前案例和预注册阈值的事实来源。受控适配器示例由 `tests/test_eval_lab.py` 覆盖。

## 证据边界

初次真实运行及解释见 [evidence/2026-07-14-initial.md](evidence/2026-07-14-initial.md)，两轮 R3 准入复跑见 [evidence/2026-07-14-admission-r3.md](evidence/2026-07-14-admission-r3.md)，三个专业 Skill 的组合评审见 [evidence/2026-07-14-professional-skill-value-review.md](evidence/2026-07-14-professional-skill-value-review.md)。评测器已经复现真实增益与退化，但仍不并入 core；原因还包括自包含发布边界和运行成本。
