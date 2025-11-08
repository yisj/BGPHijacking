#!/usr/bin/env python3
# robust run.py for Mininet nodes (exact per-node PID lookup + shell-safe exec)

import os
import sys
import re
import subprocess
from argparse import ArgumentParser

parser = ArgumentParser("Connect to a mininet node and run a command")
parser.add_argument('--node', help="The node's name (e.g., h1-1, R2, etc.)")
parser.add_argument('--list', action="store_true", default=False, help="List all running nodes.")
parser.add_argument('--cmd', nargs="+", default=['ifconfig'], help="Command to run inside node.")
FLAGS = parser.parse_args()

# ps의 전체 커맨드라인에서 "mininet:<NAME>" 토큰을 찾기 위한 정규식 템플릿
def _name_pat(name: str) -> re.Pattern:
    # 정확히 해당 노드명과 매칭(공백/줄끝 경계 고려), 대소문자 구분
    return re.compile(r'(?:^|\s)mininet:' + re.escape(name) + r'(?:\s|$)')

# 이 스크립트 자신의 PID 문자열(자기 자신 제외 용도)
_SELF_PID = str(os.getpid())

def _ps_full_lines():
    """
    시스템 전체 프로세스의 PID와 전체 커맨드라인을 반환.
    -eww: 넓은 출력, -o pid= args= : PID와 args만
    """
    try:
        proc = subprocess.run(
            ["ps", "-eww", "-o", "pid=", "-o", "args="],
            capture_output=True, text=True, check=True
        )
        return [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    except subprocess.CalledProcessError:
        return []

def find_pid_for(name: str) -> str:
    """
    특정 노드명(name)에 해당하는 'mininet:<name>' 프로세스의 PID를 엄격히 찾는다.
    - 자기 자신(run.py 호출 트리)은 제외
    - 여러 후보가 보이면 '가장 최근에 생성된(리스트상 마지막)' 항목을 선택
    """
    pat = _name_pat(name)
    lines = _ps_full_lines()
    candidates = []
    for ln in lines:
        # "PID  ARGS..." 형태 → 첫 토큰은 PID
        try:
            pid, args = ln.split(None, 1)
        except ValueError:
            continue
        if pid == _SELF_PID:
            continue
        # run.py 자체나 sudo/python으로 실행하는 현재 호출 체인을 제외
        if " run.py " in (" " + args + " "):
            # 단, mininet:<name>를 가진 **노드 쉘**이 아니라
            # 우리 자신의 상위/하위 호출 체인을 걸러내기 위함
            # 노드 쉘은 일반적으로 bash/sh로 떠 있으며 run.py가 아님
            continue
        if pat.search(args):
            candidates.append((pid, args))

    if not candidates:
        return ""

    # "마지막으로 나타난 것"을 선택(보통 최신/유효)
    return candidates[-1][0]

def list_nodes() -> dict:
    """
    전체 노드 목록을 {name: pid} 형태로 반환.
    - 모든 "mininet:<NAME>" 토큰을 수집
    - 동일 name이 여러번 나오면 마지막(최신) PID로 갱신
    """
    lines = _ps_full_lines()
    # 일반 패턴: mininet:<NAME> 을 포괄적으로 추출
    generic_pat = re.compile(r'(?:^|\s)mininet:([A-Za-z0-9\-]+)(?:\s|$)')
    ret = {}
    for ln in lines:
        try:
            pid, args = ln.split(None, 1)
        except ValueError:
            continue
        if pid == _SELF_PID:
            continue
        if " run.py " in (" " + args + " "):
            continue
        m = generic_pat.search(args)
        if not m:
            continue
        name = m.group(1)
        ret[name] = pid
    return ret

def pretty_print_nodes(mapping: dict):
    for name in sorted(mapping.keys()):
        pid = mapping[name]
        print(f"name: {name:>6s}, pid: {pid:>6s}")

def main():
    if FLAGS.list:
        mapping = list_nodes()
        pretty_print_nodes(mapping)
        return

    if not FLAGS.node:
        parser.print_help()
        return

    # 노드 전용 엄격 검색
    pid = find_pid_for(FLAGS.node)
    if not pid:
        print(f"node `{FLAGS.node}` not found", file=sys.stderr)
        sys.exit(1)

    # 실행할 명령 구성
    cmd = ' '.join(FLAGS.cmd)

    # Sanity check: hostname inside that namespace (경고만)
    try:
        sanity = subprocess.run(["mnexec", "-a", pid, "hostname"],
                                capture_output=True, text=True, timeout=1)
        hn = (sanity.stdout or "").strip()
    except Exception:
        hn = ""

    if hn and hn not in (FLAGS.node, "mininet"):
        print(f"[경고] 요청 노드 '{FLAGS.node}' vs 실제 hostname '{hn}'", file=sys.stderr)

    # 셸을 통해 실행(파이프/리다이렉션/따옴표 보존)
    os.execvp("mnexec", ["mnexec", "-a", pid, "/bin/sh", "-lc", cmd])

if __name__ == '__main__':
    main()