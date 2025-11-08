#!/usr/bin/env python3
import argparse, sys, atexit
from recommended_utils import save_tty, restore_tty, run_cmd

def best_effort_reset():
    print("== RESETTING ==")
    # sudo -n : 비대화형(비밀번호 요구 시 즉시 실패, 코드!=0). 모두 best-effort.
    cmds = [
        "sudo -n pkill -9 bgpd  >/dev/null 2>&1 || true",
        "sudo -n pkill -9 zebra >/dev/null 2>&1 || true",
        "sudo -n pkill -9 -f webserver.py >/dev/null 2>&1 || true",
        "sudo -n mn -c >/dev/null 2>&1 || true",
        "rm -f /tmp/R*.pid /tmp/R*.log || true",
        "mkdir -p logs && rm -f logs/* || true",
    ]
    for c in cmds:
        run_cmd(c, check=False)  # 실패해도 진행

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-reset", action="store_true")
    ap.add_argument("--sleep", type=int, default=3)
    ap.add_argument("--rogue", action="store_true")
    ap.add_argument("--python", default="python3")
    ap.add_argument("--bgp-file", dest="bgp_file", default="bgp.py")
    args = ap.parse_args()

    saved = save_tty()
    atexit.register(restore_tty, saved)

    try:
        if not args.no_reset:
            best_effort_reset()

        print("== START TOPOLOGY ==")
        cmd = f"sudo -n {args.python} {args.bgp_file} --sleep {args.sleep}"
        if args.rogue:
            cmd += " --rogue"

        print("Handing over to Mininet CLI (interactive). Type 'quit' to exit.")
        # Mininet CLI는 상호작용이 필요 → passthrough=True
        rc = run_cmd(cmd, passthrough=True)  # check=False 기본
        print(f"== MININET EXIT (code={rc}) ==")
    finally:
        restore_tty(saved)
        print("TTY restored. Exiting.")

if __name__ == "__main__":
    main()