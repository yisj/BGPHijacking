#!/usr/bin/env python3
# attack_orchestrator.py
import argparse
import shlex
import subprocess
import sys
import time
from typing import Tuple, List

# ------------------------------
# 런너 유틸
# ------------------------------
def run_local(cmd: str, capture: bool = True) -> Tuple[int, str, str]:
    if capture:
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    else:
        rc = subprocess.call(cmd, shell=True)
        return rc, "", ""

def run_node_raw(node: str, cmd: str) -> Tuple[int, str, str]:
    """sudo python3 run.py --node <node> --cmd "<cmd>" 호출"""
    quoted = shlex.quote(cmd)
    full = f"sudo python3 run.py --node {shlex.quote(node)} --cmd {quoted}"
    return run_local(full, capture=True)

def run_node(node: str, cmd: str) -> Tuple[int, str, str]:
    """
    호스트네임을 먼저 확인해 run.py 매핑 오류를 조기에 탐지.
    """
    rc_h, out_h, _ = run_node_raw(node, "hostname || true")
    if out_h and out_h.strip() != node:
        print(f"[경고] run.py가 '{node}' 대신 '{out_h.strip()}' 네임스페이스에 붙었습니다. run.py를 교체하세요.", file=sys.stderr)
    return run_node_raw(node, cmd)

def print_header(title: str):
    bar = "=" * len(title)
    print(f"\n{bar}\n{title}\n{bar}")

def print_block(title: str, body: str):
    print_header(title)
    print(body if body else "(출력 없음)")

# ------------------------------
# 동작 함수
# ------------------------------
def start_attacker_processes() -> None:
    """R6 zebra/bgpd 기동 + h6-1 공격자 웹서버 기동 (이미 떠 있으면 통과)"""
    print_header("R6: FRR 데몬 및 h6-1 웹서버 기동")

    cmds = [
        "/usr/lib/frr/zebra -f conf/zebra-R6.conf -d -i /tmp/zebra-R6.pid > logs/R6-zebra-stdout 2>&1",
        "/usr/lib/frr/bgpd  -f conf/bgpd-R6.conf  -d -i /tmp/bgpd-R6.pid  > logs/R6-bgpd-stdout  2>&1",
    ]
    for c in cmds:
        rc, out, err = run_node("R6", c + " || true")
        if err:
            print(f"[zebra/bgpd] stderr: {err}")

    # h6-1 웹서버
    rc, out, err = run_node("h6-1", "ps aux | grep '[w]ebserver.py' || true")
    if not out:
        run_node("h6-1", "python3 webserver.py --text '*** Attacker web server (AS6) ***' &>/dev/null &")
        print("h6-1: webserver started.")
    else:
        print("h6-1: webserver already running.")

def check_r6_status() -> None:
    rc, out, err = run_node("R6", "ss -tnlp | grep ':179 ' || true")
    print_block("R6: TCP/179 리스너", out or err)

    rc, out, err = run_node("R6", "ps aux | egrep '[z]ebra|[b]gpd' || true")
    print_block("R6: FRR 프로세스", out or err)

def bgp_summary(nodes: List[str]) -> None:
    for n in nodes:
        title = f"{n}: show ip bgp summary"
        rc, out, err = run_node(n, "vtysh -c 'show ip bgp summary' || true")
        if out:
            print_block(title, out)
        else:
            rc2, out2, err2 = run_node(n, f"tail -n 40 /tmp/{n}-bgpd.log || true")
            msg = out2 if out2 else err or "(vtysh 출력이 없어 로그로 대체했으나 로그도 없음)"
            print_block(f"{title} (fallback: tail bgpd.log)", msg)

def http_probe(node: str, target_ip: str = "11.0.1.1", timeout: int = 4) -> str:
    cmd = f"curl -s --max-time {timeout} http://{target_ip} || true"
    rc, out, err = run_node(node, cmd)
    return out.strip()

def show_http_checks(nodes: List[str], target_ip: str = "11.0.1.1"):
    lines = []
    for n in nodes:
        body = http_probe(n, target_ip=target_ip)
        if not body:
            lines.append(f"[{n}] (응답 없음)")
        else:
            snippet = body if len(body) <= 120 else body[:120] + "..."
            lines.append(f"[{n}] {snippet}")
    print_block(f"HTTP GET 결과 (→ http://{target_ip})", "\n".join(lines))

def switch_to_hard_mode() -> None:
    print_header("R6: 고급(hard) 공격 전환")
    run_node("R6", "pkill -f --signal 9 [b]gpd-R6 || true")
    rc, out, err = run_node(
        "R6",
        "/usr/lib/frr/bgpd -f conf/bgpd-R6-hard.conf -d -i /tmp/bgpd-R6.pid > logs/R6-bgpd-hard-stdout 2>&1"
    )
    if err: print(err)

def tail_logs(nodes: List[str], lines: int = 30):
    for n in nodes:
        rc, out, err = run_node(n, f"tail -n {lines} /tmp/{n}-bgpd.log || true")
        print_block(f"{n}: bgpd 로그 tail (-{lines})", out or err)

# ------------------------------
# 메인
# ------------------------------
def main():
    ap = argparse.ArgumentParser(description="BGP Hijacking Orchestrator (Steps 2~6)")
    ap.add_argument("--hard", action="store_true", help="고급(전역) 공격까지 수행")
    ap.add_argument("--only-hard", dest="only_hard", action="store_true", help="바로 hard 모드만 수행(기본 데몬/웹서버 기동 포함)")
    ap.add_argument("--no-start", action="store_true", help="데몬/웹서버 기동 생략 (점검만)")
    ap.add_argument("--wait", type=int, default=10, help="BGP 수렴 대기 시간(초, 기본 10)")
    args = ap.parse_args()

    print_header("전제: Mininet 토폴로지가 이미 올라와 있어야 합니다 (start_topology.py 실행).")
    print("※ 본 스크립트는 'run.py'를 sudo로 호출합니다. 비밀번호가 필요할 수 있습니다.\n")

    if not args.no_start:
        start_attacker_processes()
    elif not args.only_hard:
        print("(--no-start 지정됨: 데몬/웹서버 기동 생략)")

    check_r6_status()
    bgp_summary(["R2", "R3", "R5"])

    print_header("기본 응답(공격 전 또는 단순 공격 초기 수렴 확인)")
    print(f"{args.wait}초 대기 후 HTTP 체크를 진행합니다...")
    time.sleep(max(1, args.wait))
    show_http_checks(["h5-1"], target_ip="11.0.1.1")

    if args.hard or args.only_hard:
        switch_to_hard_mode()
        print(f"{args.wait}초 대기 (hard 모드 수렴 중)...")
        time.sleep(max(1, args.wait))
        show_http_checks(["h1-1", "h2-1", "h3-1", "h4-1", "h5-1"], target_ip="11.0.1.1")
    else:
        print("\n(--hard 미지정: hard 모드 전환은 생략합니다.)")

    tail_logs(["R5"], lines=40)

    print_header("완료")
    print("• 출력 내용을 바탕으로 피어 수립/수렴 여부와 공격 관찰을 판단하실 수 있습니다.")
    print("• 필요 시 --hard 옵션으로 전역 공격을 확인해 보세요.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n중단되었습니다.")