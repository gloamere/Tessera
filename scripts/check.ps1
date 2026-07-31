$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python3 -ErrorAction SilentlyContinue
}
if (-not $python) {
    throw 'Python 3 was not found.'
}

function Invoke-CheckedPython {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )

    & $python.Source @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code ${LASTEXITCODE}: $($Arguments -join ' ')"
    }
}

$checkTemp = Join-Path (
    [System.IO.Path]::GetTempPath()
) ("gloamere-check-" + [guid]::NewGuid().ToString('N'))
[void](New-Item -ItemType Directory -Path $checkTemp)

try {
    $targetLock = Join-Path $checkTemp 'target-lock.json'

    Invoke-CheckedPython -Arguments @('scripts/generate_release_files.py', '--check')
    Invoke-CheckedPython -Arguments @('scripts/validate_marketplace.py')
    Invoke-CheckedPython -Arguments @('scripts/validate_release_evidence.py')
    Invoke-CheckedPython -Arguments @('scripts/validate_quality_evidence.py')
    Invoke-CheckedPython -Arguments @(
        '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py'
    )
    # Root cause: a stale user-global plugin can contaminate repository checks.
    # The fixed empty catalog checks local files; real eval still observes Codex.
    $inspectArguments = @(
        'scripts/run_routing_eval.py',
        'inspect',
        '--catalog', 'tests/fixtures/empty_plugin_catalog.json',
        '--plugin-root', 'plugins/gloamere-eval',
        '--plugin-root', 'plugins/gloamere-workflows',
        '--marketplace', 'gloamere',
        '--output', $targetLock
    )
    & $python.Source @inspectArguments | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Python inspect failed with exit code ${LASTEXITCODE}."
    }
    Invoke-CheckedPython -Arguments @(
        'scripts/run_routing_eval.py',
        'lint',
        '--target-lock', $targetLock
    )
}
finally {
    if (Test-Path -LiteralPath $checkTemp) {
        Remove-Item -LiteralPath $checkTemp -Recurse -Force
    }
}

Write-Host 'All Gloamere checks passed.'
