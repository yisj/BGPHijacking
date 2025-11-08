#!/usr/bin/env bash
set -euo pipefail

echo "[Check] Active nodes"
python3 run.py --list || true

echo
echo "[Check] BGP TCP/179 listeners"
for r in R1 R2 R3 R4 R5 R6; do
  echo "== $r =="
  sudo python3 run.py --node $r --cmd "ss -tnlp | grep ':179 ' || true"
done

echo
echo "[Check] Recent bgpd logs (last 10 lines)"
for r in R1 R2 R3 R4 R5 R6; do
  echo "== /tmp/${r}-bgpd.log =="
  sudo python3 run.py --node $r --cmd "tail -n 10 /tmp/${r}-bgpd.log || true"
done

echo
echo "[Hint]"
echo " - 상세 상태를 보려면: ./connect.sh R2  (telnet으로 bgpd 접속 후 'show ip bgp summary')"
echo " - 웹 서버 확인: 다른 터미널에서 ./website.sh h1-1  (공격 전) / ./website.sh h6-1 (공격 서버)"