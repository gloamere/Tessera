# Tessera 拼图脚手架命令 设计

日期:2026-07-12
状态:approved(设计已在对话中确认)

## 背景与问题

一块拼图 = `pieces/<id>/` 下固定 4 类文件(`piece.yaml`、`.claude-plugin/plugin.json`、`.codex-plugin/plugin.json`、`skills/<name>/SKILL.md`)。新增一块要手工碰 **7 处**:4 个文件 + 两份 marketplace 登记 + `piece-router` 路由表。删除碰 4 处,升版本要同步 3 个 version 字段。

痛点:重复样板 + 多处同步,易漏。现有 `tessera piece` 只有 `list`。`repocheck`(两市集名单一致 / 3 个 version 一致 / Codex 条目字段齐 / 无 BOM)能抓住漂移,但**不校验路由表完整性**——漏加路由行是静默的坑。

## 目标

扩 `tessera piece` 增加 `new` / `rm` / `bump` 三个子命令,把样板与多处同步自动化。全部**非交互**(AGENTS.md 要求 Codex/Claude 靠 flag 驱动)。

非目标(YAGNI):交互式问答;自动改 `registry.yaml`(外部依赖罕见,手动);自动 git 提交(提交仍人工);`bump` 不动 codex marketplace(该文件无 version 字段)。

## 命令规格

### `tessera piece new <id> [--skill <name>] [--intent "…"] [--desc "…"]`

`--desc` 省略时默认 = `<id> 拼图`;`--skill` 省略时默认 = `<id>`。

生成:
- `pieces/<id>/piece.yaml` —— 模板:`id`、`kind: skill`、`summary`(取 `--desc`)、`when_to_use`(占位一条)、`avoid_when`(占位)、`platforms: { claude: native, codex: native, gemini: snippet, domestic: snippet }`、`external_deps: []`、`upgrade_policy: notify-only`
- `pieces/<id>/.claude-plugin/plugin.json` —— `{ name:<id>, description:<desc>, version:"0.1.0", author:{name:"van"} }`
- `pieces/<id>/.codex-plugin/plugin.json` —— `{ name:<id>, description:<desc>, version:"0.1.0", skills:"./skills/" }`
- `pieces/<id>/skills/<name>/SKILL.md` —— frontmatter `name`+`description` + 正文占位标题(`<name>` 默认 = `<id>`)

登记:
- 追加进 `.claude-plugin/marketplace.json`:`{ name:<id>, source:"./pieces/<id>", description:<desc>, version:"0.1.0", strict:true }`
- 追加进 `.agents/plugins/marketplace.json`:`{ name:<id>, source:{source:"local", path:"./pieces/<id>"}, policy:{installation:"AVAILABLE", authentication:"ON_INSTALL"}, category:"Productivity" }`
- 给了 `--intent` → 往 `piece-router` SKILL.md 插一行 `| <intent> | <id> | Skill 工具调用 <id> |`(插在含 "tessera-core 自身" 的自路由行之前);没给 → stdout 打印提醒 "别忘了手动在 piece-router 加一行"

收尾:跑 `repocheck.CheckMarketplaces` 并报告绿/红。

拒绝条件:`pieces/<id>` 目录已存在,或 `<id>` 已在任一 marketplace → 报错,不做任何写入。

### `tessera piece rm <id> [--yes]`

- 删 `pieces/<id>/` 目录;从两份 marketplace 摘除条目;若 `piece-router` 有 `<id>` 的行则删除该行
- **不可逆保护**:不带 `--yes` → 只 dry-run,打印"将删除:<目录 + 两处登记 + 路由行>",不动文件;带 `--yes` → 真删
- 硬拒 `rm tessera-core`(内核不可删)
- 找不到 `<id>` → 报错
- 收尾:跑 `repocheck.CheckMarketplaces` 报告

### `tessera piece bump <id> <version>`

- 同步写 3 个 version 字段:`pieces/<id>/.claude-plugin/plugin.json`、`pieces/<id>/.codex-plugin/plugin.json`、`.claude-plugin/marketplace.json` 中 `<id>` 条目
- `<version>` 校验为 `X.Y.Z` 形式(宽松,非法则报错)
- 找不到 `<id>` → 报错
- 收尾:跑 `repocheck.CheckMarketplaces` 报告

## 关键技术取舍:JSON 编辑策略

改两份 marketplace.json 采用 **解析 → 改 → 标准缩进重写(`json.MarshalIndent` 2 空格 + 结尾换行)**。

- 优点:代码简单、健壮,不依赖括号/逗号位置的文本拼接。
- 代价:**首次运行会把两份 marketplace 现有手工紧凑排版重排成标准缩进**——一次性噪音 diff,内容与语义不变,`repocheck` 只解析不看空白,照样绿。
- 备选(否决):纯文本拼接插入,保排版但对格式脆弱、易出 bug。脚手架工具健壮性 > 保留手写排版。

写文件一律 UTF-8 无 BOM(`repocheck.BOMFiles` 会抓 BOM)。

## 架构与落点

- `cmd/tessera/main.go` —— `piece` 分发新增 `new|rm|bump`(现有 `list` 保留);解析各自 flag,调 `internal/piece` 的函数,统一在收尾调 `repocheck.CheckMarketplaces` 打印结果
- `internal/piece/scaffold.go` —— 纯逻辑:`New(root, opts)`、`Remove(root, id, confirm bool)`、`Bump(root, id, version)`;模板以 Go 字符串常量内嵌;marketplace 读写辅助(解析→改→MarshalIndent)
- 复用 `internal/repocheck`(已有 `CheckMarketplaces`)做收尾校验,不重造

每个函数单一职责、可独立测试:输入 repo 根路径 + 参数,产生文件系统副作用 + 返回 error,不打印(打印留给 `main.go`)。

## 测试

`internal/piece/scaffold_test.go`(用 `t.TempDir()` 搭最小 repo:两份空 marketplace + piece-router 桩):
- `New`:生成 4 文件齐全、两 marketplace 各多一条、给 `--intent` 时路由表多一行、之后 `CheckMarketplaces` 通过
- `New` 拒绝:`<id>` 已存在时报错且无写入
- `Remove`:目录 + 两处登记 + 路由行三处都清干净;`--yes=false` 时 dry-run 不动文件;`rm tessera-core` 被拒;不存在报错
- `Bump`:3 个 version 字段同步;非法版本报错;不存在报错
- 回归:`repocheck` 现有测试仍全绿;`go test ./...` 全绿

## 验收

`go test ./...` 全绿;手动 `tessera piece new demo --skill demo --intent "演示" --desc "演示拼图"` 后 `tessera doctor` 识别 +1 块、两市集一致;`tessera piece rm demo --yes` 后回到原状、doctor 仍绿。
