#!/usr/bin/env python3
"""
check_attack.py

R6(rogue) 공격자와 관련된 프로세스/리스너/웹서버/경로 상태를 자동 점검합니다.

동작:
 - 호스트(로컬)에서 bgpd/zebra 프로세스 검색
 - run.py를 통해 Mininet 노드(R6, h6-1, R5 등) 내부에서 프로세스/리스너/로그 확인
 - h5-1에서 11.0.1.1로 curl을 시도해 실제 응답 확인

필요: 프로젝트 루트에 run.py가 있어야 합니다.
실행: python3 check_attack.py
"""
import subprocess
import shlex
import sys
import textwrap

def run_local(cmd, capture=True):
    """로컬 셸 명령 실행(호스트)."""
    if capture:
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    else:
        return subprocess.call(cmd, shell=True), "", ""

def run_via_runpy(node, cmd):
    """run.py를 이용해 Mininet 노드 내부에서 명령 실행."""
    # run.py --node NODE --cmd "SHELLCMD"
    # cmd 내부에 " 가 포함될 수 있으므로 전체를 shlex.quote로 감싼다.
    full = f'python3 run.py --node {shlex.quote(node)} --cmd {shlex.quote(cmd)}'
    return run_local(full, capture=True)

def print_header(title):
    print()
    print("="*len(title))
    print(title)
    print("="*len(title))

def check_host_bgpd_zebra():
    print_header("1) 호스트 머신에서 FRR 프로세스 확인 (ps aux | grep bgpd/zebra)")
    rc, out, err = run_local("ps aux | egrep '[b]gpd|[z]ebra' || true")
    if out:
        print("발견된 FRR 관련 프로세스 (호스트):")
        print(out)
    else:
        print("호스트에서 bgpd/zebra 프로세스가 발견되지 않았습니다.")
    if err:
        print("stderr:", err)

def check_node_process(node, pattern):
    print_header(f"2) 노드 {node} 내부에서 프로세스 검색: '{pattern}'")
    rc, out, err = run_via_runpy(node, f"ps aux | egrep {shlex.quote(pattern)} || true")
    if rc != 0:
        print(f"⚠️ run.py 호출 실패 (node={node}). rc={rc}")
        if err:
            print("stderr:", err)
        return False
    if out.strip():
        print(f"[{node}]에서 발견:")
        print(out)
        return True
    else:
        print(f"[{node}]에서 프로세스가 발견되지 않음.")
        return False

def check_node_listener(node, port=179):
    print_header(f"3) 노드 {node} 내부에서 TCP 리스너 확인 (포트 {port})")
    # ss may not exist in node; use netstat/ss try
    cmd = f"ss -tnlp | grep ':{port} ' || (netstat -tnlp 2>/dev/null | grep ':{port} ' ) || true"
    rc, out, err = run_via_runpy(node, cmd)
    if rc != 0:
        print(f"⚠️ run.py 호출 실패 (node={node}). rc={rc}")
        return False
    if out.strip():
        print(f"[{node}] 포트 {port} 리스너 발견:")
        print(out)
        return True
    else:
        print(f"[{node}] 에서 포트 {port} 리스너 없음.")
        return False

def tail_bgpd_log(node, lines=10):
    print_header(f"4) 노드 {node}의 bgpd 로그 tail (last {lines})")
    cmd = f"tail -n {lines} /tmp/{node}-bgpd.log || true"
    rc, out, err = run_via_runpy(node, cmd)
    if rc != 0:
        print(f"⚠️ run.py 호출 실패 (node={node}). rc={rc}")
        return
    if out.strip():
        print(out)
    else:
        print("(로그 없음 또는 로그 파일이 존재하지 않음)")

def http_check_from(node, target_ip="11.0.1.1"):
    print_header(f"5) 노드 {node}에서 HTTP GET 시도 (curl -s {target_ip})")
    # 이 명령은 run.py를 통해 curl을 실행하여 응답 내용을 확인
    cmd = f"curl -s --max-time 3 http://{target_ip} || true"
    rc, out, err = run_via_runpy(node, cmd)
    if rc != 0:
        # curl 실패(타임아웃 등)도 정보를 보여줌
        print(f"[{node}] curl 명령 종료코드: {rc}")
    if out.strip():
        print(f"[{node}] 응답 바디 (짧게 표시):")
        # 너무 길면 앞뒤만 표시
        snippet = out.strip()
        if len(snippet) > 500:
            snippet = snippet[:400] + "\n...\n" + snippet[-80:]
        print(snippet)
        return True
    else:
        print(f"[{node}] 응답이 비어있거나 실패함.")
        if err:
            print("stderr:", err)
        return False

def check_bgp_table_via_logs(node):
    print_header(f"6) 노드 {node}의 bgpd 로그에서 최근 BGP 업데이트/경로 확인")
    tail_bgpd_log(node, lines=30)

def main():
    print("BGPHijacking 자동 점검 스크립트")
    print("프로젝트 루트에서 실행하세요 (예: ~/BGPHijacking)")
    print()

    # 1) 호스트 머신 프로세스
    check_host_bgpd_zebra()

    # 2) R6 프로세스 (bgpd/zebra) — 공격자 노드
    r6_bgpd = check_node_process("R6", "[b]gpd|bgpd")
    r6_zebra = check_node_process("R6", "[z]ebra|zebra")
    r6_listener = check_node_listener("R6", port=179)

    # 3) h6-1 webserver 프로세스
    h6_web = check_node_process("h6-1", "[w]ebserver|webserver")

    # 4) R5 로그와 R5 bgp 상태(로그 기반)
    check_bgp_table_via_logs("R5")

    # 5) h5-1에서 실제 HTTP 확인 (공격 전/후 상태 확인용)
    http_ok = http_check_from("h5-1", target_ip="11.0.1.1")

    # 종합 요약
    print_header("요약")
    print(f"R6 bgpd 프로세스: {'있음' if r6_bgpd else '없음'}")
    print(f"R6 zebra 프로세스: {'있음' if r6_zebra else '없음'}")
    print(f"R6 포트179 리스너: {'있음' if r6_listener else '없음'}")
    print(f"h6-1 webserver: {'있음' if h6_web else '없음'}")
    print(f"h5-1 -> 11.0.1.1 HTTP 응답: {'있음' if http_ok else '없음'}")

    print()
    print(textwrap.dedent("""
    다음 권장 조치 (문제 발견 시):
     - R6 bgpd/zebra가 없다면: Mininet CLI에서 R6 내부로 접속하여 수동으로 데몬 실행:
         (Mininet CLI) R6 /usr/lib/frr/zebra -f conf/zebra-R6.conf -d -i /tmp/zebra-R6.pid
         (Mininet CLI) R6 /usr/lib/frr/bgpd -f conf/bgpd-R6.conf -d -i /tmp/bgpd-R6.pid
     - h6-1 웹서버가 없다면:
         (Mininet CLI) h6-1 python3 webserver.py --text "*** Attacker web server (AS6) ***"
     - run.py 호출이 실패하면 run.py의 위치/권한을 확인하세요 (스크립트는 프로젝트 루트에서 실행되어야 합니다).
    """))

if __name__ == "__main__":
    main()