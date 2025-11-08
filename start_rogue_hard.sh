#!/bin/bash
set -euo pipefail
echo "Killing any existing rogue AS (R6) daemons"
sudo -n python3 run.py --node R6 --cmd "pkill -9 -f '/usr/lib/frr/zebra.*zebra-R6\\.conf' || true"
sudo -n python3 run.py --node R6 --cmd "pkill -9 -f '/usr/lib/frr/bgpd.*bgpd-R6\\.conf' || true"
echo "Starting rogue AS (hard)"
mkdir -p logs
sudo -n python3 run.py --node R6 --cmd "/usr/lib/frr/zebra -f conf/zebra-R6.conf    -d -i /tmp/zebra-R6.pid > logs/R6-zebra-stdout 2>&1"
sudo -n python3 run.py --node R6 --cmd "/usr/lib/frr/bgpd  -f conf/bgpd-R6-hard.conf -d -i /tmp/bgpd-R6.pid  > logs/R6-bgpd-hard-stdout 2>&1"
echo "Done."