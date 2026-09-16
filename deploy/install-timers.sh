#!/usr/bin/env bash
# 用 systemd timer（带时区）替代 crontab。Ubuntu 用户 crontab 常忽略 CRON_TZ。
set -euo pipefail
REPO="${1:-/home/admin/silicon-001}"
UNIT_DIR=/etc/systemd/system
sudo cp "$REPO/deploy/systemd/silicon-square@.service" "$UNIT_DIR/"
sudo cp "$REPO/deploy/systemd/silicon-square-us-pre.timer" "$UNIT_DIR/"
sudo cp "$REPO/deploy/systemd/silicon-square-us-after.timer" "$UNIT_DIR/"
sudo cp "$REPO/deploy/systemd/silicon-square-wave-4h.timer" "$UNIT_DIR/"
if [[ "$REPO" != "/home/admin/silicon-001" ]]; then
  sudo sed -i "s#/home/admin/silicon-001#$REPO#g" "$UNIT_DIR/silicon-square@.service"
fi
sudo mkdir -p "$REPO/logs"
sudo systemctl daemon-reload
sudo systemctl enable --now silicon-square-us-pre.timer silicon-square-us-after.timer silicon-square-wave-4h.timer
# 去掉会按系统时区误触发的 crontab
if crontab -l 2>/dev/null | grep -q square-job; then
  crontab -l | grep -v square-job | grep -v '^CRON_TZ=' | grep -v '^REPO=' | grep -v '^PY=' | grep -v '^LOG=' | crontab - || true
fi
systemctl list-timers 'silicon-square-*' --no-pager
echo "ok · systemd timers with America/New_York and UTC"
