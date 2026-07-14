---
name: tessera-eval
description: 当用户要运行、复跑或比较 Tessera 路由评测，检查误调用、漏调用、多意图错误或路由准确率时使用。调用仓库内固定案例和评测脚本，保存逐案例 JSON 报告；不把 CI 的假宿主结果冒充模型实测。
---

# Tessera Eval

运行可复现的路由行为评测。评测只判断路由，不执行案例中的用户任务，不修改目标项目，不安装依赖。

## 可选本地使用记录

若能定位仓库 `scripts/usage_events.py`，进入时尝试运行 `start --host <host> --skill tessera-eval --project <cwd>`；只有返回事件 id 时，结束前运行 `finish --event-id <id> --host <host> --skill tessera-eval --outcome completed|failed --project <cwd>`。记录失败不得影响评测结果，也不得混入 `eval-results`。

## 前置判断

1. 定位 Tessera 仓库根；必须能看到 `scripts/run_routing_eval.py`、`tests/routing-cases.yaml` 和 `tests/personal-routing-cases.yaml`。不可见时报告 `UNKNOWN` 并给出需要用户提供的路径，不猜测。
2. 识别宿主。Codex 使用脚本内置、已验证的只读临时会话适配器。Claude 仅在提供符合下述契约的适配器时运行；没有适配器就报告 `unavailable`，不得声称已实测。
3. 默认运行全部案例；用户指定案例、宿主、模型或输出路径时按其要求收窄。

核心机制回归使用默认的 `tests/routing-cases.yaml`；个人工作流回归使用：

```powershell
python scripts/run_routing_eval.py --host codex --cases tests/personal-routing-cases.yaml
```

个人案例固定保持 20–30 条；只有真实失败或新的高频场景才替换或增加。Claude CLI/适配器不可用时只允许 dry-run，不得声称已完成 Claude 实测。

## 执行

Codex 全量复跑：

```powershell
python scripts/run_routing_eval.py --host codex
```

单案例 smoke：

```powershell
python scripts/run_routing_eval.py --host codex --case direct-small-edit
```

只校验案例选择与运行计划：

```powershell
python scripts/run_routing_eval.py --host codex --dry-run
```

Claude 适配器必须是一个可执行程序：从 UTF-8 stdin 读取评测提示，向 stdout 只输出符合 `tests/routing-output.schema.json` 的 JSON。调用时使用 `--adapter-executable`，额外参数逐个用 `--adapter-arg` 传入。适配器不得通过 shell 字符串拼接执行。

## 报告解释

报告默认写入被 Git 忽略的 `eval-results/`，包含宿主、时间、案例版本路径、逐案例期望/实际路由、耗时、失败类别与汇总：

- `pass_rate`：通过数 / 全部案例；执行错误也计入分母。
- `route_accuracy`：通过数 / 成功取得宿主输出的案例。
- `over_route`：简单直达任务被过度路由。
- `missed_route`：应调用核心或专业能力却直接执行。
- `multi_intent_error`：多意图请求未进入正确协调路径。
- `wrong_route`：其他路由错误。
- `execution_error`：宿主不可用、超时、退出异常或输出无法解析。

先报告“通过数、整套通过率、路由正确率、执行错误”，再列失败案例及类别。比较两次结果时按相同案例文件、宿主、模型和适配器口径；条件不一致必须注明，不做伪精确结论。

CI 只验证案例结构、评分逻辑和确定性假宿主闭环，不代表 Codex/Claude 的模型行为。模型行为结论必须来自对应宿主的新会话实跑报告。
