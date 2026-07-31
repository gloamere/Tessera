param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$SearchArguments
)

$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python3 -ErrorAction SilentlyContinue
}
if (-not $python) {
    throw 'Python 3 was not found. Install Python 3 before using gloamere-ui-system search.'
}

& $python.Source (Join-Path $PSScriptRoot 'search.py') @SearchArguments
exit $LASTEXITCODE
