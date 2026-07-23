param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RunnerArgs
)

$ErrorActionPreference = 'Stop'
$runner = Join-Path $PSScriptRoot 'run_routing_eval.py'
$versionProbe = 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'

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
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & $command.Source @prefix -c $versionProbe *> $null
    $probeExitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousErrorActionPreference
    if ($probeExitCode -ne 0) {
        continue
    }

    # Windows PowerShell 5 promotes native stderr to script errors. Preserve
    # stderr for the caller and judge the runner only by its process exit code.
    $ErrorActionPreference = 'Continue'
    & $command.Source @prefix $runner @RunnerArgs
    exit $LASTEXITCODE
}

Write-Error 'gloamere-skill-eval requires Python 3.10 or newer; no compatible python3, py, or python command was found.'
exit 127
