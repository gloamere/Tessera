<#
  Tessera 新机引导(Windows)。macOS/Linux 用 scripts/bootstrap-machine.sh。
  薄壳:检测前置 → clone 固定 tag → 构建二进制 → 跑 tessera setup(dry-run)。
  重活在 Go 的 `tessera setup` 里(跨平台)。
#>
[CmdletBinding()]
param(
  [string]$InstallRoot = (Join-Path $HOME 'tessera'),
  [string]$Repository = 'https://github.com/gloamere/Tessera.git',
  [string]$Ref = 'v2.0.0-beta.1',
  [switch]$InstallCodexPlugin,
  [switch]$SkipTests
)

$ErrorActionPreference = 'Stop'

function Require-Command([string]$Name) {
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "Missing required command: $Name"
  }
}

Require-Command git
Require-Command go

if (Test-Path -LiteralPath $InstallRoot) {
  $entries = @(Get-ChildItem -Force -LiteralPath $InstallRoot)
  if ($entries.Count -gt 0) {
    throw "InstallRoot already exists and is not empty: $InstallRoot. Refusing to overwrite it."
  }
}

$parent = Split-Path -Parent $InstallRoot
New-Item -ItemType Directory -Path $parent -Force | Out-Null
git clone --branch $Ref --depth 1 --single-branch $Repository $InstallRoot

Push-Location $InstallRoot
try {
  $resolved = (git rev-parse --verify HEAD).Trim()
  Write-Host "Tessera installed at $InstallRoot ($resolved)"

  # 构建当前平台二进制(零依赖、离线可编)
  $env:GOTOOLCHAIN = 'local'
  go build -o 'pieces/tessera-core/bin/tessera.exe' ./cmd/tessera
  Write-Host 'built tessera -> pieces/tessera-core/bin/tessera.exe'

  if (-not $SkipTests) { go test ./... }

  # 展示安装计划(dry-run,不注册)
  $codexArg = @()
  if ($InstallCodexPlugin) { $codexArg = @('--codex') }
  & 'pieces/tessera-core/bin/tessera.exe' setup --root . @codexArg

  Write-Host ''
  Write-Host '下一步:'
  Write-Host '  审阅上面的计划后,注册市集:'
  Write-Host "    & `"$InstallRoot\pieces\tessera-core\bin\tessera.exe`" setup --root `"$InstallRoot`" --register $($codexArg -join ' ')"
  Write-Host '  新建项目:'
  Write-Host "    & `"$InstallRoot\pieces\tessera-core\bin\tessera.exe`" init --target <project-path> --name `"Project Name`""
} finally {
  Pop-Location
}
