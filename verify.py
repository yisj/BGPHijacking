#!/usr/bin/env python3
import argparse, atexit
from recommended_utils import save_tty, restore_tty, run_cmd

def section(t: str):
    print("\n" + t)
    print("-" * len(t))

def main():
    ap = argparse.ArgumentParser(description="Verify BGP lab processes and logs.")
    ap.add_argument("--routers", default="R1,R2,R3,R4,R5,R6",
                    help="Comma-separated router list (default: R1..R6)")
    ap.add_argument("--tail", type=int, default=10, help="Lines to tail from bgpd logs")
    args = ap.parse_args()

    saved = save_tty()
    atexit.register(restore_tty, saved)

    try:
        routers = [r.strip() for r in args.routers.split(",") if r.strip()]

        section("Active nodes")
        # run.py는 sudo 불필요
        run_cmd("python3 run.py --list", check=False)

        section("BGP TCP/179 listeners")
        for r in routers:
            print(f"[{r}]")
            # sudo -n: 비대화형, 실패해도 진행(check=False)
            run_cmd(f"sudo -n python3 run.py --node {r} --cmd \"ss -tnlp | grep ':179 ' || true\"",
                    check=False)

        section(f"Recent bgpd logs (last {args.tail} lines)")
        for r in routers:
            print(f"== /tmp/{r}-bgpd.log ==")
            run_cmd(f"sudo -n python3 run.py --node {r} --cmd \"tail -n {args.tail} /tmp/{r}-bgpd.log || true\"",
                    check=False)

        section("Hint")
        print(" - 상세 상태: ./connect.sh R2  →  'show ip bgp summary'")
        print(" - 웹 서버 확인: ./website.sh h1-1 (공격 전) / ./website.sh h6-1 (공격 서버)")
    finally:
        restore_tty(saved)

if __name__ == "__main__":
    main()