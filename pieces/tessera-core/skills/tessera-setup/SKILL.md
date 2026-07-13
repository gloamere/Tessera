---
name: tessera-setup
description: 当用户要"初始化工作流""安装拼图""装 Tessera""setup 工作流"或在新机器/新项目上部署能力拼图时使用。引导式安装:列出可装拼图,经用户勾选后逐项安装。
---

# tessera-setup 安装引导

## 流程

1. 定位市集仓库根(从当前 skill 的插件根上溯，或让用户给出 Tessera 仓库路径)，并判断当前宿主是 Codex 还是 Claude；无法判断且会影响命令时才询问。
2. Codex 读 `.agents/plugins/marketplace.json`，Claude 读 `.claude-plugin/marketplace.json`；再读各 `pieces/<id>/piece.yaml`。`registry.yaml` 缺失时跳过外部段。
3. 生成可选列表:
   - 本地拼图：取当前宿主市集中的 id、版本(若该市集提供)与 summary。
   - 外部能力：仅当前宿主 `availability` 为 `installable`、存在 `trust_ref` 且能在 `trust.yaml` 找到匹配项时可选。
   - `status: not-integrated`、`kind` 以 `-candidate` 结尾、`reference-only`、`unverified`、`unsupported` 只能列入“不可安装/研究信息”，不得进入选择项。
4. 优先使用宿主原生多选提问；不可用时输出编号列表，要求用户回复逗号分隔的拼图 id。没有用户选择不得安装。
5. 逐项安装:
   - 本地拼图(Claude):`claude plugin install <id>@tessera --scope user`
   - 本地拼图(Codex):`codex plugin add <id>@tessera`
   - template-pack 类:按「只补缺」复制模板到项目 `docs/`(文件已存在一律跳过)
   - 外部 CLI:先跑 piece.yaml 的 version_check 探测;缺失才装;**install 命令必须与仓库根 trust.yaml 对应条目的模板逐词一致(全匹配,含未知 flag 即拒),不一致则拒绝执行并打印命令原文让用户手动判断**
6. 输出安装报告:装了什么、跳过什么、哪些因未验证或不受支持而不可安装、哪些需重启会话生效。

## 硬规则

- 永不静默安装未勾选项;永不执行 trust.yaml 之外的安装命令。
- 外部能力的 `per_platform.<host>` 安装命令必须与 `trust.yaml` 对应 `install` 逐字一致；不一致就拒绝执行并显示差异。
- 本 skill 只经 plugin 通道安装拼图;`~/.claude/skills/`、`~/.agents/skills/` 散装目录是开发模式专用,不写入。
