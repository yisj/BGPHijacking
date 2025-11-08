#!/usr/bin/env python3
# 오염 제거 + 네임스페이스/포트 잔재 정리 통합 리셋 스크립트

import os
import argparse
import subprocess
import sys
import termios
import atexit

def run(cmd: str):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, stdin=subprocess.DEVNULL)

def save_tty():
    try:
        return termios.tcgetattr(sys.stdin.fileno())
    except Exception:
        return None

def restore_tty(saved):
    try:
        if saved is not None:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, saved)
    except Exception:
        pass
    subprocess.run("stty sane >/dev/null 2>&1 || true", shell=True)
    subprocess.run("tput cnorm >/dev/null 2>&1 || true", shell=True)

def main():
    ap = argparse.ArgumentParser(description="Reset BGP Hijacking lab environment (clean & decontaminate).")
    ap.add_argument("--no-iptables", action="store_true", help="iptables 플러시 생략")
    ap.add_argument("--no-sysctl", action="store_true", help="sysctl 기본값 복구 생략")
    args = ap.parse_args()

    saved_tty = save_tty()
    atexit.register(restore_tty, saved_tty)

    def title(msg: str):
        print("=" * 70)
        print(msg)
        print("=" * 70)

    def log(step: int, total: int, msg: str):
        print(f"[{step}/{total}] {msg}")

    try:
        title("BGP Hijacking Lab — FULL RESET")

        log(1, 9, "Kill FRR daemons (watchfrr/bgpd/zebra) & webservers")
        run("sudo pkill -9 watchfrr >/dev/null 2>&1 || true")
        run("sudo pkill -9 bgpd     >/dev/null 2>&1 || true")
        run("sudo pkill -9 zebra    >/dev/null 2>&1 || true")
        run("sudo pkill -9 -f webserver.py >/dev/null 2>&1 || true")

        log(2, 9, "Clean Mininet (mn -c)")
        run("sudo mn -c >/dev/null 2>&1 || true")

        log(3, 9, "Remove temp PIDs/logs and ensure logs/")
        run("rm -f /tmp/R*.pid /tmp/R*.log || true")
        run("mkdir -p logs && rm -f logs/* || true")

        log(4, 9, "Purge stale vty sockets (TCP 2601-2609, 179 watchers)")
        # (namespaces마다 별개지만 혹시 host에 남은 경우 best-effort 정리)
        run("sudo ss -tanp | egrep ':26(0[1-9])\\s' | awk '{print $6}' | cut -d, -f2 | cut -d= -f2 | xargs -r sudo kill -9 || true")

        log(5, 9, "Release possible locks under /tmp/*-R?.pid")
        run("sudo rm -f /tmp/*-R?.pid /tmp/*-R??.pid || true")

        if not args.no_iptables:
            log(6, 9, "Flush iptables (filter/nat/mangle) — host level")
            run("sudo iptables -F >/dev/null 2>&1 || true")
            run("sudo iptables -t nat -F >/dev/null 2>&1 || true")
            run("sudo iptables -t mangle -F >/dev/null 2>&1 || true")

        if not args.no_sysctl:
            log(7, 9, "Restore sysctl defaults (selectively)")
            run("sudo sysctl -w net.ipv4.ip_forward=0 >/dev/null 2>&1 || true")
            run("sudo sysctl -w net.ipv6.conf.all.disable_ipv6=0 >/dev/null 2>&1 || true")

        log(8, 9, "Best-effort FRR vtysh conf scaffolding")
        if os.path.isdir("/etc/frr"):
            for n in ("R1","R2","R3","R4","R5","R6"):
                run(f"sudo mkdir -p /etc/frr/{n}")
                run(f"sudo bash -lc \"echo '' > /etc/frr/{n}/vtysh.conf\"")
            run("sudo chown -R frr:frr /etc/frr || true")
            run("sudo find /etc/frr -type f -name 'vtysh.conf' -exec chmod 640 {} \\; || true")

        log(9, 9, "Done. System is clean.")
    finally:
        restore_tty(saved_tty)

if __name__ == "__main__":
    main()