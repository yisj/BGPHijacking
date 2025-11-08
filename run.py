#!/usr/bin/env python3
# 네임스페이스 신뢰성 강화 run.py
# - ps -eww 로 mininet:<NAME> 정확 탐지
# - 정확 PID에 mnexec -a 붙여 /bin/sh -lc 로 커맨드 실행
# - stdin 분리/셸 안전 실행

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

def _ps_full_lines():
    try:
        proc = subprocess.run(
            ["ps", "-eww", "-o", "pid=", "-o", "args="],
            capture_output=True, text=True, check=True
        )
        return [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    except subprocess.CalledProcessError:
        return []

SELF_PID = str(os.getpid())
NAME_PAT = re.compile(r'(?:^|\s)mininet:([A-Za-z0-9\-]+)(?:\s|$)')

def list_nodes() -> dict:
    lines = _ps_full_lines()
    ret = {}
    for ln in lines:
        try:
            pid, args = ln.split(None, 1)
        except ValueError:
            continue
        if pid == SELF_PID:
            continue
        if " run.py " in (" " + args + " "):
            continue
        m = NAME_PAT.search(args)
        if not m:
            continue
        name = m.group(1)
        ret[name] = pid
    return ret

def pretty_print_nodes(mapping: dict):
    for name in sorted(mapping.keys()):
        pid = mapping[name]
        print(f"name: {name:>6s}, pid: {pid:>6s}")

def find_pid_for(name: str) -> str:
    lines = _ps_full_lines()
    candidates = []
    for ln in lines:
        try:
            pid, args = ln.split(None, 1)
        except ValueError:
            continue
        if pid == SELF_PID:
            continue
        if " run.py " in (" " + args + " "):
            continue
        if f"mininet:{name}" in args.split():
            candidates.append(pid)
        else:
            m = NAME_PAT.search(args)
            if m and m.group(1) == name:
                candidates.append(pid)
    if not candidates:
        return ""
    return candidates[-1]  # 최신

def main():
    if FLAGS.list:
        pretty_print_nodes(list_nodes())
        return

    if not FLAGS.node:
        parser.print_help()
        return

    pid = find_pid_for(FLAGS.node)
    if not pid:
        print(f"node `{FLAGS.node}` not found", file=sys.stderr)
        sys.exit(1)

    cmd = ' '.join(FLAGS.cmd)

    # 네임스페이스 hostname 확인 (경고만)
    try:
        sanity = subprocess.run(["mnexec", "-a", pid, "hostname"], capture_output=True, text=True, timeout=1)
        hn = (sanity.stdout or "").strip()
        if hn and hn not in (FLAGS.node, "mininet"):
            print(f"[경고] 요청 노드 '{FLAGS.node}' vs 실제 hostname '{hn}'", file=sys.stderr)
    except Exception:
        pass

    # 셸을 통해 실행(파이프/리다이렉션/따옴표 보존)
    os.execvp("mnexec", ["mnexec", "-a", pid, "/bin/sh", "-lc", cmd])

if __name__ == '__main__':
    main()