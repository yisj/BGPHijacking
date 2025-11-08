#!/usr/bin/env python3
import argparse, sys
from recommended_utils import save_tty, restore_tty, run_cmd
import atexit

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-reset", action="store_true")
    ap.add_argument("--sleep", type=int, default=3)
    ap.add_argument("--rogue", action="store_true")
    ap.add_argument("--python", default="python3")
    ap.add_argument("--bgp-file", default="bgp.py")
    args = ap.parse_args()

    saved = save_tty()
    atexit.register(restore_tty, saved)

    try:
        if not args.no_reset:
            print("== RESETTING ==")
            run_cmd("sudo pkill -9 bgpd >/dev/null 2>&1 || true")
            run_cmd("sudo pkill -9 zebra >/dev/null 2>&1 || true")
            run_cmd("sudo pkill -9 -f webserver.py >/dev/null 2>&1 || true")
            run_cmd("sudo mn -c >/dev/null 2>&1 || true")
            run_cmd("rm -f /tmp/R*.pid /tmp/R*.log || true")
            run_cmd("mkdir -p logs && rm -f logs/* || true")

        print("== START TOPOLOGY ==")
        cmd = f"sudo {args.python} {args.bgp_file} --sleep {args.sleep}"
        if args.rogue:
            cmd += " --rogue"

        print("Handing over to Mininet CLI (interactive). Type 'quit' to exit.")
        # interactive: passthrough True (이 경우 하위 프로세스가 TTY를 건드려도 복구 보장)
        run_cmd(cmd, passthrough=True, check=False)
    finally:
        restore_tty(saved)
        print("TTY restored. Exiting.")

if __name__ == "__main__":
    main()