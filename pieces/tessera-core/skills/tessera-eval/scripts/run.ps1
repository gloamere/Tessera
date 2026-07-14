param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RunnerArgs
)

$ErrorActionPreference = 'Stop'
$runner = Join-Path $PSScriptRoot 'run_routing_eval.py'

$candidates = @(
    @{ Name = 'python3'; Prefix = @() },
    @{ Name = 'py'; Prefix = @('-3') },
    @{ Name = 'python'; Prefix = @() }
)

foreach ($candidate in $candidates) {
    $command = Get-Command $candidate.Name -ErrorAction SilentlyContinue
    if (-not $command) {
        continue
    }

    $prefix = $candidate.Prefix
    $version = & $command.Source @prefix --version 2>&1
    if ($LASTEXITCODE -eq 0 -and "$version" -match '^Python 3\.') {
        & $command.Source @prefix $runner @RunnerArgs
        exit $LASTEXITCODE
    }
}

Write-Error 'tessera-eval requires Python 3, but python3, py, and python were not found.'
exit 127
