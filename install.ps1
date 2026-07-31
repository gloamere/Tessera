[CmdletBinding()]
param(
    [string]$Source = 'gloamere/codex-plugins',
    [string]$Ref = 'v4.0.0',
    [ValidateSet('workflows', 'maintainer', 'complete')]
    [string]$Profile = 'workflows',
    [switch]$All
)

$ErrorActionPreference = 'Stop'

# The default is the tagged Git marketplace. -Source also accepts a local
# marketplace path or another HTTPS Git host without changing the plugin IDs.
$sourceWasExplicit = $PSBoundParameters.ContainsKey('Source')
$releaseManifestPath = Join-Path $PSScriptRoot 'release-manifest.json'
if (-not (Test-Path -LiteralPath $releaseManifestPath -PathType Leaf)) {
    throw 'release-manifest.json was not found beside install.ps1. Run the installer from a complete repository checkout.'
}
try {
    $releaseState = Get-Content -LiteralPath $releaseManifestPath -Raw |
        ConvertFrom-Json
    $releaseStatus = $releaseState.distribution.releaseStatus
}
catch {
    throw "Could not read release state from ${releaseManifestPath}: $($_.Exception.Message)"
}
$sourceIsLocal = Test-Path -LiteralPath $Source -PathType Container
$candidateRemoteSource = (
    $releaseStatus -ne 'published' -and
    (-not $sourceWasExplicit -or -not $sourceIsLocal)
)

$codex = Get-Command codex.cmd -ErrorAction SilentlyContinue
if (-not $codex) {
    $codex = Get-Command codex -ErrorAction SilentlyContinue
}
if (-not $codex) {
    throw 'Codex CLI was not found. Install and sign in to Codex before installing Gloamere.'
}

function Invoke-Codex {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )

    & $codex.Source @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Codex command failed with exit code ${LASTEXITCODE}: codex $($Arguments -join ' ')"
    }
}

function Get-PluginCatalogJson {
    $output = & $codex.Source plugin list --json
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to inspect installed Codex plugins (exit code ${LASTEXITCODE})."
    }
    return ($output -join [Environment]::NewLine)
}

# v3 and v4 use different marketplace identities. Coexisting installs can
# expose duplicate skills, so migration remains an explicit user action.
$beforeInstall = Get-PluginCatalogJson
$legacySelectors = @()
try {
    $catalog = $beforeInstall | ConvertFrom-Json
    $legacySelectors = @(
        $catalog.installed |
            Where-Object { $_.pluginId -like '*@tessera' } |
            ForEach-Object { $_.pluginId } |
            Sort-Object -Unique
    )
}
catch {
    $legacySelectors = @(
        [regex]::Matches(
            $beforeInstall,
            '"pluginId"\s*:\s*"([^"]+@tessera)"'
        ) |
            ForEach-Object { $_.Groups[1].Value } |
            Sort-Object -Unique
    )
}
if ($legacySelectors.Count -gt 0) {
    Write-Warning (
        "Legacy Tessera plugins detected: $($legacySelectors -join ', '). " +
        'No installation changes were made.'
    )
    Write-Host 'Run these migration steps manually:'
    foreach ($selector in $legacySelectors) {
        Write-Host "  1. codex plugin remove $selector"
    }
    Write-Host '  2. codex plugin marketplace remove tessera'
    Write-Host '  3. Re-run this pinned Gloamere installer'
    throw 'Legacy plugins must be migrated first. See MIGRATION.md.'
}

# 根因：候选版默认指向尚不存在的 tag；修复要点：完成只读迁移检查后，published 前只允许显式本地 marketplace。
if ($candidateRemoteSource) {
    throw (
        "Gloamere is ${releaseStatus}; remote installation is unavailable. " +
        'Pass -Source with an existing local repository checkout.'
    )
}

$marketplaceArgs = @('plugin', 'marketplace', 'add', $Source)
if (-not $sourceIsLocal) {
    $marketplaceArgs += @('--ref', $Ref)
}
Invoke-Codex -Arguments $marketplaceArgs

if ($All) {
    $Profile = 'complete'
}
$plugins = switch ($Profile) {
    'workflows' { @('gloamere-workflows') }
    'maintainer' { @('gloamere-eval') }
    'complete' { @('gloamere-workflows', 'gloamere-eval') }
}

foreach ($plugin in $plugins) {
    Invoke-Codex -Arguments @('plugin', 'add', "$plugin@gloamere")
}

$afterInstall = Get-PluginCatalogJson
$missing = @(
    $plugins | Where-Object {
        $selector = [regex]::Escape("$($_)@gloamere")
        $afterInstall -notmatch ('"pluginId"\s*:\s*"' + $selector + '"')
    }
)
if ($missing.Count -gt 0) {
    throw "Codex did not report these plugins as installed: $($missing -join ', ')"
}

$sourceDescription = if ($sourceIsLocal) { $Source } else { "${Source}@${Ref}" }
Write-Host "Gloamere ${Profile} profile installed from marketplace ${sourceDescription}: $($plugins -join ', ')"
Write-Host 'Start a new Codex task to load the installed skills.'
