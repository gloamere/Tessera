param(
    [string]$Source = 'gloamere/Tessera',
    [string]$Ref = 'main',
    [switch]$All
)

$ErrorActionPreference = 'Stop'

$codex = Get-Command codex.cmd -ErrorAction SilentlyContinue
if (-not $codex) {
    $codex = Get-Command codex -ErrorAction SilentlyContinue
}
if (-not $codex) {
    throw 'Codex CLI was not found. Install and sign in to Codex before installing Tessera.'
}

$marketplaceArgs = @('plugin', 'marketplace', 'add', $Source)
if (-not (Test-Path -LiteralPath $Source) -and $Ref) {
    $marketplaceArgs += @('--ref', $Ref)
}
& $codex.Source @marketplaceArgs
if ($LASTEXITCODE -ne 0) {
    throw "Failed to add Tessera marketplace from $Source."
}

$plugins = @('tessera-core')
if ($All) {
    $plugins += @('taste', 'frontend-design', 'knowledge-base', 'finance-ops', 'growth-ops', 'product-planning', 'business-ops')
}
foreach ($plugin in $plugins) {
    & $codex.Source plugin add "$plugin@tessera"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install $plugin@tessera."
    }
}

$installed = & $codex.Source plugin list --json | ConvertFrom-Json
$missing = @(
    $plugins | Where-Object {
        $selector = "$_@tessera"
        -not ($installed.installed | Where-Object { $_.pluginId -eq $selector -and $_.installed })
    }
)
if ($missing.Count -gt 0) {
    throw "Codex did not report these plugins as installed: $($missing -join ', ')"
}

Write-Host "Tessera installed: $($plugins -join ', ')"
Write-Host 'Start a new Codex task to load the installed skills.'
