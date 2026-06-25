# Start Maestro in development mode (backend + Vite dev server) — Windows
$root = Split-Path -Parent $PSScriptRoot

Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root'; python -m uvicorn backend.main:create_app --factory --reload --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\frontend'; npm run dev"

Write-Host "Backend:  http://localhost:8000 (auto-reload)"
Write-Host "Frontend: http://localhost:5173 (hot module reload, proxies API)"
