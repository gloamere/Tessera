---
schema: tessera/decision@1
id: frontend-design-core-admission
status: superseded
created: 2026-07-15
approved: 2026-07-15
review: 上游数据格式、Python 兼容性、宿主 Skill 激活或真实质量证据变化时重审
superseded_by: business-workflow-suite-admission
supersedes:
  - current-runtime-architecture
---

# 纳入 frontend-design 核心并与 taste 顺序组合

## 决策

Tessera 发布四个独立插件：核心 `tessera-eval`，以及可选的 `frontend-design`、`taste`、`knowledge-base`。`frontend-design` 纳入 UI UX Pro Max 的可复现核心，不整体复制上游 CLI、编辑器模板或多宿主安装壳。

纳入范围固定为 35 个 CSV 数据表、Python 标准库搜索与设计系统脚本、数据校验、上游 16 个核心单测和两份按需参考。来源固定到 `nextlevelbuilder/ui-ux-pro-max-skill` commit `f8ac5e1266dba8354ea96e19994d9f4345e7ec31`，保留 MIT 许可与独立 provenance。升级必须显式更新 pin、重新执行数据/核心测试和真实质量对照。

## 组合边界

- `frontend-design` 用于从零设计、新页面/组件、设计系统与系统性重构；产出 token、信息架构、交互状态、响应式、无障碍和当前技术栈约束。
- `taste` 用于已有方案或成品的审美复核、视觉层级、排版、配色、文案语气和去模板化；不重复生成完整设计系统。
- 同时出现两个明确意图时按 `frontend-design → 实现/方案成形 → taste` 顺序执行。两者不互相依赖，也不因安装齐全而每次一起加载。
- 用户研究、访谈、可用性测试和转化实验由宿主直接处理；数据库匹配只能作为候选设计证据，不能冒充用户证据。

## 接受“核心”而非“全部上游”的原因

完整上游还包含面向不同代理和编辑器的安装器、模板及发布包装，复制后会与 Tessera 双宿主 marketplace、安装器和 Skill 路由形成第二套控制面。核心数据与脚本约 1.75 MB、无第三方 Python 依赖，足以提供可搜索知识、设计系统生成与栈规则，同时保持离线、自包含和可审计。

直接全量纳入会带来五类问题：Skill 边界重叠导致重复加载；数据库候选被当成审美结论；长上下文和搜索增加成本；上游更新扩大供应链与回归面；平台包装在 Windows/macOS/Linux 间漂移。本决策用独立插件、短 Skill、固定上游 pin、缓存搜索、双包装器和分层证据控制这些风险。

## 平台与验证

Windows 使用 `run.ps1`，macOS/Linux 使用 `run.sh`，两者只调用 Python 3 标准库实现。普通 CI 在 Ubuntu、macOS、Windows 验证双 marketplace、manifest、脚本语法、数据完整性、缓存搜索、上游核心测试和 fixture 路由。真实宿主路由与 baseline/skill 质量对照单独归档，因为 fixture 和模型自报不能替代宿主事件或可归因注入。

准入时 native routing 三场景各重复三轮，9/9 verified；五类前端任务的受控内容 R3 得到 2 个 improvement、3 个 no_change、0 regression。设置重构有 `-0.125` 的非显著原始波动，包含一项评分词法假阴性与交付优先级波动，必须保留并在内容变更时复跑。完整证据见 `experiments/eval-lab/evidence/2026-07-15-frontend-design-admission.md`。

安装后的六个独立桌面任务继续暴露执行成本：核心路由正确，但复杂规格题重复读取缓存与仓库副本、扇出外部 UI Skill/子任务/多领域检索，回答达到 3260–8555 字符。0.1.1 保留数据核心，改为单副本、两次检索、单份参考、无规格子代理和默认紧凑交付；详见 `experiments/eval-lab/evidence/2026-07-15-frontend-design-field-report.md`。

## 当前 Module 与 seam

- **宿主原生选择**：普通任务、计划、确认、委派、生命周期和外部能力。
- **`tessera-eval`**：路由政策、原生调用与稳定性报告。
- **`frontend-design`**：本地 UI/UX 核心与前端设计实现约束。
- **`taste`**：成品审美判断与去模板化复核。
- **`knowledge-base`**：Markdown 原子笔记与双链知识沉淀。
- **发布 seam**：Claude/Codex marketplace、安装器、piece 元数据与校验器声明相同四插件集合。
- **质量 seam**：`experiments/eval-lab` 保存预注册案例、失败尝试与最终 R3，不进入用户运行时。

`piece-router`、setup/status/doctor/capability registry、`planner`、私有任务后端、usage events、hooks、daemon 和数据库仍不属于当前产品。
