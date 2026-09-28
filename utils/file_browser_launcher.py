"""Helper process: shows the remote FileBrowser web UI in a native window.

Runs as a separate Python process (launched by the Remote Connection page) so
that pywebview's blocking event loop does not interfere with the Qt loop.
"""
import logging
import os
import subprocess
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from utils.paths import NO_WINDOW, PSEXEC_EXE  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (FileBrowserScript) %(message)s",
    handlers=[logging.FileHandler(os.path.join(PROJECT_ROOT, "logs", "filebrowser.log"), mode="a"), logging.StreamHandler()],
)


def main():
    if len(sys.argv) != 5:
        logging.error("Usage: python file_browser_launcher.py <ip> <domain> <user> <password>. Received %d args.", len(sys.argv))
        sys.exit(1)
    remote_ip, remote_domain, remote_user, remote_password = sys.argv[1:]
    remote_share = f"\\\\{remote_ip}\\C$"
    try:
        import webview
    except ImportError:
        logging.error("pywebview is not installed (pip install pywebview)")
        sys.exit(1)

    try:
        logging.info("Opening embedded FileBrowser window for http://%s:8080", remote_ip)
        webview.create_window(f"Remote FileBrowser - {remote_ip}", f"http://{remote_ip}:8080", width=1200, height=800)
        webview.start()

        logging.info("Webview window closed. Cleaning up remote filebrowser ...")
        cleanup_command = [
            PSEXEC_EXE, f"\\\\{remote_ip}", "-accepteula", "-u", f"{remote_domain}\\{remote_user}", "-p", remote_password, "-h",
            "cmd", "/c", "taskkill /F /IM filebrowser.exe & del /F /Q C:\\filebrowser.exe & del /F /Q C:\\WINDOWS\\system32\\filebrowser.db",
        ]
        subprocess.run(cleanup_command, check=False, capture_output=True, text=True, creationflags=NO_WINDOW, timeout=120)
        logging.info("Remote cleanup finished.")
    except Exception as error:  # noqa: BLE001
        logging.error("Error in file browser script: %s", error, exc_info=True)
    finally:
        subprocess.run(["net", "use", remote_share, "/delete", "/y"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)
        logging.info("Script finished.")


if __name__ == "__main__":
    os.makedirs(os.path.join(PROJECT_ROOT, "logs"), exist_ok=True)
    main()
