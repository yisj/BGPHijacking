#!/usr/bin/env python3
import argparse, subprocess, sys

def have_rich():
    try:
        import rich  # noqa
        return True
    except Exception:
        return False

def echo_title(t):
    if have_rich():
        from rich.console import Console
        c = Console()
        c.rule(f"[bold]{t}")
    else:
        print(f"\n=== {t} ===")

def echo(msg, style=None):
    if have_rich():
        from rich.console import Console
        c = Console()
        c.print(msg, style=style or "")
    else:
        print(msg)

def run(cmd, check=False):
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return proc

def list_nodes():
    p = run("python3 run.py --list", check=False)
    return p.stdout.strip()

def show_bgp_listeners(routers):
    echo_title("BGP TCP/179 listeners")
    for r in routers:
        echo(f"[{r}]", "bold")
        cmd = f"sudo python3 run.py --node {r} --cmd \"ss -tnlp | grep ':179 ' || true\""
        p = run(cmd)
        out = p.stdout.strip() or "(no listener or ss not available)"
        echo(out)

def tail_bgpd_logs(routers, nlines):
    echo_title(f"Recent bgpd logs (last {nlines} lines)")
    for r in routers:
        echo(f"== /tmp/{r}-bgpd.log ==", "bold")
        cmd = f"sudo python3 run.py --node {r} --cmd \"tail -n {nlines} /tmp/{r}-bgpd.log || true\""
        p = run(cmd)
        out = p.stdout.strip() or "(no log yet)"
        echo(out)

def main():
    ap = argparse.ArgumentParser(description="Verify BGP lab processes and logs.")
    ap.add_argument("--routers", default="R1,R2,R3,R4,R5,R6", help="Comma-separated router list (default: R1..R6)")
    ap.add_argument("--tail", type=int, default=10, help="Lines to tail from bgpd logs (default: 10)")
    args = ap.parse_args()

    routers = [r.strip() for r in args.routers.split(",") if r.strip()]

    echo_title("Active nodes")
    echo(list_nodes() or "(no nodes detected)")
    show_bgp_listeners(routers)
    tail_bgpd_logs(routers, args.tail)

    echo("\nHint:", "bold")
    echo(" - 상세 상태: ./connect.sh R2  →  'show ip bgp summary'")
    echo(" - 웹 서버 확인: ./website.sh h1-1 (공격 전) / ./website.sh h6-1 (공격 서버)")

if __name__ == "__main__":
    main()