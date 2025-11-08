#!/usr/bin/env bash
set -euo pipefail

# 1) 항상 깨끗이 비운 뒤 시작
./reset.sh

# 2) 토폴로지 시작 (기본: 정상 시나리오, 공격자 R6 비활성)
#    Mininet CLI로 진입합니다. 끝내실 때는 'quit'
echo "[Start] Launching topology..."
sudo python3 bgp.py --sleep 3

# 참고:
#   공격자(R6)도 함께 올리고 싶으면, 아래처럼 --rogue 옵션으로 실행하세요.
#   sudo python3 bgp.py --sleep 3 --rogue