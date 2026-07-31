---
name: gloamere-ui-system
description: 当需要从零设计或系统性重构前端页面与组件、建立设计 token 和页面结构、选择配色与字体，或把响应式、交互状态、无障碍规则落实到当前技术栈时使用。负责设计系统与实现约束；已有成品的视觉评审交给 gloamere-visual-review。不要用于纯后端、局部功能 Bug、用户研究或增长实验。
---

# UI 设计系统（Beta）

把产品语境转成可实现、可检查的界面系统。内置的第三方 UI/UX 数据与搜索脚本只提供候选依据，最终取舍仍由当前任务的用户、品牌和技术约束决定。

## 边界

- 使用：新页面/组件、系统性视觉重构、design token、配色/字体方案、响应式、交互状态、无障碍和栈相关实现规则。
- 不使用：纯后端、局部功能 Bug、只问现有页面是否好看、文案审美、用户研究或转化实验。
- 从零设计先用本 Skill 建立系统；已有设计稿或实现需要审美诊断时，改用 `$gloamere-visual-review`。

## Gloamere 编排

- 所有脚本与参考资料都相对当前加载的 `SKILL.md` 所在目录解析，不在工作区或全局目录寻找另一个同名 Skill。
- 先使用用户已经提供的产品语境和技术栈。只有当前项目文件会实质改变方案时才检查仓库。
- 数据库命中是候选证据，不代表完成用户研究、品牌验证或真实可用性测试。

## 流程

1. 提取产品类型、目标用户、使用情境、核心任务和气质关键词。不要只用“现代”“高级”等空词。
2. 新页面或系统性重构运行本 Skill 的 `scripts/search.py`：
   - 完整系统：`python <skill-root>/scripts/search.py "<产品+行业+气质>" --design-system --json`
   - 细分检索：增加 `--domain color|typography|ux|landing|chart|icons|react|web`
   - 栈规则：`--stack react|nextjs|vue|svelte|astro|html-tailwind|shadcn|...`
3. 检索最多两次：默认一次 `--design-system`；只有明显缺口时再选一个 `--domain` 或一个 `--stack`。不要遍历 CSV 或重复换词刷结果。
4. 检查候选与用户语境、已有品牌和技术约束是否冲突。零结果可在第二次预算内换词；误配要解释并舍弃。
5. 输出方向与取舍、核心 tokens、页面结构与状态、响应式与无障碍、技术栈注意点。默认保持紧凑，不重复简报或扩写成框架教程。
6. 只有用户明确要求沉淀跨页设计系统时才使用 `--persist --output-dir <项目根目录>`；已有 MASTER 时先读，未经确认不加 `--force`。

## 交付门槛

- 主次层级、间距、色彩、字体和圆角使用同一 token 系统；颜色至少定义 `background`、`foreground`、`primary`、`accent`、`border` 与状态色，不能只给孤立色值。
- 明列 loading、empty、error、disabled、hover、focus 和 reduced-motion；不能用“完整状态”一笔带过。
- 不用 emoji 充当界面图标；交互目标、键盘导航与对比度可检查。
- 明说本方案主动避免的模板化或场景错配模式，不能只列推荐项。
- 说明数据库匹配依据与人工调整，不伪称完成用户研究或真实可用性验证。

确有缺口时最多读取一份参考：通用规则用 `references/quick-reference.md`，移动端或应用验收用 `references/pro-rules.md`。第三方来源与修改边界见 `references/UPSTREAM.md`。
