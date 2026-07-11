---
schema: wfos/decision@1
id: go-tessera-migration
status: approved
created: 2026-07-11
approved: 2026-07-11
---

# 采用 Go 单二进制 + 更名 Tessera

## 背景
v2 现状:门(`gate.mjs`)与初始化器(`init-project.mjs`)为零依赖 Node ESM,选型理由是"脚本须在无构建、无 node_modules 的插件缓存快照里被 `node` 直接拉起"。负责人明确要求**放弃零门槛设计,换更强的实现**,并接受在目标机引入运行时/分发成本。

真正的热路径只有**门**——每次工具调用都由 hook 冷启动一次。强化收益几乎全部集中于此。

## 选项
- **A(采纳):Go 单二进制 `tessera`**。门冷启动约 1–8ms(Node 约 30–80ms);静态链接零运行时依赖;`GOOS/GOARCH` 一次交叉编译出全平台;可把门 + 安装器 + 自检 + 状态收敛成一个 CLI(`tessera gate/setup/doctor/selftest/piece/update`)。
- **B:Rust 单二进制**。启动同样快、正确性最强,但对"匹配几条正则 + JSON"表面积过剩,交叉编译更费。
- **C:TypeScript**(Node 24 原生跑 `.ts` 或 release 预编译 `.js`)。改动最小、拿到类型;但治不了启动延迟,也治不了"目标机须先有 Node"。属"稳"非"强"。
- **D:Deno/Bun**。原生 TS、单运行时,但要求目标机装运行时,较 Go"零依赖二进制"退一步。

## 结论
选 **A(Go)**,并将产品更名 **Tessera**(马赛克镶嵌块——每块能力是一片 tessera,拼成整体)。

**押 Go 的三条理由**
1. 把门变成真正的系统工具:标准库覆盖 regex + JSON + stdin,零第三方依赖,冷启动比 Node 快一个数量级。
2. 交叉编译是 Go 看家本领:CI 一次出齐全平台静态二进制,目标机**什么都不用装**——直接消解新机最大摩擦点(先装 Node 24)。
3. 一个二进制 = 门 + 安装器 + 自检 + 状态,分发、签名、版本管理都只有一个东西。

**不选 Rust**:借用检查器对本场景收益边际,换来更慢构建与更费的交叉编译。除非门要做成真安全边界(沙箱/权限模型)。

**契约不变**:`gate` 子命令 stdin→stdout 的裁决 JSON 与 `gate.mjs` **逐字节等价**(Claude `PreToolUse` 的 `permissionDecision`,Codex `PermissionRequest` 的 `behavior:deny`),规则数据文件保持 JSON 数据格式不变。移植以现有 47 条用例为回归基线。

## 迁移里程碑(bd epic `workflow-os-df6`)
- **M1** 门核心移植到 Go(热路径,最高价值/风险)—— `df6.1`
- **M2** `tessera` CLI 子命令 —— `df6.2`
- **M3** 交叉编译 + release 分发 —— `df6.3`
- **M4** 新机一键流程(六阶段) —— `df6.4`
- **M5** 品牌改名 Tessera —— `df6.5`
- **M6** 切 hooks 到二进制 + 弃用旧脚本 —— `df6.6`

## M6 hook 接线实测结论(2026-07-11)
Claude 端 hook 调二进制的关键事实(claude-code-guide + 本机 cmd 实测):
- Claude `hooks.json` **无 `commandWindows`、无 OS 模板**,只有单个 `command`;非零退出 → 输出被忽略 → **fail-open(门静默失效)**。
- **`sh` 不在 Windows 系统 PATH**(cmd 找不到)——agent 推荐的 `sh -c` 条件式在本机会失败 → fail-open,**不可用**。
- **cmd 对显式路径自动补 `.exe`**:单条 `"${CLAUDE_PLUGIN_ROOT}/bin/tessera" gate --platform=claude` 在 Windows(解析到 tessera.exe)与 unix(直接 tessera)**都能跑**,安全→空/exit 0,危险→正确 deny。已实测。
- 但一个安装目录只能放一个平台的 `tessera`;**二进制若缺失,cmd 找不到 → fail-open**。
- **结论:M6 的 hook 切换硬依赖 M4**(安装时放置正确平台二进制);在此之前切换 shipped hook 会让新机 fail-open。已交付 `scripts/build-gate.ps1`(本机构建 + `-All` 全平台交叉编译 + checksums),shipped hook 暂留 `node gate.mjs`(安全)。

## 遗留 / 风险
- **本机 github.com 出站被墙**(见 [bd-install-channel](bd-install-channel.md) 实测:`Connection timed out`)。本地 `go build` 因门零依赖不受影响(离线可编);但 **M3 的 release 分发与 M4 的下载流不能依赖 GitHub Releases**——需镜像或本地通道,M3 落地时再定。
- 目标机 Node 版本偏低会让旧门静默 fail-open(`import.meta.main` 需 Node 24)——迁到二进制后此隐患消失,但过渡期两条门并存需保证只有一条生效。
- 仓库文件夹(`G:\Claude\workflow-os`)与 git remote 是否物理改名,单列一条决策,不在本次范围。
- 更名波及 marketplace id / plugin id / piece id,属破坏性变更;M5 执行时保留旧脚本一段时间做回退。
