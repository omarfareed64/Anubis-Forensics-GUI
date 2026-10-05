"""Helper process: shows the remote FileBrowser web UI in a native window.

Runs as a separate Python process (launched by the Remote Connection page) so
that pywebview's blocking event loop does not interfere with the Qt loop.

Usage: python file_browser_launcher.py <ip> <domain> <user>
Secrets are read from environment variables so they never appear on a command line:
    ANUBIS_REMOTE_PASSWORD  password of the remote Windows account (for cleanup)
    ANUBIS_FB_USER          FileBrowser user created for this session
    ANUBIS_FB_PASSWORD      its password (used to log in automatically)
    ANUBIS_FB_DB            FileBrowser database path on the target (deleted on cleanup)
"""
import logging
import os
import subprocess
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from services import filebrowser_session  # noqa: E402
from utils.paths import NO_WINDOW, PSEXEC_EXE  # noqa: E402

os.makedirs(os.path.join(PROJECT_ROOT, "logs"), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (FileBrowserScript) %(message)s",
    handlers=[logging.FileHandler(os.path.join(PROJECT_ROOT, "logs", "filebrowser.log"), mode="a"), logging.StreamHandler()],
)


def main():
    if len(sys.argv) != 4:
        logging.error("Usage: python file_browser_launcher.py <ip> <domain> <user>. Received %d args.", len(sys.argv) - 1)
        sys.exit(1)
    remote_ip, remote_domain, remote_user = sys.argv[1:]
    remote_password = os.environ.get("ANUBIS_REMOTE_PASSWORD", "")
    session = {"fb_user": os.environ.get("ANUBIS_FB_USER", ""), "fb_password": os.environ.get("ANUBIS_FB_PASSWORD", ""),
               "fb_db": os.environ.get("ANUBIS_FB_DB", "")}
    remote_share = f"\\\\{remote_ip}\\C$"
    base_url = f"http://{remote_ip}:{filebrowser_session.PORT}"
    try:
        import webview
    except ImportError:
        logging.error("pywebview is not installed (pip install pywebview)")
        sys.exit(1)

    try:
        token = None
        if session["fb_user"] and session["fb_password"]:
            try:
                token = filebrowser_session.login(base_url, session["fb_user"], session["fb_password"])
                logging.info("Logged in to FileBrowser on %s", remote_ip)
            except Exception as error:  # noqa: BLE001
                logging.warning("Automatic login failed, the login page will be shown: %s", error)

        logging.info("Opening embedded FileBrowser window for %s", base_url)
        window = webview.create_window(f"Remote FileBrowser - {remote_ip}", f"{base_url}/login", width=1200, height=800)
        if token:
            state = {"done": False}

            def on_loaded():
                # Inject the session token once, then FileBrowser opens the file list.
                if not state["done"]:
                    state["done"] = True
                    window.evaluate_js(filebrowser_session.auto_login_script(token))

            window.events.loaded += on_loaded
        webview.start()

        logging.info("Webview window closed. Cleaning up remote filebrowser ...")
        cleanup = [PSEXEC_EXE, f"\\\\{remote_ip}", "-accepteula", "-u", f"{remote_domain}\\{remote_user}", "-p", remote_password, "-h",
                   "cmd", "/c", filebrowser_session.cleanup_command(session)]
        subprocess.run(cleanup, check=False, capture_output=True, text=True, creationflags=NO_WINDOW, timeout=120)
        logging.info("Remote cleanup finished.")
    except Exception as error:  # noqa: BLE001
        logging.error("Error in file browser script: %s", error, exc_info=True)
    finally:
        subprocess.run(["net", "use", remote_share, "/delete", "/y"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=NO_WINDOW)
        logging.info("Script finished.")


if __name__ == "__main__":
    main()
