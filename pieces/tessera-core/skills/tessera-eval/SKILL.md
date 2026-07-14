---
name: tessera-eval
description: 当用户要运行、复跑或比较 Tessera 路由政策与宿主原生 Skill 调用，检查误调、漏调、多意图错误、调用证据或稳定性，或要求根据重复失败优化 Skill description/路由边界时使用。保存逐案例 JSON；区分政策分类、真实宿主证据与模型自报，不自动改写提示词。
---

# Tessera Eval

评测路由政策或可观测的原生 Skill 调用。只运行无副作用探针，不执行案例中的用户任务，不修改目标项目，不安装依赖。

## 自包含运行

本 Skill 的运行器、schema 和案例都位于当前 Skill 目录内，不得搜索或依赖 Tessera 仓库 checkout。先从宿主提供的当前 `SKILL.md` 绝对路径得到 `<eval-root>`，即本文件所在目录。

- Windows：调用 `powershell -NoProfile -File "<eval-root>\scripts\run.ps1" ...`。
- macOS / Linux：调用 `sh "<eval-root>/scripts/run.sh" ...`。

启动器只需要本机 Python 3 标准库，不运行 pip，也不读取插件目录之外的 Tessera 文件。报告写入用户当前项目的 `eval-results/`；插件缓存保持只读。

## 选择模式

- `policy`：默认兼容模式。忽略用户插件配置，向隔离分类器提供路由定义，验证 Tessera 的分类政策；结果不能描述成宿主原生调用准确率。
- `native`：不提供路由清单或预期答案，让宿主按当前真实 Skills 选择；Codex 从 `exec --json` 事件读取 Skill 加载证据，Claude 需要符合契约的外部适配器。

默认案例使用 `<eval-root>/references/routing-cases.json`；个人场景使用 `<eval-root>/references/personal-routing-cases.json`。每个 native 案例必须显式声明 `expected_skills`；宿主原生处理的任务使用空数组，只有明确的 Tessera 专业请求才列出对应 Skill。

## 执行

```powershell
# 政策分类；兼容旧调用
powershell -NoProfile -File "<eval-root>\scripts\run.ps1" --host codex --mode policy

# 原生调用验证
powershell -NoProfile -File "<eval-root>\scripts\run.ps1" --host codex --mode native

# 个人场景
powershell -NoProfile -File "<eval-root>\scripts\run.ps1" --host codex --mode native --cases "<eval-root>\references\personal-routing-cases.json"

# 确认随机失败是否稳定复现
powershell -NoProfile -File "<eval-root>\scripts\run.ps1" --host codex --mode native --case <id> --repeat 3

# 只输出边界优化建议，不修改 Skill
powershell -NoProfile -File "<eval-root>\scripts\run.ps1" --host codex --mode native --case <id> --repeat 3 --suggest-tuning
```

`--repeat` 只接受 1–10。`--suggest-tuning` 只允许 native 且 `repeat >= 3`。native 默认使用45秒证据观察窗口，policy 默认120秒；可用 `--timeout` 覆盖。观察窗口结束时只有完整预期 Skill 集合已经出现才保留为 verified，否则报告执行超时。Claude 没有适配器时报告 `unavailable`，只允许 dry-run，不得声称已实测。

Native 适配器从 UTF-8 stdin 读取探针，stdout 只输出 JSON：`decision`、`selected_skills`、`observed_skills`、`observation_source`、`reason`。`observation_source` 只能是 `host-events`、`transcript` 或 `model-report`；最后一种永远不能成为 verified 证据。

## 证据与报告

- `verified`：宿主事件或可信 transcript 观察到目标 Skill；完整事件流中的直接决策也可验证未调用首方 Tessera Skill。
- `declared-only`：模型声称会调用，但没有宿主证据；不计入真实调用通过。
- `unobservable`：宿主或适配器无法提供证据。
- `conflict`：模型声明与宿主证据不一致。

报告 schema v2 保存 `mode`、`repeat`、声明限制、扁平 attempts、按案例稳定率、验证等级和 `verified_pass_rate`。`policy` 报告必须包含 `routing-policy-classification; not native invocation evidence` 声明。CI 假宿主只证明结构、聚合与评分闭环。

## 失败驱动的提示边界优化

只有同一 native 案例至少三次中出现两次相同、可观测且非执行类失败时，才生成候选：

- 漏调：检查目标 Skill `description` 是否缺少真实触发语言。
- 误调：收窄被误调 Skill 的 description，并增加明确排除边界。
- 错误路由：检查目标与竞争 Skill 的描述重叠。
- 多意图错误：检查各目标专业 Skill 的 description 是否能在同一请求中独立触发。

每轮只人工修改一个边界。先将失败案例和相邻反例各复跑三次，再运行完整 policy 与 native 回归；目标改善且没有新增退化才接受。执行错误、declared-only 和 unobservable 不生成提示建议。不得自动写回 SKILL.md，不优化用户日常提示词，不建设 Prompt Lab。
