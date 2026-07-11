[CmdletBinding()]
param(
  [string]$InstallRoot = (Join-Path $HOME 'workflow-os'),
  [string]$Repository = 'https://github.com/gloamere/workflow-os.git',
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
Require-Command node

$nodeMajor = [int]((& node --version).Trim().TrimStart('v').Split('.')[0])
if ($nodeMajor -lt 24) {
  throw "workflow-os requires Node.js 24 or newer; found $((& node --version).Trim())."
}

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
  Write-Host "workflow-os installed at $InstallRoot ($resolved)"
  if (-not $SkipTests) {
    if (Get-Command npm.cmd -ErrorAction SilentlyContinue) { npm.cmd test }
    else { npm test }
  }
  if ($InstallCodexPlugin) {
    Require-Command codex
    codex plugin marketplace add $InstallRoot
    codex plugin add wfos-core@workflow-os
    Write-Host 'Codex plugin installed. Start a new Codex session and review the hook trust prompt.'
  } else {
    Write-Host 'Plugin not installed. Re-run with -InstallCodexPlugin after reviewing this checkout.'
  }
  Write-Host "New project: node `"$InstallRoot\scripts\init-project.mjs`" --target <project-path> --name `"Project Name`""
} finally {
  Pop-Location
}
