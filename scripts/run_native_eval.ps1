param(
    [Parameter(Mandatory = $true)]
    [string]$Suite,
    [Parameter(Mandatory = $true)]
    [string]$TargetLock,
    [ValidateSet('pr', 'release', 'exhaustive')]
    [string]$Mode = 'exhaustive',
    [string]$Policy,
    [ValidateRange(1, 100000)]
    [Nullable[int]]$MaxCalls,
    [string]$RotationKey,
    [string]$Journal,
    [ValidatePattern('^[1-9][0-9]*/[1-9][0-9]*$')]
    [string]$Shard,
    [switch]$Resume,
    [switch]$Finalize,
    [switch]$DryRun,
    [ValidateRange(1, 10)]
    [Nullable[int]]$Repeat,
    [ValidateRange(1, 86400)]
    [int]$Timeout = 45,
    [string]$Output,
    [string]$Model,
    [string]$Workspace,
    [string[]]$Case,
    [string[]]$ChangedSkill,
    [switch]$IncludePrompts,
    [string]$Catalog,
    [string]$AdapterExecutable,
    [string[]]$AdapterArg
)

$ErrorActionPreference = 'Stop'
$runner = Join-Path $PSScriptRoot '..\plugins\gloamere-eval\skills\gloamere-skill-eval\scripts\run.ps1'
$runnerArgs = @(
    'native',
    '--suite', $Suite,
    '--target-lock', $TargetLock,
    '--mode', $Mode,
    '--timeout', "$Timeout"
)

if ($Policy) {
    $runnerArgs += @('--policy', $Policy)
}
if ($null -ne $MaxCalls) {
    $runnerArgs += @('--max-calls', "$MaxCalls")
}
if ($RotationKey) {
    $runnerArgs += @('--rotation-key', $RotationKey)
}
if ($Journal) {
    $runnerArgs += @('--journal', $Journal)
}
if ($Shard) {
    $runnerArgs += @('--shard', $Shard)
}
if ($Resume) {
    $runnerArgs += '--resume'
}
if ($Finalize) {
    $runnerArgs += '--finalize'
}
if ($DryRun) {
    $runnerArgs += '--dry-run'
}
if ($null -ne $Repeat) {
    $runnerArgs += @('--repeat', "$Repeat")
}
foreach ($caseId in $Case) {
    $runnerArgs += @('--case', $caseId)
}
foreach ($skillName in $ChangedSkill) {
    $runnerArgs += @('--changed-skill', $skillName)
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
if ($Catalog) {
    $runnerArgs += @('--catalog', $Catalog)
}
if ($AdapterExecutable) {
    $runnerArgs += @('--adapter-executable', $AdapterExecutable)
}
foreach ($argument in $AdapterArg) {
    $runnerArgs += @('--adapter-arg', $argument)
}

& $runner @runnerArgs
exit $LASTEXITCODE
