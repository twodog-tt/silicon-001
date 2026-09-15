#!/usr/bin/env bash
# 在阿里云 ECS 上装依赖、字体、日志目录。不写密钥、不开 HTTP 端口。
set -euo pipefail
REPO="${1:-/opt/silicon-001}"
cd "$REPO"
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update -y
  sudo apt-get install -y fonts-noto-cjk
fi
sudo mkdir -p /var/log/silicon-001
sudo chown "$(id -un):$(id -gn)" /var/log/silicon-001
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "edit $REPO/.env then crontab deploy/crontab" >&2
fi
echo "ok · venv ready · fill .env · crontab deploy/crontab"
