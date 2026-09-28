"""Browser artifact extraction (history, downloads, cookies, bookmarks, logins).

Works on a local profile folder, on auto-detected profiles of the examiner's
machine, or on a remote host through the administrative ``C$`` share. The
Chromium family (Edge, Chrome, Brave, Opera) and Firefox are supported.
"""
import html
import json
import logging
import os
import shutil
import sqlite3
import subprocess
import tempfile
from datetime import datetime

from utils.paths import NO_WINDOW, PSEXEC_EXE

logger = logging.getLogger(__name__)

CHROMIUM_PROFILES = {
    "Edge": r"AppData\Local\Microsoft\Edge\User Data\Default",
    "Chrome": r"AppData\Local\Google\Chrome\User Data\Default",
    "Brave": r"AppData\Local\BraveSoftware\Brave-Browser\User Data\Default",
    "Opera": r"AppData\Roaming\Opera Software\Opera Stable\Default",
}
FIREFOX_PROFILES_ROOT = r"AppData\Roaming\Mozilla\Firefox\Profiles"
CHROMIUM_PROCESSES = {"Edge": "msedge.exe", "Chrome": "chrome.exe", "Brave": "brave.exe", "Opera": "opera.exe"}

CHROMIUM_QUERIES = {
    "Browser History": ("History", "SELECT url, title, visit_count, datetime(last_visit_time/1000000-11644473600,'unixepoch') AS last_visit "
                                   "FROM urls ORDER BY last_visit_time DESC LIMIT 500"),
    "File Downloads": ("History", "SELECT target_path, tab_url AS url, total_bytes, datetime(start_time/1000000-11644473600,'unixepoch') AS start_time, "
                                  "datetime(end_time/1000000-11644473600,'unixepoch') AS end_time FROM downloads ORDER BY start_time DESC LIMIT 200"),
    "Search Terms": ("History", "SELECT term, datetime(u.last_visit_time/1000000-11644473600,'unixepoch') AS last_visit, u.url "
                                "FROM keyword_search_terms k JOIN urls u ON u.id = k.url_id ORDER BY u.last_visit_time DESC LIMIT 200"),
    "Cookies": ("Cookies", "SELECT host_key, name, path, datetime(creation_utc/1000000-11644473600,'unixepoch') AS created, "
                           "datetime(last_access_utc/1000000-11644473600,'unixepoch') AS last_access, is_secure, is_httponly FROM cookies "
                           "ORDER BY last_access_utc DESC LIMIT 500"),
    "Saved Logins": ("Login Data", "SELECT origin_url, username_value, datetime(date_created/1000000-11644473600,'unixepoch') AS created, "
                                   "datetime(date_last_used/1000000-11644473600,'unixepoch') AS last_used FROM logins ORDER BY date_last_used DESC"),
}
CHROMIUM_FILES = {"History": "History", "Cookies": os.path.join("Network", "Cookies"), "Login Data": "Login Data", "Bookmarks": "Bookmarks"}

FIREFOX_QUERIES = {
    "Browser History": ("places.sqlite", "SELECT url, title, visit_count, datetime(last_visit_date/1000000,'unixepoch') AS last_visit "
                                         "FROM moz_places WHERE last_visit_date IS NOT NULL ORDER BY last_visit_date DESC LIMIT 500"),
    "Bookmarks": ("places.sqlite", "SELECT b.title, p.url, datetime(b.dateAdded/1000000,'unixepoch') AS added FROM moz_bookmarks b "
                                   "JOIN moz_places p ON p.id = b.fk ORDER BY b.dateAdded DESC LIMIT 500"),
    "Cookies": ("cookies.sqlite", "SELECT host, name, path, datetime(creationTime/1000000,'unixepoch') AS created, "
                                  "datetime(lastAccessed/1000000,'unixepoch') AS last_access, isSecure, isHttpOnly FROM moz_cookies "
                                  "ORDER BY lastAccessed DESC LIMIT 500"),
    "File Downloads": ("places.sqlite", "SELECT p.url, a.content AS destination, datetime(a.dateAdded/1000000,'unixepoch') AS added "
                                        "FROM moz_annos a JOIN moz_places p ON p.id = a.place_id JOIN moz_anno_attributes n ON n.id = a.anno_attribute_id "
                                        "WHERE n.name = 'downloads/destinationFileURI' ORDER BY a.dateAdded DESC LIMIT 200"),
}


# --------------------------------------------------------------------- report
def generate_html_report(sections: dict, title: str = "Browser Artifacts") -> str:
    def cell(content, is_url=False):
        text = str(content if content is not None else "")
        safe = html.escape(text)
        display = safe if len(text) <= 100 else safe[:97] + "..."
        if is_url and text.startswith(("http://", "https://")):
            return f'<td title="{safe}"><a href="{safe}" target="_blank">{display}</a></td>'
        return f'<td title="{safe}">{display}</td>'

    css = """
    <style>
        body { font-family: 'Segoe UI', Tahoma, sans-serif; background-color: #eef2f5; color: #333; margin: 0; padding: 20px; }
        .container { max-width: 1500px; margin: auto; background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
        h1 { color: #F57C1F; border-bottom: 3px solid #23292f; padding-bottom: 10px; margin-bottom: 6px; }
        h2 { color: #23292f; margin-top: 30px; }
        .meta { color: #666; margin-bottom: 20px; }
        details { margin-bottom: 15px; border: 1px solid #ddd; border-radius: 8px; overflow: hidden; }
        details[open] { border-color: #F57C1F; }
        summary { font-size: 1.15em; font-weight: 600; padding: 14px 20px; background-color: #fcfcfc; cursor: pointer; }
        summary:hover { background-color: #f5f5f5; }
        .count { color: #F57C1F; font-weight: normal; font-size: 0.9em; margin-left: 10px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 8px 14px; text-align: left; border-bottom: 1px solid #e0e0e0; max-width: 420px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 0.92em; }
        th { background-color: #23292f; color: white; position: sticky; top: 0; }
        tr:nth-child(even) { background-color: #f9f9f9; }
        tr:hover { background-color: #f0f0f0; }
        a { color: #007bff; text-decoration: none; }
        .empty { text-align: center; padding: 20px; color: #777; }
    </style>
    """
    body = ""
    for browser, artifacts in sections.items():
        body += f"<h2>{html.escape(browser)}</h2>"
        for name, (headers, rows) in artifacts.items():
            body += f"<details><summary>{html.escape(name)} <span class='count'>({len(rows)} items)</span></summary><table>"
            body += "<tr>" + "".join(f"<th>{html.escape(str(h))}</th>" for h in headers) + "</tr>"
            if not rows:
                body += f"<tr><td class='empty' colspan='{max(len(headers), 1)}'>No artifacts found.</td></tr>"
            for row in rows:
                body += "<tr>" + "".join(cell(col, is_url="url" in str(headers[i]).lower()) for i, col in enumerate(row)) + "</tr>"
            body += "</table></details>"
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return (f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title>{css}</head><body>"
            f"<div class='container'><h1>{html.escape(title)}</h1><div class='meta'>Generated {generated} by Anubis Forensics</div>"
            f"{body}</div></body></html>")


# ------------------------------------------------------------------ helpers
def query_sqlite(db_path: str, query: str):
    if not os.path.isfile(db_path):
        return [], []
    try:
        connection = sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True)
        cursor = connection.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        headers = [description[0] for description in cursor.description]
        connection.close()
        return headers, rows
    except sqlite3.Error as error:
        logger.warning("Query failed on %s: %s", db_path, error)
        return [], []


def parse_chromium_bookmarks(path: str):
    rows = []
    if not os.path.isfile(path):
        return rows

    def walk(node, folder):
        if node.get("type") == "url":
            rows.append((node.get("name", ""), node.get("url", ""), folder, _chromium_time(node.get("date_added"))))
        for child in node.get("children", []) or []:
            walk(child, f"{folder}/{node.get('name', '')}".strip("/"))

    try:
        with open(path, "r", encoding="utf-8") as handle:
            roots = json.load(handle).get("roots", {})
        for section, node in roots.items():
            if isinstance(node, dict):
                walk(node, section)
    except (OSError, ValueError) as error:
        logger.warning("Failed to parse bookmarks: %s", error)
    return rows


def _chromium_time(value):
    try:
        return datetime.utcfromtimestamp(int(value) / 1_000_000 - 11644473600).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OverflowError):
        return ""


def _copy_if_exists(source: str, destination: str) -> bool:
    if os.path.isfile(source):
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        try:
            shutil.copy2(source, destination)
            return True
        except OSError as error:
            logger.warning("Could not copy %s: %s", source, error)
    return False


# --------------------------------------------------------------- extraction
def extract_chromium_profile(profile_dir: str, work_dir: str) -> dict:
    """Copy the databases of a Chromium profile to work_dir and query them."""
    copied = {}
    for key, relative in CHROMIUM_FILES.items():
        target = os.path.join(work_dir, key.replace(" ", "_"))
        if _copy_if_exists(os.path.join(profile_dir, relative), target):
            copied[key] = target
        elif key == "Cookies" and _copy_if_exists(os.path.join(profile_dir, "Cookies"), target):
            copied[key] = target  # older Chromium versions
    artifacts = {}
    for name, (db_key, query) in CHROMIUM_QUERIES.items():
        db_path = copied.get(db_key)
        artifacts[name] = query_sqlite(db_path, query) if db_path else ([], [])
    artifacts["Bookmarks"] = (["Title", "URL", "Folder", "Added"], parse_chromium_bookmarks(copied.get("Bookmarks", "")))
    return artifacts


def extract_firefox_profile(profile_dir: str, work_dir: str) -> dict:
    copied = {}
    for name in ("places.sqlite", "cookies.sqlite"):
        target = os.path.join(work_dir, name)
        if _copy_if_exists(os.path.join(profile_dir, name), target):
            copied[name] = target
    artifacts = {}
    for name, (db_name, query) in FIREFOX_QUERIES.items():
        db_path = copied.get(db_name)
        artifacts[name] = query_sqlite(db_path, query) if db_path else ([], [])
    return artifacts


def find_profiles(user_root: str) -> list[tuple[str, str]]:
    """Return (browser, profile_dir) pairs that exist under a user folder."""
    found = []
    for browser, relative in CHROMIUM_PROFILES.items():
        path = os.path.join(user_root, relative)
        if os.path.isdir(path):
            found.append((browser, path))
    firefox_root = os.path.join(user_root, FIREFOX_PROFILES_ROOT)
    if os.path.isdir(firefox_root):
        for entry in os.listdir(firefox_root):
            profile = os.path.join(firefox_root, entry)
            if os.path.isfile(os.path.join(profile, "places.sqlite")):
                found.append((f"Firefox ({entry})", profile))
    return found


def detect_browser(profile_dir: str) -> str:
    if os.path.isfile(os.path.join(profile_dir, "places.sqlite")):
        return "Firefox"
    lowered = profile_dir.lower()
    for browser in CHROMIUM_PROFILES:
        if browser.lower() in lowered:
            return browser
    return "Chromium"


def extract_profiles(profiles: list[tuple[str, str]], output_dir: str, title: str) -> dict:
    """Extract every (browser, profile_dir) pair and write an HTML report."""
    os.makedirs(output_dir, exist_ok=True)
    work_root = tempfile.mkdtemp(prefix="anubis_web_")
    sections = {}
    try:
        for browser, profile_dir in profiles:
            work_dir = os.path.join(work_root, browser.replace(" ", "_").replace("(", "").replace(")", ""))
            os.makedirs(work_dir, exist_ok=True)
            logger.info("Extracting %s artifacts from %s", browser, profile_dir)
            if browser.startswith("Firefox"):
                sections[browser] = extract_firefox_profile(profile_dir, work_dir)
            else:
                sections[browser] = extract_chromium_profile(profile_dir, work_dir)
            raw_dir = os.path.join(output_dir, "raw", browser.replace(" ", "_"))
            os.makedirs(raw_dir, exist_ok=True)
            for name in os.listdir(work_dir):
                shutil.copy2(os.path.join(work_dir, name), os.path.join(raw_dir, name))
    finally:
        shutil.rmtree(work_root, ignore_errors=True)

    if not sections:
        return {"status": "error", "message": "No browser profiles were found."}

    report_path = os.path.join(output_dir, "Web_Artifacts_Report.html")
    with open(report_path, "w", encoding="utf-8") as handle:
        handle.write(generate_html_report(sections, title))
    summary = {browser: {name: len(rows) for name, (_h, rows) in artifacts.items()} for browser, artifacts in sections.items()}
    with open(os.path.join(output_dir, "summary.json"), "w", encoding="utf-8") as handle:
        json.dump({"generated": datetime.now().isoformat(timespec="seconds"), "profiles": dict(profiles), "counts": summary}, handle, indent=2)
    return {"status": "success", "report_path": report_path, "output_dir": output_dir, "counts": summary}


def extract_local_profile(profile_dir: str, output_dir: str) -> dict:
    browser = detect_browser(profile_dir)
    return extract_profiles([(browser, profile_dir)], output_dir, f"{browser} Artifacts — {profile_dir}")


def extract_local_user(user_root: str | None, output_dir: str) -> dict:
    user_root = user_root or os.path.expanduser("~")
    profiles = find_profiles(user_root)
    if not profiles:
        return {"status": "error", "message": f"No supported browser profiles found under {user_root}"}
    return extract_profiles(profiles, output_dir, f"Browser Artifacts — {os.path.basename(user_root)}")


def extract_all_web_artifacts(remote_ip, domain, username, password, remote_profile=None, output_dir=None,
                              kill_browsers=True) -> dict:
    """Extract browser artifacts of a remote user through the C$ share."""
    remote_profile = remote_profile or username
    remote_share = fr"\\{remote_ip}\C$"
    user_root = fr"{remote_share}\Users\{remote_profile}"
    if not output_dir:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.abspath(f"web_artifacts_{remote_ip.replace('.', '_')}_{stamp}")

    try:
        logger.info("Mounting %s", remote_share)
        subprocess.run(["net", "use", remote_share, password, f"/user:{domain}\\{username}"], check=True,
                       capture_output=True, text=True, creationflags=NO_WINDOW)

        if kill_browsers and os.path.isfile(PSEXEC_EXE):
            processes = " & ".join(f"taskkill /F /IM {exe}" for exe in CHROMIUM_PROCESSES.values()) + " & taskkill /F /IM firefox.exe"
            subprocess.run([PSEXEC_EXE, f"\\\\{remote_ip}", "-accepteula", "-u", f"{domain}\\{username}", "-p", password,
                            "-h", "cmd", "/c", processes], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=NO_WINDOW, timeout=120)

        profiles = find_profiles(user_root)
        if not profiles:
            return {"status": "error", "message": f"No browser profiles found under {user_root}"}
        return extract_profiles(profiles, output_dir, f"Browser Artifacts — {remote_ip} ({remote_profile})")
    except subprocess.CalledProcessError as error:
        return {"status": "error", "message": f"Could not mount {remote_share}: {(error.stderr or error.stdout or '').strip()}"}
    except Exception as error:  # noqa: BLE001
        logger.exception("Web artifact extraction failed")
        return {"status": "error", "message": f"Unexpected error: {error}"}
    finally:
        subprocess.run(["net", "use", remote_share, "/delete", "/y"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=NO_WINDOW)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(extract_local_user(None, os.path.join(tempfile.gettempdir(), "anubis_web_test")))
