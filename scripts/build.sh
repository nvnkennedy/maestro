#!/usr/bin/env bash
# Build Maestro (backend deps + frontend bundle) — Linux/macOS
set -euo pipefail
cd "$(dirname "$0")/.."

echo "Installing backend dependencies..."
python3 -m pip install -r requirements.txt

echo "Installing frontend dependencies..."
npm install --prefix frontend --no-audit --no-fund

echo "Building frontend..."
npm run build --prefix frontend

echo "Running backend tests..."
python3 -m pytest tests/

echo "Build complete. Run 'python3 app.py' to start Maestro."
