#!/usr/bin/env python3
# 안전한 mininet 노드 명령 실행기
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

# '... mininet:<NAME> ...' 형태를 robust하게 파싱
MINI_PAT = re.compile(r'mininet:([A-Za-z0-9\-]+)')

def list_nodes(do_print=False):
    # ps 출력에서 mininet:<name> 를 모두 수집
    ret = {}
    try:
        proc = subprocess.run(
            ["ps", "-eo", "pid,cmd", "--no-headers"],
            capture_output=True, text=True, check=True
        )
    except subprocess.CalledProcessError as e:
        print("ps failed", file=sys.stderr)
        return ret

    for line in proc.stdout.splitlines():
        m = MINI_PAT.search(line)
        if not m:
            continue
        name = m.group(1)
        pid  = line.strip().split()[0]
        # 같은 이름이 여러 번 나오면 가장 마지막(최근)을 사용
        ret[name] = pid

    if do_print:
        for name, pid in sorted(ret.items()):
            print(f"name: {name:>6s}, pid: {pid:>6s}")
    return ret

def main():
    if FLAGS.list:
        list_nodes(do_print=True)
        return

    if not FLAGS.node:
        parser.print_help()
        return

    pid_by_name = list_nodes()
    pid = pid_by_name.get(FLAGS.node)
    if pid is None:
        print(f"node `{FLAGS.node}` not found", file=sys.stderr)
        sys.exit(1)

    cmd = ' '.join(FLAGS.cmd)
    # 실행 전 sanity: 해당 네임스페이스에서 hostname을 찍어 일치 여부를 stderr 경고
    sanity = subprocess.run(["mnexec", "-a", pid, "hostname"], capture_output=True, text=True)
    if sanity.stdout.strip() and sanity.stdout.strip() != FLAGS.node:
        print(f"[경고] 요청 노드 '{FLAGS.node}' vs 실제 hostname '{sanity.stdout.strip()}'", file=sys.stderr)

    os.execvp("mnexec", ["mnexec", "-a", pid] + cmd.split())

if __name__ == '__main__':
    main()