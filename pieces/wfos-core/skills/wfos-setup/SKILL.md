---
name: wfos-setup
description: 当用户要"初始化工作流""安装拼图""装 workflow-os""setup 工作流"或在新机器/新项目上部署能力拼图时使用。引导式安装:列出可装拼图,经用户勾选后逐项安装。
---

# wfos-setup 安装引导

## 流程

1. 定位市集仓库根(本 skill 所在插件的 CLAUDE_PLUGIN_ROOT 上溯,或让用户给出 workflow-os 仓库路径)。
2. 读仓库 `.claude-plugin/marketplace.json`(拼图清单)、`registry.yaml`(外部引用;文件缺失则跳过外部段)、各 `pieces/<id>/piece.yaml`(when_to_use/external_deps)。
3. 用 AskUserQuestion(multiSelect)列出:本地拼图(含版本与 summary)+ 外部引用 + 外部 CLI 依赖,让用户勾选。
4. 逐项安装:
   - 本地拼图(Claude):`claude plugin install <id>@workflow-os --scope user`
   - 本地拼图(Codex):`codex plugin add <id>@workflow-os`
   - template-pack 类:按「只补缺」复制模板到项目 `docs/`(文件已存在一律跳过)
   - 外部 CLI:先跑 piece.yaml 的 version_check 探测;缺失才装;**install 命令必须与仓库根 trust.yaml 对应条目的模板逐词一致(全匹配,含未知 flag 即拒),不一致则拒绝执行并打印命令原文让用户手动判断**
5. 输出安装报告:装了什么、跳过什么、哪些需重启会话、哪些需在 Codex 首次运行时确认 hook 信任。

## 硬规则

- 永不静默安装未勾选项;永不执行 trust.yaml 之外的安装命令。
- 本 skill 只经 plugin 通道安装拼图;`~/.claude/skills/`、`~/.agents/skills/` 散装目录是开发模式专用,不写入。
