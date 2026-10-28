$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 (Join-Path $PSScriptRoot 'scripts/bootstrap.py') @args
    exit $LASTEXITCODE
}
if (Get-Command python -ErrorAction SilentlyContinue) {
    & python (Join-Path $PSScriptRoot 'scripts/bootstrap.py') @args
    exit $LASTEXITCODE
}
Write-Error 'Brak Pythona 3.10+. https://www.python.org/downloads/windows/'
exit 2
