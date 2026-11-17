$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
& python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "Unit tests failed with exit code $LASTEXITCODE" }
& python scripts\verify_v03.py
if ($LASTEXITCODE -ne 0) { throw "E2E verification failed with exit code $LASTEXITCODE" }
Write-Host "V0.4 verification completed." -ForegroundColor Green
