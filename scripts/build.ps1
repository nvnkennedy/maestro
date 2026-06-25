# Build Maestro (backend deps + frontend bundle) — Windows
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "Installing backend dependencies..." -ForegroundColor Cyan
python -m pip install -r requirements.txt

Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
npm install --prefix frontend --no-audit --no-fund

Write-Host "Building frontend..." -ForegroundColor Cyan
npm run build --prefix frontend

Write-Host "Running backend tests..." -ForegroundColor Cyan
python -m pytest tests/

Write-Host "Build complete. Run 'python app.py' to start Maestro." -ForegroundColor Green
