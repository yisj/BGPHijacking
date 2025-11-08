#!/usr/bin/env python3
import os
import argparse
import subprocess

def run(cmd: str):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)

def main():
    ap = argparse.ArgumentParser(description="Reset BGP Hijacking lab environment.")
    ap.add_argument("--pretty", action="store_true", help="Use richer formatting if available.")
    args = ap.parse_args()

    use_rich = False
    if args.pretty:
        try:
            import rich  # noqa
            use_rich = True
        except Exception:
            use_rich = False

    def title(msg: str):
        if use_rich:
            from rich.console import Console
            Console().rule(f"[bold]{msg}")
        else:
            print("=" * 70)
            print(msg)
            print("=" * 70)

    def log(step: int, total: int, msg: str):
        # 고정 폭 포맷으로 들쭉날쭉 방지
        print(f"[{step}/{total}] {msg}")

    title("BGP Hijacking Lab — RESET")

    log(1, 5, "Kill FRR daemons (bgpd/zebra) & webservers")
    run("sudo pkill -9 bgpd  >/dev/null 2>&1 || true")
    run("sudo pkill -9 zebra >/dev/null 2>&1 || true")
    run("sudo pkill -9 -f webserver.py >/dev/null 2>&1 || true")

    log(2, 5, "Clean Mininet (mn -c)")
    run("sudo mn -c >/dev/null 2>&1 || true")

    log(3, 5, "Remove temp PIDs/logs")
    run("rm -f /tmp/R*.pid /tmp/R*.log || true")
    run("mkdir -p logs && rm -f logs/* || true")

    log(4, 5, "Ensure /etc/frr (best-effort)")
    if os.path.isdir("/etc/frr"):
        for n in ("R1","R2","R3","R4","R5","R6"):
            run(f"sudo mkdir -p /etc/frr/{n}")
            run(f"sudo bash -lc \"echo '' > /etc/frr/{n}/vtysh.conf\"")
        run("sudo chown -R frr:frr /etc/frr || true")
        run("sudo find /etc/frr -type f -name 'vtysh.conf' -exec chmod 640 {} \\; || true")
    else:
        print("      - /etc/frr not found — skipping.")

    log(5, 5, "Done. System is clean.")

if __name__ == "__main__":
    main()