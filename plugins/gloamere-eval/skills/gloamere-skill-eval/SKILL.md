---
name: gloamere-skill-eval
description: "当用户要检查、校验或运行 Codex Skill 路由评测，生成 path+SHA+plugin 绑定的目标锁，区分可验证证据、冲突和不可观测结果，或读取 Gloamere Eval 报告时使用。仅评测 Codex 原生 Skill 激活，不执行被测请求，不自动改写 Skill。"
---

# Gloamere Skill Eval

为 Codex Skill 路由提供可复现、证据绑定的评测。只执行无副作用探针：

- 不完成评测案例里的用户任务。
- 不修改被测仓库，不安装依赖，不调用具有外部副作用的工具。
- 不把模型自报当作 Skill 加载证据。
- 不自动修改被测 Skill 的 `SKILL.md`。

本 Skill 的 runner、schema 和说明都在当前 Skill 目录内。不要依赖 Gloamere
源码仓库或旧名称下的文件。

## 运行要求

需要 Python 3.10 或更高版本，只使用标准库。

- Windows：`powershell -NoProfile -File "<eval-root>\scripts\run.ps1" ...`
- macOS / Linux：`sh "<eval-root>/scripts/run.sh" ...`

`<eval-root>` 是当前 `SKILL.md` 所在目录。所有命令默认把 JSON 写到 stdout；
只有显式传入 `--output <path>` 才写文件，并且仍在 stdout 返回同一结果。

## 评测契约

评测分为三个动作：

1. `inspect`：扫描一个或多个 Codex 插件，并读取 `codex plugin list --json` 生成
   target lock v2。每个目标同时绑定 `target_id`、插件 ID/版本、installed/enabled，
   插件 manifest、`SKILL.md` 与 `agents/openai.yaml` 的完整路径、相对路径和各自
   SHA-256。插件目录不可观测时状态写 `null`，不假定已经安装或启用。
2. `lint`：校验 eval suite、target lock 或 report。运行前还会重新读取文件，
   防止 Skill 内容或插件身份在锁定后漂移。
3. `native`：让 Codex 按正常触发规则处理案例，并从 `codex exec --json`
   事件流验证实际读取的 `SKILL.md`。只有已完成、状态成功、退出码为零的
   `command_execution`，且命令明确读取锁定路径、输出包含锁定文件内容时，才算
   加载证据；失败、未完成或只提到路径的命令一律 fail-closed。事件适配器固定为
   `codex-exec-jsonl` schema v1；事件流缺失、截断、格式错误或出现未知事件时采用
   fail-closed，不给出已验证结论。

Schema 位于 `<eval-root>/references/schemas/`：

- `eval-suite.schema.json`
- `target-lock.schema.json`
- `report.schema.json`（公共文件名固定，当前内容为 schema v4）
- `native-invocation-output.schema.json`

suite 以顶层和逐案例 `plugin_id` 显式声明插件身份；案例使用稳定 Skill ID 填写
`expected_skills[]` 与 `forbidden_skills[]`，并包含 `language`、`tags`。runner
不内置任何业务 Skill 名称。推荐工作流：

```powershell
# 1. 锁定实际安装或工作区中的插件身份
powershell -NoProfile -File "<eval-root>\scripts\run.ps1" inspect `
  --plugin-root "C:\path\to\plugin-a" `
  --plugin-root "C:\path\to\plugin-b" `
  --output ".\eval-target-lock.json"

# 2. 校验 suite 与 lock 的绑定关系
powershell -NoProfile -File "<eval-root>\scripts\run.ps1" lint `
  --suite ".\eval-suite.json" `
  --target-lock ".\eval-target-lock.json"

# 3. 先预览低 Token release 选择；不会调用模型
powershell -NoProfile -File "<eval-root>\scripts\run.ps1" native `
  --suite ".\eval-suite.json" `
  --target-lock ".\eval-target-lock.json" `
  --policy ".\risk-tiered-v2.json" `
  --mode release `
  --changed-skill "example-skill" `
  --max-calls 40 `
  --dry-run

# 4. 使用同一选择运行并逐次写 journal
powershell -NoProfile -File "<eval-root>\scripts\run.ps1" native `
  --suite ".\eval-suite.json" `
  --target-lock ".\eval-target-lock.json" `
  --policy ".\risk-tiered-v2.json" `
  --mode release `
  --changed-skill "example-skill" `
  --max-calls 40 `
  --model "<model>" `
  --journal ".\eval-report.journal.jsonl" `
  --output ".\eval-report.json"
```

`--mode pr|release|exhaustive` 选择策略；`pr` 与发布候选的 `release`
必须提供外部 `--policy`，并可重复传 `--changed-skill`。每月漂移监测可在
`release` 下省略变更 Skill，配合 `--rotation-key YYYY-MM --max-calls 16`；
这类报告不具备发布资格。`--max-calls` 是硬上限，
`--rotation-key` 固定轮换样例，`--dry-run` 只输出选择和预算。

`exhaustive` 使用两阶段调度：必须先完成 policy 声明的全部
`initial_calls`，才会复验异常案例。当前官方套件先各运行 102 个唯一案例一次，
再用剩余预算复验异常；硬上限为 120。初始失败不会挤占尚未覆盖案例，预算不足
以完成复验时结果保持 `pending`。`--dry-run` 会明确返回
`initial_planned_calls`、`hard_max_calls`、`retry_call_capacity` 和
`execution_strategy`，且不会调用模型。

长任务使用 `--journal` 逐次原子追加、`--resume` 跳过已完成 attempt、
`--shard INDEX/TOTAL` 确定性分片。`--finalize` 只从 journal 生成报告，不调用
模型。可继续用 `--case <id>` 显式缩小范围、`--timeout <seconds>` 调整观察窗口、
`--model <model>` 绑定实际模型。默认使用隔离临时工作区；只有确需真实项目上下文
时才传 `--workspace <path>`。

## 身份与冲突

内部 `target_id` 的标准形式为 `<plugin_id>:<skill_name>`。名称相同但路径或插件不同的
Skill 会记录为冲突；只要该名称在 suite 范围内，预检就失败。运行期即使模型声明
了正确名称，只要主机证据指向锁外同名路径，也必须报告 `identity_conflict`，不能
按名称猜测。新旧安装并存、安装目录/版本变化、installed/enabled 与 lock 不一致也会
在调用 Codex 前生成结构化冲突报告并停止评分。

target lock 生成后，如果插件 manifest、`SKILL.md`、`agents/openai.yaml`、
frontmatter 名称、插件 ID/版本、相对路径或任一 SHA-256 变化，应重新运行
`inspect`，不要手工修补 lock。批次内发现漂移时，整批降级为
`identity_conflict`，不得继承预检时的 verified 结论。

## 证据与判定

每次 attempt 同时包含 `evidence_status` 与 `verdict`：

- `verified`：完整、已识别的 Codex 事件流与模型声明一致，并且有成功读取锁定
  `SKILL.md` 全文的宿主证据。
- `unobservable`：事件流格式错误、截断、含未知事件，或目标路径只被提及但未形成
  可证明的成功读取。
- `unavailable`：Codex、插件目录或已启用目标当前不可用。
- `identity_conflict`：模型声明、同名 Skill、安装身份或 target lock 互相冲突。
- `execution_error`：Codex 或测试适配器执行失败。
- `verdict` 只允许 `pass`、`fail` 或 `null`；只有 `verified` 证据参与评分，其余
  状态一律为 `null`，避免把证据问题误判成路由失败。

报告使用 schema v4，分别统计 `evidence_coverage` 和
`conditional_accuracy`，避免把“没有证据”误写成准确。新增 `evaluation`
记录 policy、mode、选择理由、选中案例、预算、实际/恢复调用数、分片与完成状态；
`provenance` 绑定 commit、suite/policy/target lock/Skill SHA、Codex CLI、model
和 ISO 时间。`lint --report` 会从 attempts 全量重算指标，不信任报告自报汇总。

报告的 `execution_provenance` 只允许 `codex_cli` 或 `fixture_adapter`。
`release_evidence_eligible` 只有前者为 `true`；fixture 仅用于验证 runner，不得作为
发布证据，即使其合成结果为 pass。

报告默认只保存 prompt SHA-256，不保存原始 prompt；只有明确需要且已确认隐私边界
时才使用 `--include-prompts`。报告不写 target lock 中的绝对路径；当
`absolute_paths_included=false` 时，lint 会递归拒绝报告任意字段中的绝对路径。

`lint --report` 可以只读兼容结构完整的 schema v2/v3 历史报告并标记兼容来源，
但只有 schema v4 能成为发布证据。兼容读取不会发布旧 Skill 名称、旧命令或旧别名。
