# Tessera 部署手册

Tessera 是 Claude/Codex 原生 Skills 之上的个人可靠性控制层，也是纯 skills 市集：无需 Go、Node、二进制、release 下载或 hooks。可选本地使用记录默认关闭且永不联网。

## Codex

```powershell
git clone https://github.com/gloamere/Tessera.git
cd Tessera
codex plugin marketplace add ./
codex plugin add tessera-core@tessera
codex plugin list
```

若 `codex --version` 报 `Access is denied`，这是 Windows Store/MSIX 的命令执行别名或权限环境问题，不是 Tessera 问题。请在普通终端运行、在“应用执行别名”中启用 Codex，或使用非 Store 版 CLI；CLI 能运行后再继续。

重装或刷新本地市集时直接重新添加插件；本地 marketplace 不是 Git marketplace，不运行 `marketplace upgrade`：

```powershell
codex plugin add tessera-core@tessera
codex plugin list
```

随后新开 Codex 会话。Codex 没有 Tessera 的 slash 命令；使用自然语言即可：

- 明确的 UI、方案或知识请求应由宿主直接调用 `taste`、`planner` 或 `knowledge-base`，不先经过 router。
- “不知道该用哪个工具，帮我规划新项目”、多意图或高风险请求才验证 `piece-router`。
- “查看拼图和依赖状态”或“tessera status”验证 `tessera-status`。
- “安装拼图 / setup”验证 `tessera-setup`。
- “禁用/启用/卸载拼图”验证 setup 的宿主动作矩阵；Codex 的启停必须报告 unsupported，不能退化为 remove。
- “回滚到 <明确 ref>”只验证 ref 和生成计划，不得切换当前 `main` 或自动重配 marketplace。
- “运行 tessera eval”验证 `tessera-eval`；政策分类与原生调用必须分开报告，默认写入 `eval-results/`。
- “查看当前 Tessera 能力”默认通过 status quick 视图验证；明确要求完整目录时才走兼容入口 `tessera-capabilities`。

## Claude Code

同一仓库也包含 `.claude-plugin/marketplace.json`。请用 Claude 自己的市集/插件命令注册和安装；不要把 Codex 命令混用到 Claude。

## 可选拼图与依赖

`tessera-core` 与当前内置拼图均无外部运行时依赖。候选后端只有在重量、收益与安装方式验证通过后才会进入拼图市集；Tessera 不静默安装第三方依赖。

## 维护者验证

每次修改插件结构或 skill 后，在仓库根目录执行：

```powershell
python -m pip install --disable-pip-version-check --requirement requirements-dev.txt
python scripts/validate_marketplace.py
python scripts/resolve_capabilities.py --host codex --probe --view quick --format table
python scripts/run_routing_eval.py --host codex --mode policy --dry-run
python scripts/run_routing_eval.py --host codex --mode native --cases tests/personal-routing-cases.yaml --dry-run
python -m unittest discover -s tests -p 'test_*.py'
codex plugin marketplace add ./
codex plugin add tessera-core@tessera
codex plugin list
codex debug prompt-input
```

再分别在可用的 Codex/Claude 新会话完成自然语言 smoke test：

- “新增一个代码语义检索拼图”应先输出七维评分、原始等级、封顶与建议，不直接安装。
- “安装拼图”不得把 `not-integrated`、`unverified` 或 candidate 项列为可安装项。
- “tessera status”无法证实时必须报告 `unknown`，不得把未知写成未安装。
- status 默认 quick 视图不得展示未验证候选；用户要求详细模式时才显示完整目录。
- 本地使用记录默认不创建文件；显式启用后只记录首方 skill 元数据与项目哈希，记录失败不得阻断任务。
- “tessera doctor”默认应输出总状态和逐项证据且零写入；明确 remediation 后只逐项确认 setup 白名单动作，结构/trust/回滚保持 plan-only。
- `policy` 应声明只验证路由政策；`native` 应区分 verified、declared-only、unobservable 与 conflict。CI 假宿主结果不得冒充模型实测。
- `--suggest-tuning` 只在 native 重复失败达到门槛后给出结构化建议，不得自动修改 SKILL.md。
- “动态解析当前能力”不得把市集存在误报成当前 active，也不得把探测失败误报成未安装。
- 已装版与市集版只差 build metadata 时应报告 `refresh-available`；预发布或缺失版本应报告 `unknown`。
- 模糊复合任务触发 router 时应有一行路由说明；明显简单任务不增加说明。
- 多交付物请求应输出依赖有序 recipe 和交接包；前置失败只阻断依赖链，独立步骤可继续。
- 在没有决策目录的普通项目中做低风险方案选择，不得自动创建 `docs/decisions/`。

Claude 端使用同义提示并额外验证 `/tessera-status` 只路由到 status skill。Claude CLI/适配器不可用时只做结构与 dry-run 校验，不得声称真实实测。模型自报只能标记 declared-only。不要依赖缓存、未跟踪的二进制或本机 hooks 作为验收依据。
