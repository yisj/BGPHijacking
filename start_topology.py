#!/usr/bin/env python3
import argparse, os, sys, shutil, subprocess, time

def have_rich():
    try:
        import rich  # noqa: F401
        return True
    except Exception:
        return False

def echo(msg, level="INFO"):
    if have_rich():
        from rich.console import Console
        from rich.markdown import Markdown
        c = Console()
        if level == "TITLE":
            c.rule(f"[bold]{msg}")
        elif level == "OK":
            c.print(f"✅  {msg}")
        elif level == "WARN":
            c.print(f"⚠️  {msg}", style="yellow")
        elif level == "ERR":
            c.print(f"❌  {msg}", style="red")
        else:
            c.print(f"[dim]{msg}[/dim]")
    else:
        prefixes = {
            "TITLE": "\n=== ",
            "OK": "[OK] ",
            "WARN": "[!] ",
            "ERR": "[X] ",
            "INFO": ""
        }
        print(prefixes.get(level, "") + msg)

def run(cmd, passthrough=False, check=True):
    echo(f"$ {cmd}", "INFO")
    if passthrough:
        return subprocess.call(cmd, shell=True)
    else:
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if proc.stdout:
            print(proc.stdout, end="")
        if proc.stderr:
            print(proc.stderr, end="", file=sys.stderr)
        if check and proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, cmd)
        return proc.returncode

def do_reset():
    echo("Resetting topology (equivalent to reset.sh)...", "TITLE")
    # 1) kill daemons
    echo("Kill FRR daemons (bgpd/zebra) & webservers")
    run("sudo pkill -9 bgpd  >/dev/null 2>&1 || true", check=False)
    run("sudo pkill -9 zebra >/dev/null 2>&1 || true", check=False)
    run("sudo pkill -9 -f webserver.py >/dev/null 2>&1 || true", check=False)
    # 2) mininet cleanup
    echo("Clean Mininet (mn -c)")
    run("sudo mn -c >/dev/null 2>&1 || true", check=False)
    # 3) temp logs
    echo("Remove temp PIDs/logs")
    run("rm -f /tmp/R*.pid /tmp/R*.log || true", check=False)
    run("mkdir -p logs && rm -f logs/* || true", check=False)
    # 4) optional /etc/frr perms (best-effort)
    if os.path.isdir("/etc/frr"):
        echo("Ensure /etc/frr has minimal structure & perms (best-effort)")
        for n in ("R1","R2","R3","R4","R5","R6"):
            run(f"sudo mkdir -p /etc/frr/{n}", check=False)
            run(f"sudo bash -lc \"echo '' > /etc/frr/{n}/vtysh.conf\"", check=False)
        run("sudo chown -R frr:frr /etc/frr || true", check=False)
        run("sudo find /etc/frr -type f -name 'vtysh.conf' -exec chmod 640 {{}} \\; || true", check=False)
    echo("Reset complete.", "OK")

def main():
    ap = argparse.ArgumentParser(description="Start topology with clean logs and nice output.")
    ap.add_argument("--no-reset", action="store_true", help="Skip reset before starting topology")
    ap.add_argument("--sleep", type=int, default=3, help="Seconds to wait in bgp.py")
    ap.add_argument("--rogue", action="store_true", help="Start with rogue R6 enabled")
    ap.add_argument("--python", default="python3", help="Python executable for bgp.py (default: python3)")
    ap.add_argument("--bgp-file", default="bgp.py", help="Path to bgp.py (default: bgp.py)")
    args = ap.parse_args()

    if not args.no_reset:
        do_reset()

    echo("Launching topology (Mininet CLI will open)...", "TITLE")
    cmd = f"sudo {args.python} {args.bgp-file} --sleep {args.sleep}"
    if args.rogue:
        cmd += " --rogue"
        echo("Rogue mode enabled (AS6 will be active).", "WARN")

    echo("Handing over to Mininet. Use 'quit' to exit.", "OK")
    # passthrough=True to keep interactive CLI
    code = run(cmd, passthrough=True, check=False)
    if code == 0:
        echo("Topology process exited normally.", "OK")
    else:
        echo(f"Topology process exited with code {code}", "ERR")
        sys.exit(code)

if __name__ == "__main__":
    main()