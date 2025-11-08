# recommended_utils.py
import sys, subprocess, termios, atexit

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

def run_cmd(cmd, capture=True, passthrough=False, check=True):
    """기본은 stdin=DEVNULL로 안전 실행. passthrough=True면 interactive 실행."""
    if passthrough:
        return subprocess.call(cmd, shell=True)
    proc = subprocess.run(
        cmd,
        shell=True,
        capture_output=capture,
        text=True,
        stdin=subprocess.DEVNULL
    )
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    if check and getattr(proc, "returncode", 0) != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd)
    return proc