"""Password-protected FileBrowser sessions on remote targets.

FileBrowser used to be started with ``--noauth``, so anyone on the target's
network could browse its C: drive while a session was open. Each session now
gets:

* a fresh database file, so FileBrowser's quick setup runs every time;
* a random user name suffix and a random password, sent to the target only as a
  bcrypt hash;
* automatic login in the Anubis viewer window, so the investigator never has to
  type the password.
"""
import json
import secrets
import subprocess

import requests

from utils.paths import FILEBROWSER_EXE, NO_WINDOW

PORT = 8080
REMOTE_EXE = "C:\\filebrowser.exe"


def new_session() -> dict:
    """Create the credentials and database path for one FileBrowser session."""
    token = secrets.token_hex(4)
    return {
        "fb_user": f"anubis_{token}",
        "fb_password": secrets.token_urlsafe(24),  # 32 characters, well above FileBrowser's minimum length
        "fb_db": f"C:\\Windows\\Temp\\anubis_fb_{token}.db",
    }


def hash_password(password: str, exe: str = FILEBROWSER_EXE) -> str:
    """Return FileBrowser's bcrypt hash of ``password`` using the bundled executable."""
    result = subprocess.run([exe, "hash", password], capture_output=True, text=True, creationflags=NO_WINDOW, timeout=60)
    hashed = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
    if result.returncode != 0 or not hashed.startswith("$2"):
        raise RuntimeError(f"Could not hash the FileBrowser password: {(result.stderr or result.stdout).strip()}")
    return hashed


def server_arguments(session: dict, password_hash: str, address: str = "0.0.0.0", port: int = PORT, root: str = "C:/") -> list[str]:
    """Command-line arguments that start FileBrowser with login required."""
    return ["--address", address, "--port", str(port), "--root", root, "--database", session["fb_db"],
            "--username", session["fb_user"], "--password", password_hash]


def login(base_url: str, user: str, password: str, timeout: int = 15) -> str:
    """Log in to FileBrowser and return the session token (JWT)."""
    response = requests.post(f"{base_url.rstrip('/')}/api/login",
                             data=json.dumps({"username": user, "password": password, "recaptcha": ""}),
                             headers={"Content-Type": "application/json"}, timeout=timeout)
    if response.status_code != 200 or response.text.count(".") != 2:
        raise RuntimeError(f"FileBrowser login failed (HTTP {response.status_code})")
    return response.text.strip()


def auto_login_script(token: str) -> str:
    """JavaScript that stores the token the way FileBrowser's web interface does, then opens the file list."""
    return f"localStorage.setItem('jwt', {json.dumps(token)}); window.location.replace('/files/');"


def cleanup_command(session: dict | None) -> str:
    """Windows command that stops FileBrowser and deletes everything it left on the target."""
    parts = ["taskkill /F /IM filebrowser.exe", f"del /F /Q {REMOTE_EXE}",
             "del /F /Q C:\\WINDOWS\\system32\\filebrowser.db"]  # left by older Anubis versions
    if session and session.get("fb_db"):
        parts.append(f"del /F /Q {session['fb_db']}")
    return " & ".join(parts)
