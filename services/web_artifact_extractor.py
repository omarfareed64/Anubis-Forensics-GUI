import os
import subprocess
import sqlite3
import tempfile
import json
import shutil
import logging
from datetime import datetime
import html

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def generate_html_report(artifacts):
    """Generates a modern, user-friendly HTML report from artifact data."""
    
    def format_cell(content, is_url=False, is_path=False):
        """Formats table cell content, truncating long text and making URLs clickable."""
        text = str(content)
        safe_text = html.escape(text)
        
        display_text = safe_text
        if len(text) > 80:
            display_text = safe_text[:77] + "..."

        if is_url:
            return f'<td title="{safe_text}"><a href="{safe_text}" target="_blank">{display_text}</a></td>'
        
        return f'<td title="{safe_text}">{display_text}</td>'

    css = """
        <style>
            body { font-family: 'Segoe UI', Tahoma, sans-serif; background-color: #eef2f5; color: #333; margin: 0; padding: 20px; }
            .container { max-width: 1400px; margin: auto; background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
            h1 { color: #F57C1F; border-bottom: 3px solid #23292f; padding-bottom: 10px; margin-bottom: 20px; }
            details { margin-bottom: 15px; border: 1px solid #ddd; border-radius: 8px; overflow: hidden; transition: box-shadow 0.3s ease; }
            details:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
            details[open] { border-color: #F57C1F; }
            summary { font-size: 1.3em; font-weight: 600; padding: 16px 20px; background-color: #fcfcfc; cursor: pointer; outline: none; list-style-position: inside; }
            summary:hover { background-color: #f5f5f5; }
            .count { color: #F57C1F; font-weight: normal; font-size: 0.9em; margin-left: 10px; }
            .content { padding: 0; }
            table { width: 100%; border-collapse: collapse; }
            th, td { padding: 12px 20px; text-align: left; border-bottom: 1px solid #e0e0e0; max-width: 400px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
            td { font-size: 0.95em; }
            th { background-color: #23292f; color: white; font-weight: bold; }
            tr:last-child td { border-bottom: none; }
            tr:nth-child(even) { background-color: #f9f9f9; }
            tr:hover { background-color: #f0f0f0; }
            a { color: #007bff; text-decoration: none; }
            a:hover { text-decoration: underline; }
        </style>
    """
    
    body_content = ""
    for title, data in artifacts.items():
        headers, rows = data
        count = len(rows)
        
        body_content += f"<details><summary>{title} <span class='count'>({count} items found)</span></summary><div class='content'><table>"
        body_content += "<tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr>"
        
        if not rows:
            body_content += f"<tr><td colspan='{len(headers)}' style='text-align:center; padding: 20px; color: #777;'>No artifacts found.</td></tr>"
        
        for row in rows:
            body_content += "<tr>"
            for i, col in enumerate(row):
                header = headers[i].lower()
                is_url = "url" in header
                is_path = "path" in header
                body_content += format_cell(col, is_url=is_url, is_path=is_path)
            body_content += "</tr>"
            
        body_content += "</table></div></details>"

    return f"<!DOCTYPE html><html><head><title>Edge Artifacts Report</title>{css}</head><body><div class='container'><h1>Edge Browser Artifacts</h1>{body_content}</div></body></html>"

def extract_data(db_path, query):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        headers = [description[0] for description in cursor.description]
        conn.close()
        return headers, rows
    except Exception as e:
        logging.error(f"Failed to extract from {db_path}: {e}")
        return [], []

def parse_bookmarks(bookmarks_path):
    data = []
    try:
        with open(bookmarks_path, 'r', encoding='utf-8') as f:
            j = json.load(f).get("roots", {})
            for section in ("bookmark_bar", "other", "synced"):
                for item in j.get(section, {}).get("children", []):
                    if item.get("type") == "url":
                        data.append((item.get("name", "N/A"), item.get("url", "N/A")))
    except Exception as e:
        logging.error(f"Failed to parse bookmarks: {e}")
    return data

def extract_all_web_artifacts(remote_ip, domain, username, password, remote_profile=None):
    if not remote_profile:
        remote_profile = username

    base_remote_path = fr"\\{remote_ip}\C$\Users\{remote_profile}\AppData\Local\Microsoft\Edge\User Data\Default"
    tmp_dir = tempfile.mkdtemp(prefix="anubis_web_")

    # Temp local copies paths
    history_tmp_path = os.path.join(tmp_dir, "History")
    cookies_tmp_path = os.path.join(tmp_dir, "Cookies")
    bookmarks_tmp_path = os.path.join(tmp_dir, "Bookmarks")
    
    remote_share = fr"\\{remote_ip}\C$"
    psexec_path = os.path.abspath("PSTools/PsExec.exe")

    try:
        logging.info(f"Mounting remote share: {remote_share}")
        subprocess.run(
            ["net", "use", remote_share, password, f"/user:{domain}\\{username}"],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        logging.info("Remote share mounted successfully.")

        # Attempt to kill the Edge process to unlock database files
        if os.path.exists(psexec_path):
            logging.info("Attempting to close Microsoft Edge on the remote machine to unlock files...")
            kill_edge_command = [
                psexec_path, f"\\\\{remote_ip}", "-accepteula",
                "-u", f"{domain}\\{username}", "-p", password, "-h",
                "cmd", "/c", "taskkill /F /IM msedge.exe"
            ]
            # We run this command but don't check for errors, as the process might not be running, which is fine.
            subprocess.run(kill_edge_command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logging.info("Sent command to close Edge. Allowing a moment for the process to terminate.")
        else:
            logging.warning(f"PsExec not found at {psexec_path}, cannot kill remote Edge process. Files might be locked.")

        files_to_copy = {
            f"{base_remote_path}\\History": history_tmp_path,
            f"{base_remote_path}\\Network\\Cookies": cookies_tmp_path,
            f"{base_remote_path}\\Bookmarks": bookmarks_tmp_path,
        }

        for src, dst in files_to_copy.items():
            logging.info(f"Copying {src} to {dst}")
            # Use copy instead of xcopy for simplicity and to avoid dependency on xcopy being in PATH
            if os.path.exists(src):
                shutil.copy2(src, dst)
                logging.info(f"Successfully copied {os.path.basename(src)}")
            else:
                logging.warning(f"Source file not found: {src}")


        history_headers, history = extract_data(history_tmp_path, "SELECT url, title, visit_count, datetime(last_visit_time/1000000-11644473600,'unixepoch') AS visit_time FROM urls ORDER BY last_visit_time DESC LIMIT 100;")
        downloads_headers, downloads = extract_data(history_tmp_path, "SELECT target_path, tab_url, datetime(start_time/1000000-11644473600,'unixepoch') AS download_time FROM downloads ORDER BY start_time DESC LIMIT 50;")
        cookies_headers, cookies = extract_data(cookies_tmp_path, "SELECT host_key, name, value, datetime(creation_utc/1000000-11644473600,'unixepoch') AS created FROM cookies ORDER BY creation_utc DESC LIMIT 100;")
        bookmarks_rows = parse_bookmarks(bookmarks_tmp_path)
        
        report_artifacts = {
            "Browser History": (history_headers, history),
            "File Downloads": (downloads_headers, downloads),
            "Cookies": (cookies_headers, cookies),
            "Bookmarks": (["Title", "URL"], bookmarks_rows)
        }

        html_content = generate_html_report(report_artifacts)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.abspath(f"web_artifacts_{remote_ip.replace('.', '_')}_{ts}")
        os.makedirs(output_dir, exist_ok=True)
        
        report_path = os.path.join(output_dir, "Web_Artifacts_Report.html")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        # Move raw files into the output directory
        if os.path.exists(history_tmp_path): shutil.move(history_tmp_path, os.path.join(output_dir, "History"))
        if os.path.exists(cookies_tmp_path): shutil.move(cookies_tmp_path, os.path.join(output_dir, "Cookies"))
        if os.path.exists(bookmarks_tmp_path): shutil.move(bookmarks_tmp_path, os.path.join(output_dir, "Bookmarks"))

        logging.info(f"All artifacts and report are in: {output_dir}")
        return {"status": "success", "report_path": report_path, "output_dir": output_dir}

    except subprocess.CalledProcessError as e:
        error_message = f"Command failed: {e}. Stderr: {e.stderr.decode('utf-8', errors='ignore') if e.stderr else 'N/A'}"
        logging.error(error_message)
        return {"status": "error", "message": error_message}
    except Exception as e:
        error_message = f"An unexpected error occurred: {e}"
        logging.error(error_message)
        return {"status": "error", "message": error_message}
    finally:
        logging.info(f"Unmounting remote share: {remote_share}")
        subprocess.run(["net", "use", remote_share, "/delete"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)
            logging.info(f"Cleaned up temporary directory: {tmp_dir}")

if __name__ == '__main__':
    # This part is for standalone testing of the script
    r_ip = input("Remote IP: ").strip()
    r_domain = input("Domain: ").strip()
    r_user = input("Username: ").strip()
    r_pass = input("Password: ").strip()
    r_profile = input("Remote username (or leave blank to use same): ").strip() or r_user
    
    result = extract_all_web_artifacts(r_ip, r_domain, r_user, r_pass, r_profile)
    print(result)

    if result["status"] == "success":
        import webview
        webview.create_window("Edge Artifacts", result["report_path"])
        webview.start() 