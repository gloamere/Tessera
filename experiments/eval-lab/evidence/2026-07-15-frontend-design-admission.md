---
schema: tessera/eval-lab-evidence@1
date: 2026-07-15
host: codex-cli-0.144.1
model: host-default
repeat: 3
activation: native-routing-and-controlled-injection
base_commit: 8bafd59
cases_sha256: ec7f7dbd4aaecfd34d38056e56e604acc45c4aa192731b9c09665afff0881dda
skill_sha256: 3db539e025269e5feded74431c3a6b02445b922c91f332dc71da632f495ea6bf
decision: admit-frontend-design-core-as-optional-plugin
---

# frontend-design 核心准入证据

## 结论

纳入 UI UX Pro Max 的可复现核心，作为独立可选 `frontend-design` 插件；不复制完整上游发布壳。它与 `taste` 按“设计系统与实现约束 → 成品审美复核”顺序组合，不强制共同加载。

| 验证面 | 结果 |
| --- | --- |
| 上游 pin | `nextlevelbuilder/ui-ux-pro-max-skill@f8ac5e1266dba8354ea96e19994d9f4345e7ec31` |
| 本地核心 | 35 个 CSV，数据校验通过，上游 16 个核心单测通过 |
| 自包含 | 缓存副本从无关工作目录生成结构化设计系统；无第三方 Python 包 |
| 双宿主发布 | Claude/Codex manifest、marketplace、piece 与短 Skill 校验通过 |
| 原生路由 | 3 场景 × 3 轮，9/9 verified，0 execution error |
| 质量 R3 | 5 场景 × 3 轮配对，2 improvement、3 no_change、0 regression |

## 原生路由与组合边界

`codex-frontend-routing-r3.json` 保留 9 次宿主事件：

- 新 B2B dashboard 设计系统三轮均只命中 `frontend-design`；
- React 落地页“先设计、后去模板味”三轮均命中 `frontend-design` 与 `taste`；
- 用户访谈与可用性测试三轮均不命中 Tessera 的两个前端 Skill，由宿主其它能力处理。

总 pass rate 与 verified pass rate 均为 `1.0`，没有 over-route、missed-route、multi-intent error 或 wrong-route。

## 内容价值 R3

质量评测使用固定 SHA-256 的 `SKILL.md` 受控注入；基线与技能条件都禁用目标插件，避免自动激活不稳定污染归因。每个条件运行三次，取中位数，显著阈值预设为 `±0.200`。

| 场景 | baseline | skill | delta | verdict | 主要局部变化 |
| --- | ---: | ---: | ---: | --- | --- |
| B2B dashboard | 0.500 | 0.875 | +0.375 | improvement | 增：语义 token、状态、无障碍、反模式；无损失 |
| 技术文档首页 | 0.500 | 0.750 | +0.250 | improvement | 增：目标气质、语义 token、对比度/focus；“拒绝错配”措辞通过率小幅波动 |
| 移动结账 | 0.500 | 0.500 | 0.000 | no_change | 增：失败恢复、触控目标；响应式措辞小幅波动 |
| 分析图表 | 0.500 | 0.625 | +0.125 | no_change | 增：图表无障碍、React 指导；token 显式措辞小幅波动 |
| 设置重构 | 0.875 | 0.750 | -0.125 | no_change | 增：语义 token；状态中文词与交付优先级评分波动 |

没有案例达到 regression 阈值。设置页原始负向变化需要保留：技能回答实际列出 `Loading`、校验失败、网络失败和未保存，评分规则要求中文“加载”，因此 `required-states` 的下降主要是词法假阴性；但交付优先级也从 3/3 降到 2/3，属于真实的非显著波动，后续内容改版应复跑该案例。

15 组 baseline 与 15 组 skill 调用累计模型耗时约 25.01 分钟。baseline/skill input tokens 为 959,408 / 854,710，output tokens 为 22,956 / 21,350。质量 R3 不进入普通 CI。

## 失败尝试与方法修正

首次五案例 R3 在基线首轮均超过 120 秒，报告为 5 个 `execution_error`，没有技能条件结果，不能推断 regression。失败原始文件保留为 `codex-frontend-design-value-r3-timeout.json`。

随后只增加执行约束（直接回答、不巡检或修改工作区、限制篇幅）并保持评分标准与 `±0.200` 阈值不变。原生自动加载烟测仍无法稳定观察 Skill 读取，因此质量面改用仓库既有的哈希内容注入；真实安装和组合选择继续由独立 native routing R3 证明。这个分层避免把“能被宿主选中”和“内容能提升输出”混成一个指标。

## 原始证据

- `codex-frontend-routing-r3.json`
- `codex-frontend-design-value-r3-timeout.json`
- `codex-frontend-design-value-r3.json`

三个 JSON 分别保留逐次宿主事件、失败原因、完整回答、逐标准结果、token usage 与耗时。
