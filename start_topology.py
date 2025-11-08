#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys

def run(cmd: str, passthrough=False, check=True):
    if passthrough:
        return subprocess.call(cmd, shell=True)
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if proc.stdout:
        sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd)
    return proc.returncode

def do_reset():
    print("== RESET ==")
    run("sudo pkill -9 bgpd  >/dev/null 2>&1 || true", check=False)
    run("sudo pkill -9 zebra >/dev/null 2>&1 || true", check=False)
    run("sudo pkill -9 -f webserver.py >/dev/null 2>&1 || true", check=False)
    run("sudo mn -c >/dev/null 2>&1 || true", check=False)
    run("rm -f /tmp/R*.pid /tmp/R*.log || true", check=False)
    run("mkdir -p logs && rm -f logs/* || true", check=False)
    if os.path.isdir("/etc/frr"):
        for n in ("R1","R2","R3","R4","R5","R6"):
            run(f"sudo mkdir -p /etc/frr/{n}", check=False)
            run(f"sudo bash -lc \"echo '' > /etc/frr/{n}/vtysh.conf\"", check=False)
        run("sudo chown -R frr:frr /etc/frr || true", check=False)
        run("sudo find /etc/frr -type f -name 'vtysh.conf' -exec chmod 640 {} \\; || true", check=False)
    print("== RESET DONE ==")

def main():
    ap = argparse.ArgumentParser(description="Start topology (clean logs; Mininet CLI).")
    ap.add_argument("--no-reset", action="store_true", help="Skip reset before starting")
    ap.add_argument("--sleep", type=int, default=3, help="Seconds for bgp.py --sleep")
    ap.add_argument("--rogue", action="store_true", help="Start with rogue R6 enabled")
    ap.add_argument("--python", default="python3", help="Python executable for bgp.py")
    ap.add_argument("--bgp-file", default="bgp.py", help="Path to bgp.py")
    args = ap.parse_args()

    if not args.no_reset:
        do_reset()

    print("== START TOPOLOGY ==")
    cmd = f"sudo {args.python} {args.bgp-file} --sleep {args.sleep}"
    if args.rogue:
        cmd += " --rogue"
        print("  (rogue enabled)")
    print("  handover to Mininet CLI (type 'quit' to exit)")
    code = run(cmd, passthrough=True, check=False)
    print(f"== MININET EXIT (code={code}) ==")
    sys.exit(code)

if __name__ == "__main__":
    main()