#!/usr/bin/env bash
# 在国内 ECS 上：生成专用钥匙、装 autossh，把「你自己的」海外机 127.0.0.1:8888 转到本机。
# 必须传入自己的机器，禁止用公司跳板。
#   bash deploy/ecs-install-tunnel.sh ubuntu@你的香港公网IP
set -euo pipefail
HK="${1:-}"
if [[ -z "$HK" ]]; then
  echo "usage: $0 USER@YOUR_OWN_HOST   # 自己的香港/海外机，不要用公司机器" >&2
  exit 1
fi
KEY="/root/.ssh/id_ed25519_hk_proxy"
if [[ ! -f "$KEY" ]]; then
  ssh-keygen -t ed25519 -N "" -f "$KEY" -C "silicon-001-ecs-proxy"
fi
echo "----- 把下面整行加到香港机 ubuntu 的 ~/.ssh/authorized_keys -----"
cat "${KEY}.pub"
echo "----------------------------------------------------------------"

if ! ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=8 "$HK" "echo hk_ok"; then
  echo "还不能免密登录香港机。加好公钥后再跑：$0 $HK" >&2
  exit 2
fi
if ! ssh -i "$KEY" -o BatchMode=yes "$HK" "curl -sS -o /dev/null --max-time 5 -x http://127.0.0.1:8888 https://www.binance.com/"; then
  echo "香港机 127.0.0.1:8888 还没有 tinyproxy。先在香港跑：sudo bash deploy/hk-tinyproxy.sh" >&2
  exit 3
fi

apt-get update -y
apt-get install -y autossh
install -d /etc/systemd/system
cat >/etc/systemd/system/silicon-binance-proxy.service <<EOF
[Unit]
Description=SSH tunnel to HK tinyproxy for Binance Square
After=network-online.target
Wants=network-online.target

[Service]
User=root
Environment=AUTOSSH_GATETIME=0
ExecStart=/usr/bin/autossh -M 0 -N \\
  -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \\
  -o ExitOnForwardFailure=yes -o StrictHostKeyChecking=accept-new \\
  -i ${KEY} \\
  -L 127.0.0.1:8888:127.0.0.1:8888 \\
  ${HK}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now silicon-binance-proxy.service
sleep 2
systemctl --no-pager --full status silicon-binance-proxy.service | head -n 20
curl -sS -o /dev/null -w "ecs_via_tunnel binance=%{http_code} t=%{time_total}\\n" \
  --max-time 12 -x http://127.0.0.1:8888 "https://www.binance.com/"
echo "ok · 在 ECS .env 加：SQUARE_HTTPS_PROXY=http://127.0.0.1:8888"
