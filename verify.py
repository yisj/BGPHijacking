#!/usr/bin/env python3
import argparse
from recommended_utils import save_tty, restore_tty, run_cmd
import atexit

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--routers", default="R1,R2,R3,R4,R5,R6")
    ap.add_argument("--tail", type=int, default=10)
    args = ap.parse_args()

    saved = save_tty()
    atexit.register(restore_tty, saved)

    try:
        routers = [r.strip() for r in args.routers.split(",") if r.strip()]

        print("Active nodes:")
        run_cmd("python3 run.py --list")

        print("\nBGP TCP/179 listeners:")
        for r in routers:
            print(f"[{r}]")
            run_cmd(f"sudo python3 run.py --node {r} --cmd \"ss -tnlp | grep ':179 ' || true\"")

        print(f"\nRecent bgpd logs (last {args.tail}):")
        for r in routers:
            print(f"== /tmp/{r}-bgpd.log ==")
            run_cmd(f"sudo python3 run.py --node {r} --cmd \"tail -n {args.tail} /tmp/{r}-bgpd.log || true\"")

    finally:
        restore_tty(saved)

if __name__ == "__main__":
    main()