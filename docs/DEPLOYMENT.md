# workflow-os v2 部署手册

workflow-os 分为两步：机器安装一次，项目初始化一次。插件提供可复用能力；项目目录保存该项目的目标、决策、研究和人类规则。

## 1. 新机器：安装能力市场

```powershell
git clone https://github.com/gloamere/workflow-os.git $HOME\workflow-os
cd $HOME\workflow-os
npm.cmd test
codex plugin marketplace add .
codex plugin add wfos-core@workflow-os
```

在 Codex Desktop 中重启或新开会话，启用 `wfos-core`，并审阅其 hook 定义后明确选择是否信任。hooks 不是完整安全边界；为 GitHub 的 `main` 配置禁止 force push 的 ruleset。

Claude 的安装使用同一仓库中的 `.claude-plugin/marketplace.json`，但 Claude 和 Codex 的插件安装命令必须各自执行，不能互相替代。

## 2. 新项目：初始化项目知识库

```powershell
node $HOME\workflow-os\scripts\init-project.mjs --target D:\Projects\my-game --name "My Game"
```

脚本只创建缺失文件，并在 `AGENTS.md` 写入一个带边界标记的托管区；现有人类规则、代码和文档不会被覆盖。先用 `--dry-run` 预览。

创建后结构如下：

```text
my-game/
  AGENTS.md
  .workflow-os/project.yaml
  docs/
    PROJECT.md
    NOW.md
    INBOX.md
    decisions/
    research/
```

## 3. 每个项目的开始方式

在项目根目录打开 Codex，先读 `docs/PROJECT.md` 与 `docs/NOW.md`；需要路线选择时新增 `docs/decisions/` 下的记录，确认后再实现。研究和外部能力通过已安装的 skills 使用，安装外部 CLI 前必须获得负责人授权。

## 升级与回退

更新市场仓库后先运行 `npm.cmd test`，再在 Codex 中升级/重装插件并开新会话。若插件或 hooks 行为异常，先在 Codex 中禁用该插件；项目 Markdown 不受影响。
