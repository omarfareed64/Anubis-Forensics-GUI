import webview
import subprocess
import sys
import logging
import os

# Configure logging to append to the main log file
log_file_path = os.path.join(os.path.dirname(__file__), '..', 'filebrowser.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] (FileBrowserScript) %(message)s',
    handlers=[
        logging.FileHandler(log_file_path, mode='a'),
        logging.StreamHandler()
    ]
)

def main():
    if len(sys.argv) != 5:
        logging.error(f"Usage: python file_browser_launcher.py <ip> <domain> <user> <password>. Received {len(sys.argv)} args.")
        sys.exit(1)

    remote_ip, remote_domain, remote_user, remote_password = sys.argv[1:]
    remote_share = f"\\\\{remote_ip}\\C$"
    
    try:
        # 1. Open web UI in embedded popup window
        logging.info(f"[*] Opening embedded FileBrowser window for http://{remote_ip}:8080")
        
        window = webview.create_window(
            f"Remote FileBrowser - {remote_ip}",
            f"http://{remote_ip}:8080",
            width=1200,
            height=800
        )
        webview.start() # This is a blocking call that runs until the window is closed

        # 2. After closing the window, clean up
        logging.info("[*] Webview window closed by user. Starting remote cleanup...")
        remote_path = "C:\\filebrowser.exe"
        remote_db_path = "C:\\WINDOWS\\system32\\filebrowser.db"
        
        cleanup_command = [
            "PsExec.exe", f"\\\\{remote_ip}", "-accepteula",
            "-u", f"{remote_domain}\\{remote_user}", "-p", remote_password, "-h",
            "cmd", "/c",
            f"taskkill /F /IM filebrowser.exe & del /F /Q {remote_path} & del /F /Q {remote_db_path}"
        ]
        
        # Use CREATE_NO_WINDOW to prevent a console flash
        subprocess.run(cleanup_command, check=True, capture_output=True, text=True, creationflags=0x08000000)
        logging.info("[*] Remote cleanup process completed successfully.")

    except Exception as e:
        logging.error(f"Error in file browser script: {e}", exc_info=True)
    finally:
        # Final cleanup: disconnect the network share
        logging.info(f"[*] Disconnecting network share {remote_share}")
        subprocess.run(["net", "use", remote_share, "/delete"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000)
        logging.info("[*] Script finished.")

if __name__ == "__main__":
    main() 