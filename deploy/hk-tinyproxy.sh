#!/usr/bin/env bash
# 在你自己的香港/海外机上安装 tinyproxy，只监听 127.0.0.1:8888。
# 不要装在公司机器上。国内 ECS 用 SSH 本地转发连过来，海外机安全组不用新开端口。
set -euo pipefail
if [[ "$(id -u)" -ne 0 ]]; then
  echo "run as root: sudo bash $0" >&2
  exit 1
fi
apt-get update -y
apt-get install -y tinyproxy
CONF="$(cd "$(dirname "$0")" && pwd)/tinyproxy.conf"
if [[ -f "$CONF" ]]; then
  cp "$CONF" /etc/tinyproxy/tinyproxy.conf
else
  echo "missing $CONF" >&2
  exit 1
fi
systemctl enable --now tinyproxy
systemctl restart tinyproxy
ss -lnt | grep -E ':8888' || true
curl -sS -o /dev/null -w "via_proxy binance=%{http_code} t=%{time_total}\n" \
  --max-time 10 -x http://127.0.0.1:8888 "https://www.binance.com/" \
  || echo "tinyproxy up, but curl -x probe failed"
echo "ok · tinyproxy 127.0.0.1:8888 · next: ECS ssh tunnel"
