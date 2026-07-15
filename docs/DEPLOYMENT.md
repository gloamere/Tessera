# Tessera 部署手册

Tessera 分发八个独立 Skill：核心 `tessera-eval`，以及七个可选专业插件 `frontend-design`、`taste`、`knowledge-base`、`finance-ops`、`growth-ops`、`product-planning`、`business-ops`。插件发现、安装、启停、刷新和卸载全部使用 Claude/Codex 原生功能。

## Codex

### 一键安装

```powershell
irm https://raw.githubusercontent.com/gloamere/Tessera/main/install.ps1 | iex
```

安装全部八个插件：

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/gloamere/Tessera/main/install.ps1))) -All
```

```bash
# macOS / Linux，默认只安装 core
curl -fsSL https://raw.githubusercontent.com/gloamere/Tessera/main/install.sh | sh

# 安装全部八个插件
curl -fsSL https://raw.githubusercontent.com/gloamere/Tessera/main/install.sh | sh -s -- --all
```

手动等价命令：

```powershell
codex plugin marketplace add gloamere/Tessera --ref main
codex plugin add tessera-core@tessera
codex plugin list --json
```

安装器不会修改 `config.toml`、下载额外运行时或执行 pip。修改插件后刷新 marketplace 并重新执行 `codex plugin add <name>@tessera`，然后新开任务。卸载使用 `codex plugin remove <name>@tessera`。

若 `codex --version` 报 `Access is denied`，先修复 Windows 的命令执行别名或 CLI 安装；这不是 Tessera 生命周期层能够处理的问题。

## Claude Code

```powershell
claude plugin marketplace add gloamere/Tessera
claude plugin install tessera-core@tessera --scope user
claude plugin list --json
```

专业插件使用相同的 `claude plugin install <name>@tessera --scope user` 形式。安装、更新、启用或禁用后在交互会话运行 `/reload-plugins`。浏览、启停和卸载使用 `/plugin` 或对应 `claude plugin` 命令。

Claude CLI 在当前验证机器不可用时，只验证双宿主发布物结构和 eval dry-run；不得声称完成 Claude 原生调用实测。

## 自包含边界

`tessera-core` 的安装包内含 eval 运行器、23 个核心案例、25 个个人案例和两个输出 schema。`frontend-design` 自包含 35 个本地 CSV 数据表、标准库搜索/设计系统脚本及 PowerShell/POSIX 包装器。四个业务插件只有 Skill、manifest 与 piece 元数据，没有外部运行时依赖。Skill 从自身安装路径启动，不查找 Tessera 仓库，报告写入当前项目。插件安装只依赖 Codex/Claude；实际运行 eval 或前端设计搜索还需要系统可调用 Python 3，但不需要第三方 Python 包。POSIX 包装器支持 macOS 与 Linux。

## Smoke test

新会话中验证：

1. 普通代码、架构、高风险确认和插件生命周期请求不加载任何 Tessera 控制层 Skill。
2. “为这个 Next.js dashboard 建立设计系统和响应式实现约束”加载 `frontend-design`。
3. “评审这个已完成页面的视觉层级和配色”加载 `taste`。
4. 同时要求从零设计与最终审美复核时，先运行 `frontend-design`，实现或方案成形后再运行 `taste`。
5. “把会议记录整理成双链知识笔记”加载 `knowledge-base`。
6. “形成团队账号 PRD，并比较方案、指标和风险”加载 `product-planning`。
7. “建立召回活动的目标、渠道、埋点和复盘”加载 `growth-ops`。
8. “整理员工离职 SOP、RACI 和升级路径”加载 `business-ops`。
9. “做银行流水与现金总账对账，不要过账”加载 `finance-ops`；投资下单、付款和申报不加载它。
10. “运行 tessera eval”加载 `tessera-eval`。
11. 前端用户研究仍由宿主处理；`frontend-design` 的数据库候选不能冒充用户证据。

## 维护者验证

```powershell
python -m pip install -r requirements-dev.txt
./scripts/check.ps1
codex plugin marketplace add ./
codex plugin add tessera-core@tessera
codex plugin list --json
./scripts/run_native_eval.ps1
```

macOS / Linux 对应使用 `sh scripts/check.sh` 与 `sh scripts/run_native_eval.sh`。

真实行为验收使用 native 模式。只有宿主事件或可信 transcript 才能成为 `verified`；policy、CI fixture、模型自报和 dry-run 都不能替代真实宿主证据。

`scripts/validate_marketplace.py` 只检查 Tessera 自己的双宿主发布物：marketplace 插件集合、manifest name/version、piece 元数据、Skill frontmatter、精简能力集合和 eval 案例/schema。运行时安装与启用状态由宿主原生界面负责。

分发版本以根目录 `VERSION` 为事实来源，并必须与 Claude marketplace 的 `metadata.version` 一致。创建同名 `v<version>` tag 后，GitHub Actions 会重新执行完整验证并生成 Release；版本不一致时发布失败。

## 升级与清理

从 0.4 升级到 0.5 后，旧控制层 Skill 不再发布；0.6 起 eval 安装包自包含运行器、案例和 schema；0.7 起不再发布旧 `planner`；3.2 起策划与运营按四个业务域独立安装。重新添加目标插件并新开会话即可；已安装的 `planner@tessera` 仍需使用宿主原生插件管理器卸载。旧 `~/.tessera` usage 数据不会被迁移或自动删除；需要保留时先备份，不需要时由用户自行清理。
