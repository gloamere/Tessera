param(
    [Parameter(Mandatory = $true)]
    [string]$Suite,
    [Parameter(Mandatory = $true)]
    [string]$TargetLock,
    [ValidateRange(1, 10)]
    [Nullable[int]]$Repeat,
    [ValidateRange(1, 86400)]
    [int]$Timeout = 45,
    [string]$Output,
    [string]$Model,
    [string]$Workspace,
    [string[]]$Case,
    [switch]$IncludePrompts
)

$ErrorActionPreference = 'Stop'
$runner = Join-Path $PSScriptRoot '..\plugins\gloamere-eval\skills\gloamere-skill-eval\scripts\run.ps1'
$runnerArgs = @(
    'native',
    '--suite', $Suite,
    '--target-lock', $TargetLock,
    '--timeout', "$Timeout"
)

if ($null -ne $Repeat) {
    $runnerArgs += @('--repeat', "$Repeat")
}
foreach ($caseId in $Case) {
    $runnerArgs += @('--case', $caseId)
}
if ($Output) {
    $runnerArgs += @('--output', $Output)
}
if ($Model) {
    $runnerArgs += @('--model', $Model)
}
if ($Workspace) {
    $runnerArgs += @('--workspace', $Workspace)
}
if ($IncludePrompts) {
    $runnerArgs += '--include-prompts'
}

& $runner @runnerArgs
exit $LASTEXITCODE
