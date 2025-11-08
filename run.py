#!/usr/bin/env python3
# robust run.py for Mininet nodes (PID mapping + shell-safe exec)

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

# match "... mininet:<NAME> ..." in the full argv of node shell
MINI_PAT = re.compile(r'\bmininet:([A-Za-z0-9\-]+)\b')

def list_nodes(do_print=False):
    """Return {name: pid} by scanning full command lines."""
    ret = {}
    try:
        # -eww : do not truncate; show full width
        proc = subprocess.run(
            ["ps", "-eww", "-o", "pid=", "-o", "args="],
            capture_output=True, text=True, check=True
        )
    except subprocess.CalledProcessError:
        print("ps failed", file=sys.stderr)
        return ret

    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        # split first field PID from the rest
        try:
            pid, args = line.split(None, 1)
        except ValueError:
            continue
        m = MINI_PAT.search(args)
        if not m:
            continue
        name = m.group(1)
        # last one wins (most recent)
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

    # Join the command exactly as typed; we will pass it to /bin/sh -lc
    cmd = ' '.join(FLAGS.cmd)

    # Sanity check: hostname inside that namespace
    # Run mnexec to get hostname, but treat 'mininet' as acceptable (common default).
    try:
        sanity = subprocess.run(["mnexec", "-a", pid, "hostname"], capture_output=True, text=True, timeout=1)
        hn = sanity.stdout.strip()
    except Exception:
        hn = ""

    # Many Mininet setups leave the namespace hostname as 'mininet'.
    # Only warn if hostname is present and clearly different from requested node.
    if hn and hn not in (FLAGS.node, "mininet"):
        print(f"[경고] 요청 노드 '{FLAGS.node}' vs 실제 hostname '{hn}'", file=sys.stderr)

    # Very important: run through a shell to keep pipes/quotes/redirs intact
    os.execvp("mnexec", ["mnexec", "-a", pid, "/bin/sh", "-lc", cmd])

if __name__ == '__main__':
    main()