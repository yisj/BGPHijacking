#!/usr/bin/env python3
import argparse
import subprocess

def run(cmd: str):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)

def section(title: str):
    print("\n" + title)
    print("-" * len(title))

def list_nodes():
    p = run("python3 run.py --list")
    return p.stdout.strip()

def show_bgp_listeners(routers):
    section("BGP TCP/179 listeners")
    for r in routers:
        print(f"[{r}]")
        cmd = f"sudo python3 run.py --node {r} --cmd \"ss -tnlp | grep ':179 ' || true\""
        out = run(cmd).stdout.strip()
        print(out if out else "(no listener or ss not available)")

def tail_bgpd_logs(routers, nlines):
    section(f"Recent bgpd logs (last {nlines} lines)")
    for r in routers:
        print(f"== /tmp/{r}-bgpd.log ==")
        cmd = f"sudo python3 run.py --node {r} --cmd \"tail -n {nlines} /tmp/{r}-bgpd.log || true\""
        out = run(cmd).stdout.strip()
        print(out if out else "(no log yet)")

def main():
    ap = argparse.ArgumentParser(description="Verify BGP lab processes and logs.")
    ap.add_argument("--routers", default="R1,R2,R3,R4,R5,R6",
                    help="Comma-separated routers (default: R1..R6)")
    ap.add_argument("--tail", type=int, default=10, help="Lines to tail (default: 10)")
    args = ap.parse_args()

    routers = [r.strip() for r in args.routers.split(",") if r.strip()]

    section("Active nodes")
    nodes = list_nodes()
    print(nodes if nodes else "(no nodes detected)")

    show_bgp_listeners(routers)
    tail_bgpd_logs(routers, args.tail)

    section("Hint")
    print(" - 상세 상태: ./connect.sh R2  →  'show ip bgp summary'")
    print(" - 웹 서버 확인: ./website.sh h1-1 (공격 전) / ./website.sh h6-1 (공격 서버)")

if __name__ == "__main__":
    main()