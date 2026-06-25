#!/usr/bin/env bash
# Start Maestro in development mode (backend + Vite dev server)
set -euo pipefail
cd "$(dirname "$0")/.."

trap 'kill 0' EXIT
python3 -m uvicorn backend.main:create_app --factory --reload --port 8000 &
npm run dev --prefix frontend &
echo "Backend:  http://localhost:8000  |  Frontend: http://localhost:5173"
wait
