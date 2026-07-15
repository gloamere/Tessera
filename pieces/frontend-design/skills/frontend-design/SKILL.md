---
name: frontend-design
description: 当需要从零设计或系统性重构前端页面/组件、建立设计 token 与页面结构、选择配色字体、或把 UX/响应式/无障碍规则落实到当前技术栈时使用。负责“设计系统与实现约束”；已有成品的纯审美评审和去 AI 味交给 taste。
---

# 前端设计系统

把产品语境转成可执行的设计系统和技术栈约束。内置本地 UI/UX 数据库；搜索结果是候选证据，不是不可质疑的设计结论。

## 边界

- 使用：新页面/组件、系统性视觉重构、design token、配色/字体方案、响应式、交互状态、无障碍和栈相关实现规则。
- 不使用：纯后端、局部功能 Bug、只问现有页面是否好看、文案审美、用户研究或转化实验。
- `frontend-design` 先给系统与约束；页面实现完成后，只有用户要求审美评审或结果明显需要去模板化时再使用 `taste`。

## 流程

1. 从仓库识别技术栈；无法识别且会改变方案时再询问。
2. 提取产品类型、目标用户、使用情境和气质关键词。不要只用“现代”“高级”等空词。
3. 新页面或系统性重构先运行本 Skill 的 `scripts/search.py`：
   - 完整系统：`python <skill-root>/scripts/search.py "<产品+行业+气质>" --design-system --json`
   - 细分检索：增加 `--domain color|typography|ux|landing|chart|icons|react|web`
   - 栈规则：`--stack react|nextjs|vue|svelte|astro|html-tailwind|shadcn|...`
4. 检查候选是否与用户语境冲突。零结果要换词重试；明显误配要解释并改选，不能把数据库输出当事实。
5. 输出：设计方向、tokens、页面结构、组件/状态、响应式与无障碍约束、当前栈的实现注意点。
6. 只有用户明确要求沉淀跨页设计系统时才使用 `--persist --output-dir <项目根目录>`；已有 MASTER 时先读，未经确认不加 `--force`。

## 交付门槛

- 主次层级、间距、色彩、字体和圆角使用同一 token 系统；颜色至少定义 `background`、`foreground`、`primary`、`accent`、`border` 与状态色，不能只给孤立色值。
- 明列 loading、empty、error、disabled、hover、focus 和 reduced-motion；不能用“完整状态”一笔带过。
- 不用 emoji 充当界面图标；交互目标、键盘导航与对比度可检查。
- 明说本方案主动避免的模板化或场景错配模式，不能只列推荐项。
- 说明数据库匹配依据与人工调整，不伪称完成用户研究或真实可用性验证。

需要完整规则时按需读取 `references/quick-reference.md`；移动端/应用交付检查读取 `references/pro-rules.md`。
