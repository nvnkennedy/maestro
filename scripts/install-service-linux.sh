#!/usr/bin/env bash
# Install Maestro as a systemd service (run with sudo)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME="${SUDO_USER:-$USER}"

cat > /etc/systemd/system/maestro.service << EOF
[Unit]
Description=Maestro Automotive Test Automation Framework
After=network.target

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$ROOT
Environment=MAESTRO_OPEN_BROWSER=false
ExecStart=$(command -v python3) $ROOT/app.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now maestro
echo "Maestro service installed and started (http://localhost:8000)"
