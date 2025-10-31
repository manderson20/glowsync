#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(pwd)"
SVC_USER="$(whoami)"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  source .venv/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt
else
  source .venv/bin/activate
  pip install -r requirements.txt
fi

python -m app.db --init

# Install systemd units
TMP_API="/tmp/lightshow-api.service"
TMP_SCH="/tmp/lightshow-scheduler.service"
sed "s|%h|/home/${SVC_USER}|g; s|%i|${SVC_USER}|g" systemd/lightshow-api.service > "$TMP_API"
sed "s|%h|/home/${SVC_USER}|g; s|%i|${SVC_USER}|g" systemd/lightshow-scheduler.service > "$TMP_SCH"

sudo mv "$TMP_API" /etc/systemd/system/lightshow-api.service
sudo mv "$TMP_SCH" /etc/systemd/system/lightshow-scheduler.service
sudo systemctl daemon-reload

echo "Done. Use: sudo systemctl enable --now lightshow-api.service lightshow-scheduler.service"
