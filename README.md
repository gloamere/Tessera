# workflow-os

可组合、AI 友好的项目工作流工具包。它让 Markdown 保持为 Obsidian、Git 与人类协作的知识事实源；AI 或平台只是可替换的适配器，Codex 是第一个适配器。

## 运行环境

`workflow-os` 需要 Node.js 24 或更高版本。SQLite 使用 Node 的 `node:sqlite`，因此不承诺兼容 Node.js 20。

## 安装到一个项目

在目标项目根目录运行：

```powershell
node path/to/workflow-os/bin/workflow-os.mjs init --codex --obsidian
```

它只新增缺失文件，不覆盖已有内容。先用 `--dry-run` 预览：

```powershell
node path/to/workflow-os/bin/workflow-os.mjs init --codex --obsidian --dry-run
```

安装后，直接在该项目目录向 Codex 提需求即可。它应读取短小的项目上下文和相应工作包，而不是依赖整段对话历史。

## SQLite 本地索引

每个已安装项目可在 `.workflow/index.sqlite` 维护一个本地“指挥索引”。它只从 Markdown 派生，用于快速查看工作状态、待拍板项、依赖和为 agent 生成短上下文包。

- `docs/` 中的 Markdown 是唯一事实源，也是唯一需要提交到 Git 的项目知识。
- SQLite、WAL/SHM 文件与写锁均由 `.workflow/.gitignore` 忽略；删除数据库不会丢失项目知识。
- 数据流只允许 **Markdown → SQLite**。不要直接编辑数据库，也不要从数据库回写设计、策划或正文。
- 任何设备克隆项目后，都可以用 `rebuild --render-now` 从 Markdown 恢复索引。

## 澄清与拍板

总指挥先读取现有代码、项目文档与 brief；可自行查明的事实不会反问你。只有范围、目标、验收、上线风险或实现方向仍存在高影响歧义时，才把工作包设为 `waiting_clarification` 并提出一个问题（最多三个），同时写明推荐默认值。

澄清用于消除“你说的到底是什么”；拍板用于在多个已整理方案中由你选择方向。两者分别记录在工作包的 `## 待澄清` / `## 待负责人拍板`。

## UI Taste 与适配器

安装会创建 `docs/ui/TASTE.md` 与 `.workflow/extensions/ui/`。`TASTE.md` 只沉淀你已经确认的审美信号、排除项和证据；参考项目或一次生成图不能自动成为项目规则。

首个适配器是 [taste-skill](https://github.com/Leonxlnx/taste-skill)：用于设计解读、反套路审查和截图复盘。对于私服游戏客户端，它受 `game-client` profile 约束，不默认套用网页 landing page、GSAP 或低信息密度的风格。

## 日常命令

以下命令都在已安装工作流的项目根目录运行：

```powershell
# 新建 Markdown 工作包或待拍板决策
workflow-os work create "商城 UI 改造"
workflow-os decision create "确认商城视觉方向" --work-item <work-id>

# 从 Markdown 刷新本地索引；同时更新 NOW.md 的自动总览区
workflow-os sync --render-now

# 查看当前推进、卡点、待拍板与下一步
# status / context / validate 是只读命令：不持有写锁，可被多个 agent 并发调用。
# 它们会尽力刷新索引；若写锁已被占用，则直接读取现有索引而不是失败。
workflow-os status
workflow-os status --json
workflow-os status --no-sync   # 纯读，完全不写盘

# 为一个工作包输出最小上下文包
workflow-os context <work-id>
workflow-os context <work-id> --json

# 校验 Markdown 元数据和引用；或从零重建本地索引
workflow-os validate
workflow-os rebuild --render-now

# 检查并安全升级工作流模板；本地改过的文件不会被覆盖
workflow-os upgrade --plan
workflow-os upgrade --apply

# 每个子 agent 回合后记录结果；返回 stop 时不得继续重试
workflow-os guard <work-id> --outcome progress
workflow-os guard <work-id> --outcome no-progress --error "同一失败特征"
```

命令的帮助文本是当前版本参数的最终依据：`workflow-os <command> --help`。

## 总指挥与子 agent

总指挥负责状态收敛：开始时执行 `status` / `context`，结束时在已汇总子任务、完成负责人拍板后独占执行 `sync --render-now`。它也负责在必要时运行 `validate` 或 `rebuild`。

子 agent 只读取自己的短简报，并只修改被分配、互不冲突的 Markdown 产物；它们不创建、修改或同步 `.workflow/index.sqlite`，也不编辑 `docs/NOW.md` 的自动总览区。这样可避免并发写索引或多个 agent 相互覆盖状态。

## 长期维护与 token 守卫

`init --codex` 会创建或无损注入 `AGENTS.md` 的 `workflow-os` 托管块。之后升级只替换这个标记区，不会覆盖项目原有规则。

`.workflow/manifest.yaml` 保存已安装的模板哈希与适配器来源。`upgrade --plan` 只显示安全更新与本地覆盖；`upgrade --apply` 只更新未被本地修改的托管文件。它会把外部 skill（例如 Taste）标为 `external_check_required`，由总指挥调研更新内容后再向你提升级方案；项目升级命令绝不静默覆盖个人全局 skill。

`adapter install` 只会安装代码内白名单里写死的包名。`.workflow/adapters.yaml` 是项目内文件，可以指向白名单里的条目，但不能扩充它：`--authorized` 授权的是「安装某个具名适配器」，不是「用该文件当时的任意字符串执行 pip」。包名不符时安装被拒绝，且不会调用 pip。

`.workflow/agent-budget.yaml` 和 `guard` 限制工作轮次、并发、连续无进展与重复错误。它避免循环和上下文膨胀，但不声称能读取 Codex Desktop 的精确计费 token；精确平台用量属于账户或工作区层面的数据。

## 核心原则

- 工作包是最小交付单位；一个项目不必走完整流程。
- 设计、策划与功能方向必须由项目负责人拍板，拍板前只记录为待决策。
- 研究、盘点、素材整理可以并行；同一文件或有前置依赖的实现不得并行修改。
- `docs/` 是 Obsidian 可直接打开的项目知识库；`.workflow/` 保存可迁移规则、模板和可重建的本地索引。

## 目录概览

```text
.workflow/             # 规则、模板、忽略规则和本地 SQLite 索引
docs/
  PROJECT.md           # 项目目标、约束和入口
  NOW.md               # 当前状态；自动区由总指挥刷新
  INBOX.md             # 未整理灵感、反馈和临时问题
  work/                # 一个工作包一份 Markdown
  decisions/           # 待拍板与已确认的决策
  briefs/              # 可复用的 UI、活动和功能简报
```
