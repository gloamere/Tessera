---
schema: wfos/decision@1
id: codex-cli-access
status: approved
created: 2026-07-11
approved: 2026-07-11
---

# Codex CLI 调用方式

## 背景
桌面版自带 codex.exe 位于 C:\Users\Administrator\AppData\Local\OpenAI\Codex\bin\07133f975a59dbd9\codex.exe,不在 PATH;bin 下哈希目录名会随桌面版更新变化。

## 选项
- **A(推荐)**:在 C:\Users\Administrator\.local\bin(已在 PATH)放 codex.cmd shim,内容动态解析 bin 下最新目录:
  `@echo off` / `for /f "delims=" %%i in ('dir /b /ad /o-d "%LOCALAPPDATA%\OpenAI\Codex\bin"') do (set "CODEX_DIR=%%i" & goto :run)` / `:run` / `"%LOCALAPPDATA%\OpenAI\Codex\bin\%CODEX_DIR%\codex.exe" %*`
- **B**:不进 PATH,文档与脚本一律写全路径(桌面版更新后手改)。

## 结论
选 **A**:在 `C:\Users\Administrator\.local\bin`(已在 PATH)放置 `codex.cmd` shim,动态解析 `bin` 下按修改时间倒序的最新哈希目录。

**执行**:已写入 `C:\Users\Administrator\.local\bin\codex.cmd`,内容与本文件「选项 A」描述一致。文件编码校验(hex dump):首字节 `0x40`('@'),无 BOM;行尾均为 `0d0a`(CRLF);纯 ASCII。

**候选目录核实**:`bin` 目录下当前有 4 个哈希子目录,按 `dir /b /ad /o-d` 排序(即按修改时间倒序,shim 逻辑取第一个)得到最新为 `07133f975a59dbd9`(LastWriteTime 2026-06-10),与决策背景中记录的路径一致。

**验证结果**:
- PowerShell `& "C:\Users\Administrator\.local\bin\codex.cmd" --version` → `codex-cli 0.138.0-alpha.7`,退出码 0。
- PowerShell 内 `cmd /c "codex --version"`(依赖 PATH 解析)→ 同样输出 `codex-cli 0.138.0-alpha.7`,退出码 0。
- 备注:通过本任务所用 Bash 工具(Git Bash/MSYS)调用 `cmd /c '...'` 时观察到异常——无论是 shim 还是裸 `codex --version`,均返回一个交互式 cmd 横幅而非命令输出。经排查确认这是 Bash 工具到 cmd.exe 的引号/调用传递问题(与 shim 本身无关),因为同一命令从原生 PowerShell 发起的 `cmd /c` 完全正常。以 PowerShell 调用结果为准,shim 工作正常。
