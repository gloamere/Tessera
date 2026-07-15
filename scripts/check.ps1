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

Invoke-CheckedPython -Arguments @('scripts/validate_marketplace.py')
Invoke-CheckedPython -Arguments @('-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py')
Invoke-CheckedPython -Arguments @(
    'scripts/run_routing_eval.py',
    '--host', 'claude',
    '--case', 'direct-small-edit',
    '--case', 'multi-intent',
    '--case', 'evaluate-routing',
    '--case', 'frontend-design-system',
    '--case', 'finance-reconciliation',
    '--case', 'growth-campaign-loop',
    '--case', 'product-planning-prd',
    '--case', 'business-ops-runbook',
    '--adapter-executable', $python.Source,
    '--adapter-arg', 'tests/fixtures/fake_eval_host.py',
    '--output', 'eval-results/ci-routing.json'
)
Invoke-CheckedPython -Arguments @(
    'scripts/run_routing_eval.py',
    '--host', 'claude',
    '--mode', 'native',
    '--case', 'frontend-taste-handoff',
    '--repeat', '3',
    '--suggest-tuning',
    '--adapter-executable', $python.Source,
    '--adapter-arg', 'tests/fixtures/fake_eval_host.py',
    '--output', 'eval-results/ci-native.json'
)
Invoke-CheckedPython -Arguments @(
    'scripts/run_routing_eval.py',
    '--host', 'codex',
    '--mode', 'native',
    '--cases', 'pieces/tessera-core/skills/tessera-eval/references/personal-routing-cases.json',
    '--dry-run'
)

Write-Host 'All Tessera checks passed.'
