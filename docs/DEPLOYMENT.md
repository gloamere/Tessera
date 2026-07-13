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

## Claude Code

同一仓库也包含 `.claude-plugin/marketplace.json`。请用 Claude 自己的市集/插件命令注册和安装；不要把 Codex 命令混用到 Claude。

## 可选拼图与依赖

`tessera-core` 与当前内置拼图均无外部运行时依赖。候选后端只有在重量、收益与安装方式验证通过后才会进入拼图市集；Tessera 不静默安装第三方依赖。

## 维护者验证

每次修改插件结构或 skill 后，在仓库根目录执行：

```powershell
codex plugin marketplace add ./
codex plugin add tessera-core@tessera
codex plugin list
codex debug prompt-input
```

再用新会话完成三条自然语言验证。不要依赖缓存、未跟踪的二进制或本机 hooks 作为验收依据。
