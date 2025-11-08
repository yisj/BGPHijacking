#!/usr/bin/env python3
import os
import argparse
import subprocess
import sys
import termios
import tty
import atexit

def run(cmd: str):
    # 하위 프로세스가 터미널을 건드리지 않게 표준입력을 끊어둡니다.
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, stdin=subprocess.DEVNULL)

# 현재 TTY 설정 저장
def save_tty():
    try:
        return termios.tcgetattr(sys.stdin.fileno())
    except Exception:
        return None

# TTY 복구
def restore_tty(saved):
    try:
        if saved is not None:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, saved)
    except Exception:
        pass
    # 그래도 혹시 몰라서 stty/tput로 한 번 더 복구
    subprocess.run("stty sane >/dev/null 2>&1 || true", shell=True)
    subprocess.run("tput cnorm >/dev/null 2>&1 || true", shell=True)

def main():
    ap = argparse.ArgumentParser(description="Reset BGP Hijacking lab environment.")
    ap.add_argument("--pretty", action="store_true", help="(unused: plain output only)")
    args = ap.parse_args()

    # TTY 상태 백업 + 종료 시 항상 복구
    saved_tty = save_tty()
    atexit.register(restore_tty, saved_tty)

    def title(msg: str):
        print("=" * 70)
        print(msg)
        print("=" * 70)

    def log(step: int, total: int, msg: str):
        print(f"[{step}/{total}] {msg}")

    try:
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
    finally:
        # finally에서 TTY 복구(atexit도 있으나 즉시 복구 보장)
        restore_tty(saved_tty)

if __name__ == "__main__":
    main()