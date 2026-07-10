# MarkItDown 资料入口适配器

MarkItDown 将 PDF、Word、PowerPoint、Excel、图片 OCR、音频和网页等资料转换为适合 LLM 阅读的 Markdown。它是“资料入口”，不是项目事实源，也不是高保真排版或 UI 还原工具。

## 启用与授权

`workflow-os init` 和 `workflow-os adapter doctor` 会检测 `markitdown` 是否在 PATH。若缺失，Codex 必须先说明：安装需要 Python 3.10+、计划启用的格式依赖、来源 `microsoft/markitdown`，并获得负责人明确授权；未经授权不得运行 `pip install` 或下载任何工具。

获得授权后可运行 `workflow-os adapter install markitdown --authorized`。实际包和格式范围由 `.workflow/adapters.yaml` 决定；先安装 PDF、Word、PowerPoint、Excel 支持，不会隐式启用 OCR、音频或 Azure 服务。

## 导入规则

原始文件继续保留在其原位置或由负责人另行归档。转换得到的 Markdown 应位于 `docs/sources/`，并记录原始路径、SHA-256、导入时间、转换器版本与关联工作包/研究。它只能作为 Evidence Card、brief 或结论的可追溯输入，不能自动成为已确认结论。

负责人授权并安装后，使用：`workflow-os ingest <local-file> --research <research-id>` 或 `--work-item <work-id>`。该命令只读取本地文件、调用本地 `markitdown`，并生成派生 Markdown；不会联网下载内容。

只处理本地、负责人已授权的文件。不要将不可信 URL 直接交给转换器；MarkItDown 以当前进程权限执行 I/O，应使用最小必要权限与最窄的本地文件调用范围。
