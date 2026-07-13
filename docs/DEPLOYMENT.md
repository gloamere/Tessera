# Tessera 部署手册

Tessera 是纯 skills 市集：无需 Go、Node、二进制、release 下载或 hooks。

## Codex

```powershell
git clone https://github.com/gloamere/Tessera.git
cd Tessera
codex plugin marketplace add ./
codex plugin add tessera-core@tessera
codex plugin list
```

若 `codex --version` 报 `Access is denied`，这是 Windows Store/MSIX 的命令执行别名或权限环境问题，不是 Tessera 问题。请在普通终端运行、在“应用执行别名”中启用 Codex，或使用非 Store 版 CLI；CLI 能运行后再继续。

重装或刷新本地市集时：

```powershell
codex plugin marketplace upgrade
codex plugin add tessera-core@tessera
codex plugin list
```

随后新开 Codex 会话。Codex 没有 Tessera 的 slash 命令；使用自然语言即可：

- “不知道该用哪个工具，帮我规划新项目”验证 `piece-router`。
- “查看拼图和依赖状态”或“tessera status”验证 `tessera-status`。
- “安装拼图 / setup”验证 `tessera-setup`。
- “运行 tessera eval”验证 `tessera-eval`；评测报告默认写入 `eval-results/`。
- “动态解析当前 Tessera 能力”验证 `tessera-capabilities`；结果必须区分 active、installed、available 与 unknown。

## Claude Code

同一仓库也包含 `.claude-plugin/marketplace.json`。请用 Claude 自己的市集/插件命令注册和安装；不要把 Codex 命令混用到 Claude。

## 可选拼图与依赖

`tessera-core` 与当前内置拼图均无外部运行时依赖。候选后端只有在重量、收益与安装方式验证通过后才会进入拼图市集；Tessera 不静默安装第三方依赖。

## 维护者验证

每次修改插件结构或 skill 后，在仓库根目录执行：

```powershell
python -m pip install --disable-pip-version-check --requirement requirements-dev.txt
python scripts/validate_marketplace.py
python scripts/resolve_capabilities.py --host codex --probe --format table
python scripts/run_routing_eval.py --host codex --dry-run
codex plugin marketplace add ./
codex plugin add tessera-core@tessera
codex plugin list
codex debug prompt-input
```

再分别在可用的 Codex/Claude 新会话完成自然语言 smoke test：

- “新增一个代码语义检索拼图”应先输出七维评分、原始等级、封顶与建议，不直接安装。
- “安装拼图”不得把 `not-integrated`、`unverified` 或 candidate 项列为可安装项。
- “tessera status”无法证实时必须报告 `unknown`，不得把未知写成未安装。
- “tessera doctor”应输出总状态和逐项证据，且不得修改文件或自动执行修复。
- “tessera eval”应调用固定案例并区分整套通过率、路由正确率和执行错误；CI 假宿主结果不得冒充模型实测。
- “动态解析当前能力”不得把市集存在误报成当前 active，也不得把探测失败误报成未安装。
- 已装版与市集版只差 build metadata 时应报告 `refresh-available`；预发布或缺失版本应报告 `unknown`。
- 模糊复合任务触发 router 时应有一行路由说明；明显简单任务不增加说明。
- 在没有决策目录的普通项目中做低风险方案选择，不得自动创建 `docs/decisions/`。

Claude 端使用同义提示并额外验证 `/tessera-status` 只路由到 status skill。不要依赖缓存、未跟踪的二进制或本机 hooks 作为验收依据。
