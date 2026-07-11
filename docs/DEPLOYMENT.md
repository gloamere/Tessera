# workflow-os v2 部署手册

workflow-os 分为两步：机器安装一次，项目初始化一次。插件提供可复用能力；项目目录保存该项目的目标、决策、研究和人类规则。

## 1. 新机器：安装能力市场

推荐使用固定版本的 bootstrap。它不会覆盖现有目录，默认 clone、构建门二进制、运行测试并跑 `tessera setup`（dry-run）展示六阶段计划；注册市场需你审阅信任复核后手动执行 `--register`。需要 Git 与 Go。

```powershell
$script = Join-Path $env:TEMP 'workflow-os-bootstrap.ps1'
Invoke-WebRequest https://raw.githubusercontent.com/gloamere/workflow-os/v2.0.0-beta.1/scripts/bootstrap-machine.ps1 -OutFile $script
powershell -ExecutionPolicy Bypass -File $script -InstallCodexPlugin
```

不要使用 `Invoke-Expression` 或把远程内容直接 pipe 到 shell。先下载再执行，才能在执行前审阅脚本；`-Ref` 可用于固定其他已发布 tag。

手动方式如下：

```powershell
git clone --branch v2.0.0-beta.1 --depth 1 https://github.com/gloamere/workflow-os.git $HOME\workflow-os
cd $HOME\workflow-os
go build -o pieces\wfos-core\bin\tessera.exe .\cmd\tessera
go test ./...
& .\pieces\wfos-core\bin\tessera.exe setup --root . --codex            # 审阅六阶段计划与信任复核
& .\pieces\wfos-core\bin\tessera.exe setup --root . --register --codex # 审阅无误后注册市场
codex plugin add wfos-core@workflow-os
```

在 Codex Desktop 中重启或新开会话，启用 `wfos-core`，并审阅其 hook 定义后明确选择是否信任。hooks 不是完整安全边界；为 GitHub 的 `main` 配置禁止 force push 的 ruleset。

Claude 的安装使用同一仓库中的 `.claude-plugin/marketplace.json`，但 Claude 和 Codex 的插件安装命令必须各自执行，不能互相替代。

## 2. 新项目：初始化项目知识库

```powershell
& $HOME\workflow-os\pieces\wfos-core\bin\tessera.exe init --target D:\Projects\my-game --name "My Game"
```

`tessera init` 只创建缺失文件，并在 `AGENTS.md` 写入一个带边界标记的托管区；现有人类规则、代码和文档不会被覆盖。先用 `--dry-run` 预览。

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

更新时下载新的已发布 tag 到新目录并先运行测试，再在 Codex 中升级/重装插件并开新会话。若插件或 hooks 行为异常，先在 Codex 中禁用该插件；项目 Markdown 不受影响。保留旧 checkout 即可回退。
