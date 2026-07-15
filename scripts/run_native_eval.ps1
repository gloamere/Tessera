param(
    [ValidateRange(1, 20)]
    [int]$Repeat = 3,
    [string]$Output = 'eval-results/codex-native.json'
)

$ErrorActionPreference = 'Stop'

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python3 -ErrorAction SilentlyContinue
}
if (-not $python) {
    throw 'Python 3 was not found.'
}
if (-not (Get-Command codex -ErrorAction SilentlyContinue) -and -not (Get-Command codex.cmd -ErrorAction SilentlyContinue)) {
    throw 'Codex CLI was not found. Install and sign in to Codex before running native eval.'
}

& $python.Source scripts/run_routing_eval.py `
    --host codex `
    --mode native `
    --cases pieces/tessera-core/skills/tessera-eval/references/personal-routing-cases.json `
    --repeat $Repeat `
    --suggest-tuning `
    --output $Output
if ($LASTEXITCODE -ne 0) {
    throw "Native eval failed with exit code $LASTEXITCODE."
}
