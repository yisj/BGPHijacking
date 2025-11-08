#!/usr/bin/env python3
import os, sys, subprocess

def have_rich():
    try:
        import rich  # noqa
        return True
    except Exception:
        return False

def echo(msg, level="INFO"):
    if have_rich():
        from rich.console import Console
        c = Console()
        styles = {"OK":"green","WARN":"yellow","ERR":"red","TITLE":"bold"}
        if level == "TITLE":
            c.rule(f"[bold]{msg}")
        else:
            icon = {"OK":"✅","WARN":"⚠️","ERR":"❌"}.get(level,"•")
            c.print(f"{icon} {msg}", style=styles.get(level,""))
    else:
        print(msg)

def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)

def main():
    echo("BGP Hijacking Lab — RESET", "TITLE")

    echo("1/5 Kill FRR daemons (bgpd/zebra) & webservers")
    for cmd in [
        "sudo pkill -9 bgpd  >/dev/null 2>&1 || true",
        "sudo pkill -9 zebra >/dev/null 2>&1 || true",
        "sudo pkill -9 -f webserver.py >/dev/null 2>&1 || true",
    ]:
        run(cmd)

    echo("2/5 Clean Mininet (mn -c)")
    run("sudo mn -c >/dev/null 2>&1 || true")

    echo("3/5 Remove temp PIDs/logs")
    run("rm -f /tmp/R*.pid /tmp/R*.log || true")
    run("mkdir -p logs && rm -f logs/* || true")

    echo("4/5 Ensure /etc/frr (best-effort)")
    if os.path.isdir("/etc/frr"):
        for n in ("R1","R2","R3","R4","R5","R6"):
            run(f"sudo mkdir -p /etc/frr/{n}")
            run(f"sudo bash -lc \"echo '' > /etc/frr/{n}/vtysh.conf\"")
        run("sudo chown -R frr:frr /etc/frr || true")
        run("sudo find /etc/frr -type f -name 'vtysh.conf' -exec chmod 640 {} \\; || true")
    else:
        echo("/etc/frr not found — skipping.", "WARN")

    echo("5/5 Done. System is clean.", "OK")

if __name__ == "__main__":
    main()