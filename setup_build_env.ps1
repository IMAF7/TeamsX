# Setup build venv (ASCII only)
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Venv = Join-Path $Root ".venv-build"

if (-not (Test-Path -LiteralPath $Venv)) {
    Write-Host "Creating venv: $Venv"
    python -m venv $Venv
}

$Py = Join-Path $Venv "Scripts\python.exe"
$Pip = Join-Path $Venv "Scripts\pip.exe"

& $Py -m pip install --upgrade pip
& $Pip install -r (Join-Path $Root "requirements-build.txt")

Write-Host ""
Write-Host "Ready. Run: .\build.ps1"
