<#
.SYNOPSIS
  构建 tessera 门二进制。默认只构建当前平台并放入 pieces/tessera-core/bin/;
  -All 交叉编译全平台到 dist/ 并生成 checksums(M3 release 用)。
.NOTES
  零 CGO,纯 Go 交叉编译。需要 Go(见 machine-go-toolchain memory:本机在 C:\Go)。
#>
param(
  [switch]$All
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$pkg = './cmd/tessera'

# 定位 go(优先 PATH,回退本机手装位置)
$go = (Get-Command go -ErrorAction SilentlyContinue).Source
if (-not $go -and (Test-Path 'C:\Go\bin\go.exe')) { $go = 'C:\Go\bin\go.exe' }
if (-not $go) { throw 'go 未找到:装 Go 或把 C:\Go\bin 加入 PATH' }
$env:GOTOOLCHAIN = 'local'

Push-Location $repo
try {
  if (-not $All) {
    # 当前平台 → piece 的 bin/(供本机 hook 直接调用)
    $bin = Join-Path $repo 'pieces/tessera-core/bin'
    New-Item -ItemType Directory -Force -Path $bin | Out-Null
    $name = if ($IsWindows -or $env:OS -eq 'Windows_NT') { 'tessera.exe' } else { 'tessera' }
    & $go build -o (Join-Path $bin $name) $pkg
    Write-Host "built $name -> $bin"
    return
  }

  # 全平台交叉编译 → dist/ + checksums.txt
  $dist = Join-Path $repo 'dist'
  New-Item -ItemType Directory -Force -Path $dist | Out-Null
  $targets = @(
    @{os='windows'; arch='amd64'; ext='.exe'},
    @{os='windows'; arch='arm64'; ext='.exe'},
    @{os='darwin';  arch='amd64'; ext=''},
    @{os='darwin';  arch='arm64'; ext=''},
    @{os='linux';   arch='amd64'; ext=''},
    @{os='linux';   arch='arm64'; ext=''}
  )
  $lines = @()
  foreach ($t in $targets) {
    $out = Join-Path $dist ("tessera-{0}-{1}{2}" -f $t.os, $t.arch, $t.ext)
    $env:GOOS = $t.os; $env:GOARCH = $t.arch
    & $go build -o $out $pkg
    $hash = (Get-FileHash $out -Algorithm SHA256).Hash.ToLower()
    $lines += "$hash  $(Split-Path -Leaf $out)"
    Write-Host ("built {0}/{1}" -f $t.os, $t.arch)
  }
  Remove-Item Env:GOOS, Env:GOARCH -ErrorAction SilentlyContinue
  $lines | Set-Content -Path (Join-Path $dist 'checksums.txt') -Encoding utf8
  Write-Host "checksums -> $dist/checksums.txt"
}
finally {
  Pop-Location
}
