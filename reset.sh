#!/usr/bin/env bash
set -euo pipefail

echo "[1/5] Kill FRR daemons (bgpd/zebra) and webservers"
sudo pkill -9 bgpd  >/dev/null 2>&1 || true
sudo pkill -9 zebra >/dev/null 2>&1 || true
sudo pkill -9 -f webserver.py >/dev/null 2>&1 || true

echo "[2/5] Clean Mininet (links, namespaces, OVS)"
sudo mn -c >/dev/null 2>&1 || true

echo "[3/5] Remove temp PIDs/logs"
rm -f /tmp/R*.pid /tmp/R*.log || true
mkdir -p logs
rm -f logs/* || true

echo "[4/5] (Optional) ensure /etc/frr exists and perms"
if [ -d /etc/frr ]; then
  # vtysh는 안 써도 되지만, 과거 설정 잔재로 만들어 두셔도 무방합니다.
  for n in R1 R2 R3 R4 R5 R6; do
    sudo mkdir -p /etc/frr/$n
    sudo bash -lc "echo '' > /etc/frr/$n/vtysh.conf"
  done
  sudo chown -R frr:frr /etc/frr || true
  sudo find /etc/frr -type f -name 'vtysh.conf' -exec chmod 640 {} \; || true
fi

echo "[5/5] Done. System is clean."