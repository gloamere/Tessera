# Tessera 部署手册

Tessera 只分发四个 Skill：核心 `tessera-eval`，以及可选的 `taste`、`planner`、`knowledge-base`。插件发现、安装、启停、刷新和卸载全部使用 Claude/Codex 原生功能。

## Codex

### 一键安装

```powershell
irm https://raw.githubusercontent.com/gloamere/Tessera/main/install.ps1 | iex
```

安装全部四个插件：

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/gloamere/Tessera/main/install.ps1))) -All
```

```bash
# macOS / Linux，默认只安装 core
curl -fsSL https://raw.githubusercontent.com/gloamere/Tessera/main/install.sh | sh

# 安装全部四个插件
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

`tessera-core` 的安装包内含 eval 运行器、15 个核心案例、25 个个人案例和两个输出 schema。Skill 从自身安装路径启动，不查找 Tessera 仓库，报告写入当前项目。插件安装只依赖 Codex/Claude；实际运行 eval 还需要系统可调用 Python 3，但不需要任何第三方 Python 包。

## Smoke test

新会话中验证：

1. 普通代码、架构、高风险确认和插件生命周期请求不加载任何 Tessera 控制层 Skill。
2. “评审这个页面的视觉层级和配色”加载 `taste`。
3. “把会议记录整理成双链知识笔记”加载 `knowledge-base`。
4. “给活动设计三个可拍板方向”加载 `planner`。
5. “运行 tessera eval”加载 `tessera-eval`。
6. 同时包含两个明确专业意图时，宿主可分别加载对应专业 Skill，不需要 router。

## 维护者验证

```powershell
python scripts/validate_marketplace.py
python -m unittest discover -s tests -p 'test_*.py'
python scripts/run_routing_eval.py --host codex --mode policy --dry-run
python scripts/run_routing_eval.py --host codex --mode native --cases pieces/tessera-core/skills/tessera-eval/references/personal-routing-cases.json --dry-run
codex plugin marketplace add ./
codex plugin add tessera-core@tessera
codex plugin list --json
```

真实行为验收使用 native 模式。只有宿主事件或可信 transcript 才能成为 `verified`；policy、CI fixture、模型自报和 dry-run 都不能替代真实宿主证据。

`scripts/validate_marketplace.py` 只检查 Tessera 自己的双宿主发布物：marketplace 插件集合、manifest name/version、piece 元数据、Skill frontmatter、精简能力集合和 eval 案例/schema。运行时安装与启用状态由宿主原生界面负责。

## 升级与清理

从 0.4 升级到 0.5 后，旧控制层 Skill 不再发布；0.6 起 eval 安装包自包含运行器、案例和 schema。重新添加 `tessera-core` 并新开会话即可。旧 `~/.tessera` usage 数据不会被迁移或自动删除；需要保留时先备份，不需要时由用户自行清理。
