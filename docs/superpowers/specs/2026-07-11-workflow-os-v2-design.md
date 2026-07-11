# workflow-os v2 设计:个人能力操作系统(拼图市集)

- **状态**:待负责人审阅
- **日期**:2026-07-11
- **分支**:`design/workflow-os-v2`
- **来源**:头脑风暴(6 轮澄清)→ 4 方案设计竞赛(4 设计 × 2 红队 × 3 评委,15 agent)→ Codex(gpt-5.6)外部评审 → 能力声明核查(7 agent,全部核实属实)→ spec 三视角自审(修订于本版)。证据存档见附录 A。

## 1. 目标与非目标

**目标**:一个易移植、通用、每个环节可替换/可成长的**个人**工作流操作系统:

1. **拼图注册表**——集中登记每块能力拼图:是什么、何时用、支持哪些平台、怎么装、怎么查版本。
2. **意图路由**——宿主 agent 主会话(一级 gateway)识别工作内容,派发对应拼图(skill / CLI / 插件 / 将来的 subagent)。
3. **管理现有工具而非重新实现**——默认拼图集:wfos-core、bd-tasks、taste、knowledge-base(本地)+ superpowers、agent-reach(外部引用);planner 散装孵化。
4. **低摩擦安装(两条命令 + 一次 /wfos-setup)+ 定期自主升级**——发现新版→报负责人确认,绝不静默升级。
5. **双端一等公民**:Claude Code 与 Codex;Gemini/国产 AI 薄适配(M4)。

**非目标**:项目任务记账系统(归 bd,**永不复活**,§2 裁决)、SQLite/数据库、常驻服务/计划任务、Obsidian 专用插件、团队/多用户场景(其余项的触发条件见 §19)。

## 2. 已拍板决策记录

| 日期 | 决策 | 说明 |
|---|---|---|
| 2026-07-10 | 任务追踪交给 bd,workflow-os 不自建任务系统 | bd 0.62+ 能力是旧版记账索引的超集 |
| 2026-07-10 | 注册表用文件,不用 SQLite | 4~15 条记录;官方状态文件已记版本/scope/哈希 |
| 2026-07-10 | 拼图 = 管理现有工具,不重新实现能力 | reach/taste/superpowers/bd 为默认对象 |
| 2026-07-11 | 采纳候选 A(拼图市集),Codex 核查后升级为双端一等 | 见 §3 |
| 2026-07-11 | SQLite 记账系统不复活(负责人终裁) | 旧系统从未实际使用,git 历史保留 |
| 2026-07-11 | 门必须是有执行力的机制 | **不可逆操作门**为硬机制(平台 hook);**方向性拍板门**以共享状态文件为载体、其落地动作由不可逆操作门兜底,定性见 §7 |

## 3. 总体架构

三层:**市集仓库**(数据层,本仓库即注册表与分发源)→ **wfos-core**(内核插件:路由兜底、安装、升级、体检、门)→ **能力拼图**。

关键机制全部复用平台原生能力,并利用两平台同构性:

- **同一份 SKILL.md 双端通用**(name/description frontmatter;实测 Claude 格式 skill 经 symlink 被 Codex 正常加载)。
- **仓库同时是两个市集**:`.claude-plugin/marketplace.json` 与 `.agents/plugins/marketplace.json` 由各拼图 `piece.yaml` 生成。
- **hook 脚本双端复用**:Codex 兼容 `CLAUDE_PLUGIN_ROOT`/`CLAUDE_PLUGIN_DATA`;差异只在配置载体与裁决字段(§7)。
- gateway 即宿主主会话;无常驻程序、无数据库、无独立发行 CLI。自建脚本约 400~600 行量级(设计参考,非验收项):check-updates.mjs(含 --doctor)、gate.mjs、wos-bump.mjs;M4 再加 inject-block.mjs(~150 行)。

**拼图形态与安装方式**(按 kind):

| kind | 形态 | 安装方式 |
|---|---|---|
| `skill` / `cli-wrapper` | 独立插件(自带双 manifest + skills/) | `claude plugin install` / `codex plugin add` |
| `template-pack` | 模板包,非插件 | wfos-setup 按「只补缺」复制文件 |
| `plugin-ref` | 外部引用,不在本市集 | 按 registry.yaml 声明的各平台命令安装 |
| `subagent` / `workflow` | 预留枚举(planner 成熟后用) | 待定义 |

## 4. 仓库布局

```text
G:\Claude\workflow-os\        # 名义路径;脚本定位自身资源一律用 CLAUDE_PLUGIN_ROOT(双端可用),不硬编码
├── .claude-plugin\marketplace.json      # Claude 市集清单(生成物,提交入库)
├── .agents\plugins\marketplace.json     # Codex 市集清单(生成物,提交入库)
├── trust.yaml                           # 安装白名单(§11)
├── registry.yaml                        # 外部引用登记(schema 见 §5;M1 骨架就位)
├── targets.yaml                         # M4:平台名 → 注入目标路径
├── pieces\
│   ├── wfos-core\
│   │   ├── .claude-plugin\plugin.json   # 生成物
│   │   ├── .codex-plugin\plugin.json    # 生成物
│   │   ├── piece.yaml
│   │   ├── skills\{piece-router, wfos-setup, wfos-upgrade}\SKILL.md
│   │   ├── commands\{wfos-status, wfos-upgrade}.md
│   │   ├── hooks\claude.hooks.json      # M1:PreToolUse(门);M2 追加 SessionStart
│   │   ├── hooks\codex.hooks.json       # M1:PermissionRequest(门);M2 追加 SessionStart
│   │   ├── gate-rules.yaml              # 危险模式清单(数据,§7)
│   │   └── scripts\{gate.mjs, check-updates.mjs(M2)}
│   ├── bd-tasks\      # kind: cli-wrapper,独立插件(结构同 wfos-core,省略)
│   ├── taste\         # kind: skill(M0 先核实来源;本机当前未安装)
│   ├── planner\       # 散装孵化,M3 只建骨架目录与 README
│   └── knowledge-base\ # kind: template-pack:decisions/research/briefs 模板
├── legacy\README.md   # 指向旧实现 git 引用(commit 973a85b),不留工作副本
├── scripts\{wos-bump.mjs, inject-block.mjs(M4)}
└── docs\superpowers\specs\
```

**路径解析规则(统一)**:① 脚本定位自身/拼图资源:`CLAUDE_PLUGIN_ROOT` 环境变量(两端都注入);② 机器级状态:`os.homedir()/.workflow-os/state.json`(上次检查时间与失败原因、已确认版本/来源、已忽略提醒;可删可重建);③ 「从 cwd 向上找 `.git`」**仅**用于 wfos-setup 向用户项目写模板时定位用户项目根;④ M4 snippet 内路径在注入时绝对化。

## 5. 拼图清单(piece.yaml)

语义事实源。`wos-bump` 从它生成市集条目与 plugin manifest。schema 要点:

- `id`;`kind`:`skill | plugin-ref | cli-wrapper | template-pack`(预留 `subagent | workflow`)
- `summary: string`;`when_to_use: string[]`(路由语义);`avoid_when: string`
- `platforms`:每平台 `native | snippet | none`
- `external_deps[]`:`version_check`(本机命令,取 stdout 全部 semver 的最大值)、`latest_check`(`method: github-release | npm | self`;`self` 契约:运行 `command`,提取输出中全部 semver 取最大与本地比较,无 semver 即失败并自动落到 `fallback`)、`install`(按平台)、`trust_ref`(必须命中 trust.yaml 同名条目)
- `upgrade_policy: notify-only`(唯一合法值)

示例(`pieces/bd-tasks/piece.yaml`):

```yaml
id: bd-tasks
kind: cli-wrapper
summary: 任务追踪。管理现有 bd (beads) CLI,不重新实现任务系统。
when_to_use:
  - 新任务/待办/需求拆解 → bd create / bd q
  - 会话开始找活干 → bd ready
  - 多步骤工作 → bd create --type epic + bd dep
  - 需要负责人异步确认的节点 → bd gate(仅作异步通知载体;权威状态是 decisions 文件,见 §7)
  - 禁止:TodoWrite、markdown TODO 列表
avoid_when: 纯问答、无需跟踪的一次性小操作
platforms: { claude: native, codex: native, gemini: snippet, domestic: snippet }
external_deps:
  - name: bd
    version_check: "bd version"
    latest_check:
      method: self
      command: "bd upgrade status"
      fallback: { method: github-release, repo: gastownhall/beads }   # 原 steveyegge/beads 已迁移
    install:
      windows: "npm install -g @beads/bd"
    trust_ref: bd
upgrade_policy: notify-only
```

**trust.yaml**(每 kind 定义唯一规范命令模板,全匹配=命令与模板逐参数一致、含未知 flag 即拒):

```yaml
allowed_installs:
  - id: bd
    kind: npm-global            # 模板:npm install -g <package>[@<pin>]
    package: "@beads/bd"
    pin: null                   # 可选 semver;锁版后升级提醒跳过
    upstream: gastownhall/beads
  - id: superpowers
    kind: claude-marketplace    # 模板:claude plugin marketplace add <source>
    source: obra/superpowers-marketplace
    install: "claude plugin install superpowers@superpowers-marketplace"
```

**registry.yaml**(外部引用,最小 schema:`id`、`kind: plugin-ref`、`summary`、`per_platform.{claude,codex}` 获取方式、可选 `version_check`/`latest_check`、`trust_ref`):superpowers 在 Claude 走官方市集;在 Codex 端 M3 验证两条候选路径——`codex plugin marketplace add obra/superpowers-marketplace`(Codex 兼容读 `.claude-plugin/marketplace.json`)或 skills symlink 到 `~/.agents/skills/`(本机已证 Claude 格式可读)——择优写死。agent-reach 登记为外部 skill + 其机器级 CLI 生态的 external_deps 体检项,不收编。

## 6. 意图路由

三级,零自建路由代码:

1. **原生自动触发**:SKILL.md description 写触发场景;两端均按 description 隐式触发(Codex 经 `codex debug prompt-input` 实测)。
2. **兜底**:`piece-router` skill(面向复合/模糊意图),正文一页派发表:调研→reach、UI→taste、写代码→superpowers 流程链、任务→bd、策划→planner;含门规则引用。
3. **手动**:`/wfos-status` 等 slash command(Claude)、`$skill` 显式调用(Codex)。

不做 UserPromptSubmit 关键词匹配(误报机制性有害)。

## 7. 门(两类)

### 7.1 方向性拍板门(设计/策划/UI/技术路线)

- **载体**:`docs/decisions/<slug>.md` frontmatter(`status: pending | approved | rejected`),knowledge-base 拼图提供模板(M3)。**decisions 文件状态是唯一权威**;`bd gate` 仅作异步通知/阻塞载体,关门前必须回写文件状态。
- **规则注入**:M1~M3 仅经 skill 文本(piece-router、planner);M4 起对薄适配平台经托管块。规则:关联决策未 `approved`,不得执行会固化方向的实现任务。
- **如实定性**:这是「共享状态文件 + 规则文本」的约定级机制,任何平台的 agent 读同一份状态;其**落地动作**(push、发布、批量改写)由 7.2 的硬门兜底。完整可用时点为 M3(模板就位)。§2 拍板按此口径满足。

### 7.2 不可逆操作门(硬机制)

载体:`gate-rules.yaml`(数据文件)+ `gate.mjs`(匹配逻辑双端共用,输出层分平台)。初始清单:

| # | 模式(Bash 与 PowerShell 双语法) | Claude | Codex |
|---|---|---|---|
| 1 | 递归强制删除,目标在项目根之外/盘符/家目录(`rm -rf`、`Remove-Item -Recurse -Force`) | ask | **deny** |
| 2 | 项目内递归强制删除 | ask | 原生审批 |
| 3 | `git push --force/-f` 到 main/master | ask | **deny** |
| 4 | `git push --force/-f` 其他分支 | ask | 原生审批 |
| 5 | `git reset --hard` / `git checkout -- .` / `git clean -fd`(丢弃未提交改动) | ask | 原生审批 |
| 6 | 白名单外全局安装(`npm i -g`、`pip install` 等非 trust 条目) | ask | 原生审批 |
| 7 | 改写 trust.yaml / gate-rules.yaml 自身 | ask | **deny** |

平台语义:Claude PreToolUse → `permissionDecision:"ask"`(matcher `Bash|PowerShell`);Codex PermissionRequest → 表中 deny 项输出 deny(带 reason),其余不裁决→走原生审批弹窗。**Codex PreToolUse 的 `permissionDecision:"ask"` fail-open(标失败后继续),严禁使用。** 如实定性:hooks 是 guardrail 而非完整安全边界(官方原话;存在绕过路径),硬约束依赖各平台原生 sandbox/permissions;能用原生 permissions 规则表达的优先生成原生规则。

## 8. 安装

**机器级(一次性)**:

```text
Claude:claude plugin marketplace add <repo路径>
        claude plugin install wfos-core@workflow-os --scope user
Codex: codex plugin marketplace add <repo路径>
        codex plugin add wfos-core@workflow-os
```

前置(M0 落实):确定 Codex CLI 调用方式——桌面版自带 `codex.exe` 不在 PATH,M0 决定加 PATH shim 或文档写全路径。

重启后跑 `/wfos-setup`:读市集清单 + registry.yaml(缺失则跳过外部引用段)+ 各 piece.yaml → 列清单 → AskUserQuestion 勾选 → 逐项安装:`skill`/`cli-wrapper` 拼图走 plugin 安装;`template-pack` 按「只补缺」复制(文件存在即跳过,不做哈希仪式);外部 CLI 先探测(`bd version`),缺失才装,install 命令必须全匹配 trust.yaml 模板,否则拒绝并打印手动命令。**wfos-setup 只经 plugin 通道安装拼图;`~/.claude/skills/`、`~/.agents/skills/` 散装目录专属开发模式(§10),不进 setup 安装路径。**

**项目级(每项目,很薄)**:user-scope 安装天然覆盖所有项目;需要知识沉淀时 `/wfos-setup 项目模板` 写入 `docs/`;Codex 项目级定制 skill 放 `<repo>/.agents/skills/`(实测自动发现)。

**安装报告**:装了什么、跳过什么、需重启项、需信任确认项(Codex 插件 hooks 为 non-managed,首次运行需显式 trust)。

## 9. 升级与体检

**探测(自动,只读)**:M2 起,两端 SessionStart hook 运行 `check-updates.mjs`——读 state.json,距上次 <7 天直接退出;到期则比对本地市集清单与已装版本(`installed_plugins.json` / `codex plugin list` 仅作探测器,user scope 优先)、按 latest_check 查外部件(带超时;网络失败静默跳过,原因写 state,下次会话提示「上次检查失败」,由用户择机手动重试)。发现差异输出一行提醒(Claude:`hookSpecificOutput.additionalContext`;Codex:按实测的输出契约)。hook 无执行权。

**确认与执行(人工)**:`/wfos-upgrade` 列明细 → AskUserQuestion 逐项确认 → 执行:

- **本地拼图,Claude 端**:`claude plugin update <名>@workflow-os`(须带全名);
- **本地拼图,Codex 端**:本地路径市集是**活引用**,直接重跑 `codex plugin add <名>@workflow-os` 装入新版本快照(实测 0.2.0→0.3.0,无需 remove);`codex plugin marketplace upgrade` **仅适用于 Git 市集**,本地市集报错,不用;
- **外部 CLI**:trust.yaml 校验通过的升级命令;**bd 特例**:升级前强制过 doctor 双安装检查(C:\env 手解 exe 遮蔽 npm shim),未统一通道前只提示不执行;
- 完成后提示重启生效。旧版本快照缓存需手动删除 `~/.claude/plugins/cache/<市集>/<插件>/<旧版本>`(`plugin prune` 只清孤儿自动依赖,实测不清版本快照)。

**doctor(体检,M2)**:`check-updates.mjs --doctor`,经 `/wfos-status` 暴露。检查项:bd 双安装遮蔽、插件双 scope 并存、hook 配置在位且脚本可执行、市集清单与 plugin.json 版本一致性、trust_ref 悬空。

## 10. 开发迭代模式(消解发布税)

- **调优期**:skill 散装(Claude `~/.claude/skills/`;Codex `~/.agents/skills/` 或 repo 级 `.agents/skills/`),改完下个会话生效。
- **稳定后**:移入 `pieces/<id>/skills/`,跑 `node scripts/wos-bump.mjs <piece>`——同步 bump piece.yaml/双 plugin.json/双市集清单版本 → `claude plugin validate .`(含无 BOM 检查)→ 两端重装 → 提示重启。一条命令完成发布。
- 收编时删除散装副本,避免双份触发。

## 11. 安全模型

1. **声明与执行分离**:piece.yaml/registry.yaml 是纯声明,无自动执行器盲跑其中命令。
2. **自动执行面全量列举**:`check-updates.mjs`(SessionStart:只读探测 + 写自家 state)与 `gate.mjs`(工具调用时:只读匹配 + 输出裁决)。两者物理上均不含安装逻辑。
3. **白名单外置且不可扩权**:trust.yaml 在 git 管控下,固定参数模板全匹配;piece.yaml 只能 `trust_ref` 指向既有条目,不能扩充。
4. **平台权限兜底**:安装/升级命令仍过各平台原生权限弹窗;settings 只 allowlist 只读命令。
5. **升级不静默**:notify-only 唯一策略;执行只发生在用户确认后。
6. **执行不经 shell**:spawn + 参数数组,无字符串拼接/变量展开。

## 12. 多平台(M4,触发条件:实际开始在 Gemini/国产平台干活)

- **Gemini**:skill 拼图用原生 `gemini skills link <path>`(gemini 0.41.2 实测有 skills 子命令);路由表注入 `~/.gemini/GEMINI.md` 托管块。
- **国产 CLI**:targets.yaml 登记「平台名→上下文文件路径」,同一注入器换目标,零平台专有代码。
- **注入器** `inject-block.mjs`(~150 行):移植旧版标记块 + sha256 + 冲突检测,**新写「块内容被手改→警告不覆盖」**(核实旧代码只有标记畸形拒写);只改标记区间;snippet 路径注入时绝对化,绝不指向版本化缓存。

## 13. Windows 工程约束

- 生成/写入的 JSON/YAML/MD 一律**无 BOM UTF-8**(PowerShell 5.1 默认 BOM 会让 `claude plugin validate` 报错);wos-bump 内置校验。
- 零 POSIX 习语:存在性检查用 Node `fs`,家目录 `os.homedir()`,无 `~` 展开、无 `test -d`。
- hook 直接 `node <script>` 调用,不套 cmd/bash 包装。
- 路径解析规则见 §4。

## 14. 旧系统处置对照表

| 旧功能(v1,从未实际使用) | 去向 |
|---|---|
| work-item/decision 记账 + status/context CLI | bd(create/ready/show/epic/dep/gate);decisions 文件保留为拍板门载体(模板重写) |
| Markdown→SQLite 索引(1363 行)+ 文件锁 + sync/rebuild | 删除(无派生存储即无一致性问题) |
| guard 轮次守卫 + agent-budget.yaml | 理念并入门与平台原生机制;不做轮次计数器 |
| research 流程(scout/analyst/auditor、Evidence Cards) | 调研拼图承接(agent-reach + 平台 deep-research 类 skill);模板精华并入 knowledge-base |
| ingest(MarkItDown) | 可选外部 CLI 拼图,按需登记,非默认集 |
| AGENTS.md 托管块 + manifest 哈希 + 本地覆盖检测 | 唯一成建制移植资产 → inject-block.mjs(M4) |
| pip 白名单(源码硬编码) | trust.yaml(原则不变:配置不能扩权) |
| .codex/agents/*.toml + 硬编码模型名 | 删除;Codex 走原生插件/skills,不写模型名 |
| templates/docs(PROJECT/NOW/INBOX/work…) | 记账类模板删除;decisions/research/briefs 重写进 knowledge-base |

处置方式:旧实现完整保留于 git 历史(`main`、`fix/concurrency-and-cli-hardening`,HEAD=973a85b),v2 分支删除工作副本,`legacy/README.md` 留指引。不重写历史,不做迁移测试(无存量数据)。

## 15. 错误处理

- 升级探测网络失败:静默跳过 + 原因入 state,下次 SessionStart 提示;不内置 DoH/镜像组件(人工核查文档时才用这类手段)。
- `installed_plugins.json` 解析失败/格式变化:降级 `claude plugin list` 文本解析;再失败显示 unknown,不阻塞。双 scope:user 优先 + doctor 警告。
- Codex 插件 hooks 不生效(plugin_hooks flag 可疑):回退写 `~/.codex/hooks.json` 全局配置(确切路径与事件命名大小写为 M1 冒烟项,二进制迹象为 kebab-case)。
- 托管块冲突(M4):手改即停,`--force` 才覆盖。
- 市集清单校验失败:wos-bump 拒绝发布并指出字段。

## 16. 测试

`node --test`(旧测试随旧系统删除,全部新写):

- check-updates:节流、超时、state 读写、多 scope 消歧、降级链、doctor 各检查项(bd 双安装、双 scope、版本一致性)
- gate:七条模式的 Bash+PowerShell 变体与常见绕过拼写;Claude/Codex 两种输出格式
- trust:全匹配通过、未知 flag 拒绝、trust_ref 悬空拒绝、pin 语义
- wos-bump:版本同步、无 BOM、清单生成一致性
- 注入器五分支(创建/更新/追加/畸形拒写/手改警告)——**M4 触发时才写**

集成冒烟(手动脚本):双端 `marketplace add → install → 改版本 → 升级(Claude update / Codex 重 add)` 全链路;`codex debug prompt-input` 验证 skill 注入;**M1 准入冒烟**:① Codex 插件 hooks 实际触发(plugin_hooks flag 疑点);② 全局 `~/.codex/hooks.json` 路径与事件命名;③ Codex CLI 调用方式;④ PermissionRequest deny 实际拦截 + reason 显示。

## 17. 里程碑

实现计划映射:**M0+M1 = 第一份实现计划(核心可用);M2+M3 = 第二份;M4 触发时单独成计划。**

| 阶段 | 内容 | 验收(可判定) | 量 |
|---|---|---|---|
| M0 | v2 分支清删旧工作副本;taste-skill 来源核实(Leonxlnx/taste-skill);bd 双安装通道决策;Codex CLI 调用方式决策 | `src/ bin/ templates/ test/` 删除、`legacy/README.md` 与 `pieces/` 骨架在位;`docs/decisions/bd-install-channel.md` 与 `codex-cli-access.md` 状态非 pending;taste 来源确认或降级出默认集 | 半天 |
| M1 | piece.yaml + 双市集清单 + registry.yaml 骨架 + wfos-core(piece-router / wfos-setup / /wfos-status / 双端门 hooks + gate-rules.yaml)+ bd-tasks 插件;四项准入冒烟(§16) | 两端 install wfos-core **与 bd-tasks** 成功;Claude 端表 1/3/7 模式弹 ask;Codex 端表 1/3/7 被 deny 且 reason 显示、表 2/4/5/6 走原生审批;bd 路由:slash/$skill 显式调用 100% 生效,3~5 条固定 prompt 隐式冒烟记录命中(不设硬阈值) | 1.5~2 天 |
| M2 | 升级链:check-updates(SessionStart 两端接入)+ doctor + /wfos-upgrade + wos-bump | 改版本号→两端下次会话收到提醒→确认→Claude update / Codex 重 add→重启生效;doctor 报出本机已知的 bd 双安装与 superpowers 双 scope | 半天~1 天 |
| M3 | taste 收编、planner 骨架(散装,不进 setup 验收)、knowledge-base(decisions 拍板门模板)、registry.yaml 外部条目 + superpowers Codex 路径择优 | `/wfos-setup` 走通默认集(wfos-core、bd-tasks、taste、knowledge-base + 外部 superpowers、agent-reach);用模板新建一个 decision,门 skill 能正确区分 pending/approved | 1 天 |
| M4(可选) | Gemini(`skills link` + GEMINI.md 块)、国产(targets.yaml)、inject-block.mjs | `gemini skills link` 后至少一块拼图实际触发;注入器五分支测试通过;targets.yaml 新增平台零代码 | 半天~1 天 |

M0~M3 合计 3.5~4.5 天;M4 触发时另计 0.5~1 天。M1 结束即日常可用。

## 18. 风险与缓解

- **description 路由是概率触发**:piece-router 兜底 + 手动入口;散装模式让调优零成本。
- **plugin CLI 表面较新,语义可能变**(已知坑:Claude update 须带全名;Codex marketplace upgrade 仅 Git 市集):命令全部封装在 setup/upgrade skill 文档,坏了改一处。
- **Codex plugin_hooks flag 状态可疑**:M1 冒烟为准入项,回退路径已定(§15)。
- **hooks 契约演进快**:doctor 含 hook 自检;升级宿主后跑一次。
- **上游变化**(bd 已迁 gastownhall、跨 1.x):latest_check 优先用工具自带命令,仓库坐标作 fallback。
- **本机网络对 OpenAI 文档域 DNS 污染**:自动化不依赖这些域;人工核查用 DoH/镜像。

## 19. 明确不做与触发条件

| 不做 | 触发条件(到了再做) |
|---|---|
| 任务记账系统 | **永不**(§2 负责人终裁) |
| SQLite / 任何数据库 | 拼图 >50 或出现真实跨字段查询需求 |
| 独立发行 CLI / npm 包 | 出现第二个用户 |
| 计划任务/常驻调度 | SessionStart 提醒被证实不够用 |
| UserPromptSubmit 关键词路由 | 永不(误报机制性有害) |
| Obsidian 专用适配 | knowledge-base 的 Markdown 本身 Obsidian 可开;出现真实可视化工作流再议 |
| Gemini/国产深度适配 | 实际开始在该平台干活 |
| subagent/workflow 类拼图实现 | planner 内容成熟、需要编排形态时(schema 已预留) |

## 附录 A:已核实平台事实(2026-07,证据存档于会话 scratchpad)

**Claude Code 2.1.132**:
- 本地路径市集 add / install(--scope user)/ update 全链路实测可用;`plugin update` 须带 `@marketplace` 全名;validate 拒绝 BOM。
- 插件缓存为版本化快照;uninstall/update 不清缓存;**`plugin prune` 只清孤儿自动依赖,实测(dry-run)不清已卸载插件与旧版本快照**——旧快照需手动删除。
- `installed_plugins.json` 同一插件可多 scope 并存(本机 superpowers:project 5.0.6 + user 6.1.1)。

**Codex Desktop 26.608.12217 / CLI 0.138.0-alpha.7**(本机在用,CLI 不在 PATH):
- skills 按 description 隐式触发;repo 级 `.agents/skills/` 实验实测自动发现;`~/.agents/skills` 与 `~/.codex/skills` 双目录均被扫描(探针实测;官方推荐目录以文档为准)。
- `codex plugin marketplace add <本地路径|owner/repo|git-url>` 实测存在;**本地路径市集为活引用(list 的 ROOT 即源路径,非快照);重复 `codex plugin add <名>@<市集>` 即装入新版本快照(实测 0.2.0→0.3.0,无需 remove);`marketplace upgrade` 仅适用 Git 市集,对本地路径市集报错**(自审实测)。
- 插件含 skills/hooks/MCP/apps;兼容读 `.claude-plugin/marketplace.json` 与 `CLAUDE_PLUGIN_ROOT`;`plugin_hooks` feature flag 状态可疑(removed/false),M1 冒烟定论。
- hooks:10 事件;**PreToolUse `permissionDecision:"ask"` 不支持且 fail-open**(二进制错误串 + 源码测试 `unsupported_permission_decision_fails_open` + 文档三方吻合);PermissionRequest 可 deny 或不裁决→原生审批;官方明言 PreToolUse 是 guardrail 非完整边界;全局 hooks.json 确切路径与事件命名大小写未实测(二进制迹象 kebab-case),列为 M1 冒烟。
- SKILL.md 双端互通:本机 14 个 Claude 格式 skill 经 symlink 被 Codex 正常加载。

**bd(beads)**:
- 0.62.0 手解 exe(C:\env,PATH 首位)与 npm `@beads/bd` 1.0.2 shim 双安装并存;上游已迁 gastownhall/beads,最新 1.1.0;自带 `bd upgrade status/review/ack`;**`bd gate` 子命令存在**(`bd --help` 实测:"Manage async coordination gates");bd init 依赖 Dolt(本机已装)。

**其他**:
- taste-skill 本机未安装(全盘无踪影);来源坐标存于旧码 DEFAULT_ADAPTERS(Leonxlnx/taste-skill)。
- gemini CLI 0.41.2 已装,有 `gemini skills list/enable/disable/install/link/uninstall` 子命令。
- 官方文档域:`developers.openai.com/codex/*` = `learn.chatgpt.com/docs/*`(同一 Vercel 部署);本机 DNS 污染致两域直连失败。
