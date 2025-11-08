#!/usr/bin/env python3
"""
attack_orchestrator.py
- Steps 2) ~ 6) 통합 자동화 스크립트

기능 요약
1) (옵션) R6 FRR(zebra/bgpd) 및 h6-1 웹서버 기동
2) R6 리스너/프로세스, R2/R3/R5 BGP 요약(vtysh) 확인
3) h5-1에서 11.0.1.1 HTTP 확인(기본 상태)
4) (옵션) R6 bgpd를 hard 모드로 전환(11.0.0.0/9 두 개 광고) 후,
   h2-1, h3-1, h4-1, h5-1에서 공격 효과 확인
5) R5 bgpd 로그 tail 및 요약 출력

주의
- 반드시 프로젝트 루트(BGPHijacking)에서 실행하세요. (run.py 경로 기준)
- Mininet 토폴로지가 이미 올라와 있어야 합니다. (start_topology.py 실행 후, mininet> 유지)
- run.py 호출은 sudo 권한이 필요합니다.
"""
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

def run_node(node: str, cmd: str) -> Tuple[int, str, str]:
    """sudo python3 run.py --node <node> --cmd "<cmd>" 호출"""
    quoted = shlex.quote(cmd)
    full = f"sudo python3 run.py --node {shlex.quote(node)} --cmd {quoted}"
    return run_local(full, capture=True)

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
    """R6 zebra/bgpd 기동 + h6-1 공격자 웹서버 기동 (이미 떠 있으면 그대로 통과)"""
    print_header("R6: FRR 데몬 및 h6-1 웹서버 기동")

    # R6 zebra/bgpd (기본 공격: bgpd-R6.conf)
    cmds = [
        "/usr/lib/frr/zebra -f conf/zebra-R6.conf -d -i /tmp/zebra-R6.pid > logs/R6-zebra-stdout 2>&1",
        "/usr/lib/frr/bgpd  -f conf/bgpd-R6.conf  -d -i /tmp/bgpd-R6.pid  > logs/R6-bgpd-stdout  2>&1",
    ]
    for c in cmds:
        rc, out, err = run_node("R6", c + " || true")
        # 출력은 조용하게, 에러만 필요 시 확인
        if err:
            print(f"[zebra/bgpd] stderr: {err}")

    # h6-1 공격자 웹서버
    rc, out, err = run_node("h6-1", "ps aux | grep '[w]ebserver.py' || true")
    if not out:
        rc, out, err = run_node(
            "h6-1",
            "python3 webserver.py --text '*** Attacker web server (AS6) ***' &>/dev/null &"
        )
        print("h6-1: webserver started.")
    else:
        print("h6-1: webserver already running.")

def check_r6_status() -> None:
    """R6 포트179 리스너 및 FRR 프로세스 확인"""
    rc, out, err = run_node("R6", "ss -tnlp | grep ':179 ' || true")
    print_block("R6: TCP/179 리스너", out or err)

    rc, out, err = run_node("R6", "ps aux | egrep '[z]ebra|[b]gpd' || true")
    print_block("R6: FRR 프로세스", out or err)

def bgp_summary(nodes: List[str]) -> None:
    """각 라우터의 BGP 요약 출력 (vtysh가 없으면 로그 안내)"""
    for n in nodes:
        title = f"{n}: show ip bgp summary"
        rc, out, err = run_node(n, "vtysh -c 'show ip bgp summary' || true")
        if out:
            print_block(title, out)
        else:
            # vtysh가 없거나 bgpd가 아직 준비 안 된 경우 로그로 대체
            rc2, out2, err2 = run_node(n, "tail -n 40 /tmp/{}-bgpd.log || true".format(n))
            msg = out2 if out2 else err or "(vtysh 출력이 없어 로그로 대체했으나 로그도 없음)"
            print_block(f"{title} (fallback: tail bgpd.log)", msg)

def http_probe(node: str, target_ip: str = "11.0.1.1", timeout: int = 4) -> str:
    """node에서 target_ip로 curl 수행 후 body 반환(없으면 빈 문자열)"""
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
            # 응답이 너무 길면 앞부분만
            snippet = body
            if len(snippet) > 120:
                snippet = snippet[:120] + "..."
            lines.append(f"[{n}] {snippet}")
    print_block(f"HTTP GET 결과 (→ http://{target_ip})", "\n".join(lines))

def switch_to_hard_mode() -> None:
    """R6 bgpd를 hard 설정으로 전환 (기존 bgpd-R6 프로세스 kill 후 hard로 재기동)"""
    print_header("R6: 고급(hard) 공격 전환")
    # 기존 bgpd 종료
    run_node("R6", "pkill -f --signal 9 [b]gpd-R6 || true")
    # hard 설정으로 기동
    rc, out, err = run_node(
        "R6",
        "/usr/lib/frr/bgpd -f conf/bgpd-R6-hard.conf -d -i /tmp/bgpd-R6.pid > logs/R6-bgpd-hard-stdout 2>&1"
    )
    if err:
        print(err)

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
    ap.add_argument("--only-hard", action="store_true", help="바로 hard 모드만 수행(기본 데몬/웹서버 기동 포함)")
    ap.add_argument("--no-start", action="store_true", help="데몬/웹서버 기동 생략 (점검만)")
    ap.add_argument("--wait", type=int, default=10, help="BGP 수렴 대기 시간(초, 기본 10)")
    args = ap.parse_args()

    print_header("전제: Mininet 토폴로지가 이미 올라와 있어야 합니다 (start_topology.py 실행).")
    print("※ 본 스크립트는 'run.py'를 sudo로 호출합니다. 비밀번호가 필요할 수 있습니다.\n")

    # 2) 공격자 데몬/웹서버 기동
    if not args.no_start:
        start_attacker_processes()
    elif not args.only-hard:
        print("(--no-start 지정됨: 데몬/웹서버 기동 생략)")

    # 2-1) R6 상태 확인
    check_r6_status()

    # 3) R2/R3/R5 BGP 요약
    bgp_summary(["R2", "R3", "R5"])

    # 4) 베이스라인: h5-1에서 기본 응답 확인
    print_header("기본 응답(공격 전 또는 단순 공격 초기 수렴 확인)")
    print(f"{args.wait}초 대기 후 HTTP 체크를 진행합니다...")
    time.sleep(max(1, args.wait))
    show_http_checks(["h5-1"], target_ip="11.0.1.1")

    # 5) (옵션) hard 모드로 전환 및 효과 확인
    if args.hard or args.only-hard:
        switch_to_hard_mode()
        print(f"{args.wait}초 대기 (hard 모드 수렴 중)...")
        time.sleep(max(1, args.wait))
        # h1-1은 기본(AS1) 유지, h2-1~h5-1은 공격자 페이지를 기대
        show_http_checks(["h1-1", "h2-1", "h3-1", "h4-1", "h5-1"], target_ip="11.0.1.1")
    else:
        print("\n(--hard 미지정: hard 모드 전환은 생략합니다.)")

    # 6) R5 로그 등 추가 관찰
    tail_logs(["R5"], lines=40)

    print_header("완료")
    print("• 출력 내용을 바탕으로 피어 수립/수렴 여부와 공격 관찰을 판단하실 수 있습니다.")
    print("• 필요 시 --hard 옵션으로 전역 공격을 확인해 보세요.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n중단되었습니다.")