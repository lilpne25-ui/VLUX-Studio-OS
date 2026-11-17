param([switch]$CheckOnly)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$Venv = Join-Path $Root ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Host "Creando entorno virtual local (.venv) con paquetes del sistema..." -ForegroundColor Cyan
    & python -m venv --system-site-packages $Venv
}
if (-not (Test-Path $Python)) { throw "No se pudo crear .venv" }
if (-not (Get-Command ffprobe -ErrorAction SilentlyContinue)) { throw "FFprobe no está en PATH" }
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { throw "FFmpeg no está en PATH" }
& $Python -c "import sqlite3; print('SQLite OK')"
& $Python -m compileall -q vlux_ci
if ($CheckOnly) {
    Write-Host "Launcher preflight OK. Use .\start.ps1 para iniciar el dashboard." -ForegroundColor Green
    exit 0
}
Write-Host "VLUX Studio OS V0.6: http://127.0.0.1:8765" -ForegroundColor Green
Write-Host "Detener con Ctrl+C. Este proceso no inicia Blender ni usa GPU." -ForegroundColor Yellow
& $Python -m vlux_ci.cli --db data\vlux.sqlite dashboard --host 127.0.0.1 --port 8765
