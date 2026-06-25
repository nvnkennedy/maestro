#!/usr/bin/env bash
# Build Maestro Docker images
set -euo pipefail
cd "$(dirname "$0")/.."

docker build -f docker/Dockerfile -t maestro:latest .
docker build -f docker/Dockerfile.frontend -t maestro-frontend:latest .
echo "Images built: maestro:latest, maestro-frontend:latest"
