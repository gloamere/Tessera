---
name: piece-router
description: 仅当请求模糊、包含多个独立交付物、涉及高风险或不可逆方向决策，或请求新增/引入/拆分拼图时使用。Tessera 在这些异常场景选择工作方式并执行能力准入；明确的单一任务以及 taste、planner、knowledge-base 等专业请求由宿主原生直接处理，不先调用本 skill。
---

# 拼图派发表

宿主原生 Skill 选择是默认路径。本 skill 不是所有请求的前置网关，只处理 description 指定的异常场景。

## 可选本地使用记录

若能定位仓库 `scripts/usage_events.py`，进入本 skill 时尝试运行 `start --host <host> --skill piece-router --project <cwd>`；只有返回事件 id 时，结束前才运行 `finish --event-id <id> --host <host> --skill piece-router --outcome completed|failed --project <cwd>`。记录默认关闭、只写 `~/.tessera`，任何缺失或失败都静默跳过且不得影响路由。

## 动态能力解析

本 skill 实际命中后，优先使用当前会话明确暴露的 skills 作为 active 证据。能定位 Tessera 仓库时，按 `tessera-capabilities` 的流程运行 `scripts/resolve_capabilities.py --host <host> --probe`，把会话可见 skill 逐项作为 `--active-skill` 传入。普通任务不得为了探测目录先调用本 skill。

只直接调用 `runtime_state: active` 的能力；`installed` 建议新开会话，`available` 可转 `tessera-setup`，`unknown` 如实说明证据不足，`reference-only`、`unverified`、`unsupported` 不得路由。仓库或脚本不可见时退化为当前会话 skill 列表，不因无法动态解析而阻塞直接任务。

下表是内置意图示例，不是安装或激活状态的事实来源：

| 意图 | 拼图 | 调用方式 |
|---|---|---|
| 搜索、调研、查资料、读 URL、看某平台讨论 | agent-reach 或宿主原生能力 | 先按 registry 检查当前宿主可用性；不可用时如实说明并使用宿主已有能力，不假定外部 skill 可调用 |
| UI/视觉设计评审、审美判断、反套路自检 | taste | 本仓库拼图,随 tessera 市集提供;未装则提示 /tessera-setup |
| 写代码、改功能、修 bug | superpowers 流程链或宿主原生能力 | 当前宿主可用时走 brainstorming → writing-plans → 实现 → verification；不可用则如实说明并正常完成 |
| 记笔记、整理知识、建/查知识库 | knowledge-base | 本仓库拼图,随 tessera 市集提供;未装则提示 /tessera-setup |
| 游戏/内容/产品方案策划(非写代码) | planner | 本仓库拼图,随 tessera 市集提供;未装则提示 /tessera-setup |
| 新增/引入/拆分/设计拼图 | 本 router | 读取 `references/piece-admission.md`，先给七维评分与 S–F 建议，再决定是否进入实现 |
| 安装 registry 中未集成/候选外部能力 | 本 router | 说明其不可安装状态与缺失证据，不进入 tessera-setup 选择项 |
| 拼图状态/安装/升级 | tessera-core 自身 | tessera-status、tessera-setup skill |
| 全面体检/诊断 Tessera 漂移或状态矛盾 | tessera-core 自身 | tessera-doctor skill；只读检查，不自动修复 |
| 复跑固定案例、评估路由准确率与错误类型 | tessera-core 自身 | tessera-eval skill；只判断路由，不执行案例任务 |
| 动态列出或解释当前可用能力 | tessera-core 自身 | 日常走 tessera-status；明确要求完整目录时兼容调用 tessera-capabilities |

**如实交代状态**:未安装、未验证或规划中的目标只能说明其状态,不能伪装成已安装、可直接调用的 skill/CLI。

## 先选执行层级

1. **单一、明确、低风险**:由宿主直接完成，不调用本 skill。
2. **明确命中已安装的专业拼图**:由宿主直接调用该拼图，不先经过本 skill。
3. **模糊、多个独立交付物、高风险或不可逆方向决策**:本 skill 识别意图并选择下一步。
4. **可拆成独立子任务的复杂工作**:宿主支持时按下节「条件委派」委派,主 agent 汇总。
5. **任务规划与跟踪**使用宿主 agent 的原生能力，不为此引入外部任务后端。

## 条件委派子代理

复杂 ≠ 自动多代理。仅当**当前宿主确实提供委派/子代理能力**且同时满足:

1. 能拆成至少两个输入、输出、写入面相互独立的子任务;
2. 并行节省的时间或专业收益,大于任务说明、汇总与上下文切换成本;
3. 不涉及负责人拍板、外部安装、不可逆操作或同一文件并发修改。

满足时:主 agent 先写清每个子任务的目标、范围、输入、验收与禁止修改项;最多并行 3 个;主 agent 负责汇总、冲突处理、验证与最终交付。任一条件不满足、宿主无委派能力或任务高度串行时,退回直接执行或调用已安装的专业 skill。

## 硬规则(必须遵守)

1. **方向性拍板**:目标项目已有 ADR、`docs/decisions/` 或其它决策规范时严格遵循。项目没有决策机制时，只对高影响、难逆转的方向请求用户确认；使用宿主原生结构化提问能力，不可用时直接提出一个简短文本问题。不得仅因缺少决策目录而阻塞任务或自动创建文件。
2. **不可逆操作**(强推、递归删除、丢弃改动、全局安装)执行前先向用户说明并确认;不可逆命令仍受 Codex/Claude 原生权限约束。

## 多意图命中

命中多块拼图且选择会实质改变结果时，优先用宿主原生结构化提问让用户选；不可用时提出一个简短文本问题。若请求包含至少两个具有独立交付物的意图，必须读取 `references/multi-intent-recipes.md`，在执行前输出依赖有序 recipe，并按其交接、中断与降级规则推进。普通单任务步骤不生成 recipe。零命中时正常工作，不硬套拼图。路由决策以净收益为准:质量提升必须大于额外 token、调用延迟与上下文切换成本。

## 路由解释

本 router 被实际调用并作出选择时，在执行前输出一行：`路由说明：<任务形态> → <执行层级/拼图>；原因：<净收益依据>；不可用时：<降级方式>`。明显简单任务直接执行且没有调用本 router 时不额外输出；除用户显式启用的本地使用记录外，不写日志、不做联网遥测。
