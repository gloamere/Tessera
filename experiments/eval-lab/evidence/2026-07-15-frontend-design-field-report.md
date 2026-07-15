---
schema: tessera/eval-lab-evidence@1
date: 2026-07-15
host: codex-desktop
source: user-returned-independent-task-transcripts
cases: 6
decision: tighten-execution-budget-and-context-boundary
---

# frontend-design 首轮独立任务回报

用户在六个独立 Codex 任务中运行 A–F 提示，并原样返回实际加载 Skill、可见工具调用、最终回答与主观问题。本记录只保存可复核摘要，不把用户附件复制进仓库。

| 案例 | 路由 | 回答长度 | 结论 |
| --- | --- | ---: | --- |
| A B2B dashboard | `ui-skills-root` + `frontend-design`，另下载外部 UI Skill | 8555 字符 | 核心命中正确；重复读取缓存/仓库副本、外部 Skill 404、过长 |
| B 已有 SaaS 首页审美评审 | `taste` | 1021 字符 | 边界与篇幅正确 |
| C 最小 UI 清理 | `ui-skills-root` + `baseline-ui` | 777 字符 | 边界与篇幅正确 |
| D 设计后审美复核 | `frontend-design` + `taste` | 3260 字符 | 组合命中正确；错误把通用 React 页面绑定到 Tessera 仓库，过长 |
| E 用户访谈 | `planner` | 4607 字符 | 未误触发前端 Skill；篇幅属于外部 planner 问题 |
| F Astro 文档设计 | `ui-skills-root` + `frontend-design`，子任务额外加载 `taste` | 4288 字符 | 核心命中正确；七类搜索、两个子任务、重复加载与额外审美 Skill |

## 根因与修正

数据检索本身没有表现出质量或性能问题。失控来自 Skill 没有限定执行预算：默认从仓库识别技术栈导致通用任务被当前工作区污染；`<skill-root>` 不够明确导致缓存与仓库副本各读一次；细分检索没有上限；规格题可以继续派生 UI Skill、参考资料、官方搜索和子任务；交付没有默认篇幅。

`frontend-design` 0.1.1 因此增加以下硬边界：

- 规格简报充分时不巡检工作区；
- 只使用最先读取的 Skill 副本；
- 本地搜索最多两次，参考最多一份；
- 不下载重叠的通用 UI Skill，不为规格/评审启动子代理；
- 默认五区块、约 1200–2200 中文字符；
- `taste` 只复核已形成的具体方案，不重复生成设计系统。

首次自动复测显示执行预算有效：A 只读取缓存 Skill、运行一次设计系统搜索，没有外部 UI Skill、404 或子任务；F 运行一次设计系统与一次 Astro 搜索，没有额外 `taste`、外部 UI Skill 或子任务。F 从 4288 降到 2842 字符。A 仍有 6304 字符，因此继续把交付从建议篇幅收紧为固定五段、每段最多五条、核心 token 最多 12 个，并禁止目录树、框架教程和穷举验收清单。

固定结构后的 A 再复测为 2559 字符，只读取一次缓存 Skill、运行一次本地搜索，0 个外部 UI Skill、0 个子任务；五个输出区块与规则一致。相对用户首轮 8555 字符减少约 70%，同时保留 token、信息架构、状态、响应式、无障碍和 Next.js 六类要求。本轮不再为追求机械字符阈值继续删减，避免损伤完整性。

B、C 已证明专业审美与快速清理可以保持独立，因此本轮不扩大 `frontend-design` 的触发范围，也不删除 35 个按需数据表。
