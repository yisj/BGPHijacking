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

def run_cmd(cmd, capture=True, passthrough=False, check=False):
    """
    기본은 check=False 로 예외를 내지 않습니다.
    비대화형 안전 실행을 위해 stdin=DEVNULL.
    """
    if passthrough:
        # 상호작용 필요한 경우에만 패스스루
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