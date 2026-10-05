"""Network helpers."""
import subprocess

from utils.paths import NO_WINDOW


def host_reachable(ip: str, timeout_ms: int = 3000) -> bool:
    """Return True only when ``ip`` really answers a ping.

    Windows ``ping`` exits with code 0 when a router replies "Destination host
    unreachable", so the exit code alone is not trustworthy. A genuine echo
    reply always contains "TTL=".
    """
    try:
        result = subprocess.run(["ping", "-n", "1", "-w", str(timeout_ms), ip], capture_output=True, text=True,
                                errors="replace", creationflags=NO_WINDOW, timeout=timeout_ms / 1000 + 10)
    except (subprocess.SubprocessError, OSError):
        return False
    return result.returncode == 0 and "TTL=" in result.stdout.upper()
