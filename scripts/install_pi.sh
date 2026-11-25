#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PI_USER="${SUDO_USER:-$USER}"
PI_HOME="$(getent passwd "$PI_USER" | cut -d: -f6)"
INSTALL_DIR="$PI_HOME/prahari-eo"
VENV_DIR="$PI_HOME/prahari-env"

if [[ "$PROJECT_DIR" != "$INSTALL_DIR" ]]; then
  echo "Place this checkout at $INSTALL_DIR before installing (current: $PROJECT_DIR)." >&2
  exit 2
fi

sudo apt update
sudo apt install -y python3-venv python3-opencv python3-numpy python3-lgpio \
  python3-gpiozero python3-yaml v4l-utils
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  python3 -m venv --system-site-packages "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements-pi.txt"
sudo install -m 0644 "$PROJECT_DIR/deploy/prahari.service" /etc/systemd/system/prahari.service
sudo sed -i "s/^User=dtc$/User=$PI_USER/; s|^WorkingDirectory=/home/dtc/prahari-eo$|WorkingDirectory=$INSTALL_DIR|; s|^ExecStart=/home/dtc/prahari-env|ExecStart=$VENV_DIR|" /etc/systemd/system/prahari.service
sudo systemctl daemon-reload
echo "Installed. Service is not enabled yet. Review config.yaml, secure the frame, and verify the configured soft limits before enabling the hardware service."
