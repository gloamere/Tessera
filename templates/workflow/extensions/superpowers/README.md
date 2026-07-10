# Superpowers 开发执行适配器

这是可选适配器，不是 `workflow-os` 的替代品。`workflow-os` 继续负责 Markdown 事实源、负责人拍板、工作包、研究证据与预算；Superpowers 仅在明确的软件开发任务中补强执行。

默认可调用：`brainstorming`、`writing-plans`、`subagent-driven-development`、`systematic-debugging`、`verification-before-completion`。

不默认调用：`using-git-worktrees` 和强制 TDD。游戏私服部署、配置、数值策划和 UI 调整应按风险选择验证方式，不能被统一工程流程绑住。

## 更新策略

1. 总指挥在需要时调研官方 Release 与变更说明。
2. 运行 `workflow-os adapter check superpowers --version <version> --release-url <url>` 记录候选版本；状态文件位于 `.workflow/runtime/`，不会提交到 Git。
3. 向负责人说明新旧行为差异、与 `AGENTS.md` 的冲突风险及回退方式；仅在确认后才在 Codex 插件界面安装或更新。
4. 更新后用一个小型开发工作包验证：计划、子 agent、测试和完成校验均能正常工作。

不要让 Superpowers 覆盖 `AGENTS.md` 中 workflow-os 的托管块；以项目规则、拍板闸门和预算守卫为准。
