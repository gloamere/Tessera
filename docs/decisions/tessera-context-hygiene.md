---
schema: tessera/decision@1
id: tessera-context-hygiene
status: approved
created: 2026-07-12
approved: 2026-07-12
review: Claude Code 修复 #14882 / #43875 / #31935 后重审
---

# 上下文卫生:拼图如何进上下文,以及不要踩的坑

## 背景

拼图 = Claude Code / Codex 的 Skill。想确认"渐进式披露"到什么程度、能不能进一步压常驻上下文。2026-07-12 调研结论如下。

## 机制

- **三级渐进披露(文档设计)**:① `name`+`description` 会话启动常驻(~80–100 token/块);② SKILL.md 正文仅调用时加载;③ 引用资源按需。
- **常驻税 = 所有已装拼图的 description 之和**,线性随已装数增长。
- **CLAUDE.md / AGENTS.md 与拼图是不同机制**:CLAUDE.md 全文常驻;AGENTS.md 仅 Codex 常驻读(Claude Code 不自动读);拼图走渐进披露。**拼图本身不写 CLAUDE.md/AGENTS.md**;唯一注入是 `tessera init` 往目标项目 AGENTS.md 补一段带标记、幂等、~150 token 的 guidance(Codex 侧常驻,Claude Code 零成本)。无 hooks。

## 坑(勿踩)

- **`disable-model-invocation: true` 不能用来做"router 派发到隐藏拼图"**:
  - Claude Code [#43875](https://github.com/anthropics/claude-code/issues/43875) / [#43809](https://github.com/anthropics/claude-code/issues/43809):该开关让 skill **对模型完全不可达**,连 router 显式派发也调不动(`cannot be used with Skill tool due to disable-model-invocation`)——**断路由**。
  - [#31935](https://github.com/anthropics/claude-code/issues/31935):它**连 description 都不从上下文去掉**——**不省 token**。
  - 结论:既断路由又不省 token,纯负优化,**勿用**。
- **[#14882](https://github.com/anthropics/claude-code/issues/14882)(启动即加载 skill 全文,而非仅 description)**:OPEN,2.0.74 复现,2.1.132 / 2.1.207 changelog 均未提修复。**不能指望渐进披露可靠生效**,按"启动可能全载"来设计。

## 可控杠杆(Tessera 已采用)

平台不可靠,唯一能自己控的三条,现状已占:

1. **正文精简**:每块 SKILL.md 保持短(~40 行 ≈ 400–600 token),对冲 #14882 最有效。
2. **按需 opt-in 装**:市集逐块安装,常驻税只对已装拼图收——省法是"别装用不到的",非技术开关。
3. **重活走 subagent**:大流程隔离上下文,不占主会话。

在当前平台约束下,这已接近最优;没有安全的技术开关能再压常驻成本。
