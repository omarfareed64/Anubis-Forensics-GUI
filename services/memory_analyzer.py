"""Memory analysis pipeline built on Volatility 3.

Produces the same JSON files the GUI and the report generator consume:

    wininfo.json, pslist.json, cmdline.json, netscan.json, malfind.json,
    userassist.json, filtered_netscan.json, dumped_memory/PID_<n>/...,
    dumped_memory_features.json, virustotal_results.json,
    virustotal_ip_results.json

Volatility is executed as a subprocess (``vol -r json``) so a crash inside a
plugin never takes the GUI down.
"""
import hashlib
import ipaddress
import json
import os
import re
import subprocess
import time
from datetime import datetime

import requests

from utils.paths import NO_WINDOW, venv_script

VOLATILITY_PLUGINS = [
    ("wininfo", "windows.info"),
    ("pslist", "windows.pslist"),
    ("cmdline", "windows.cmdline"),
    ("netscan", "windows.netscan"),
    ("malfind", "windows.malfind"),
    ("userassist", "windows.registry.userassist"),
]

SUSPICIOUS_PROTECTIONS = ("PAGE_EXECUTE_READWRITE", "PAGE_EXECUTE_WRITECOPY")
VT_BASE = "https://www.virustotal.com/api/v3"
IPV4_RE = re.compile(rb"(?<![\d.])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?![\d.])")


def classify_ip(value) -> str:
    if value in (None, "", "*", "-", "0.0.0.0", "::", "N/A"):
        return "n/a"
    try:
        address = ipaddress.ip_address(str(value).strip("[]"))
    except ValueError:
        return "n/a"
    if address.is_loopback or address.is_unspecified or address.is_link_local or address.is_multicast:
        return "local"
    if address.is_private or address.is_reserved:
        return "private"
    return "public"


def load_json(folder: str, name: str):
    path = os.path.join(folder, name if name.endswith(".json") else name + ".json")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def flatten_volatility(rows) -> list:
    """Volatility's JSON renderer nests children under ``__children``; flatten it."""
    flat = []
    stack = list(rows or [])
    while stack:
        row = stack.pop(0)
        if not isinstance(row, dict):
            continue
        children = row.pop("__children", []) or []
        flat.append(row)
        stack = list(children) + stack
    return flat


def build_filtered_netscan(netscan: list) -> dict:
    """Group connections by owning process (same shape as the sample data)."""
    owners = {}
    for conn in netscan:
        key = (conn.get("Owner", "-") or "-", str(conn.get("PID", "-") or "-"))
        owners.setdefault(key, []).append({
            "protocol": conn.get("Proto", ""),
            "State": conn.get("State", "") or "N/A",
            "LocalAddr": str(conn.get("LocalAddr", "")),
            "LocalPort": str(conn.get("LocalPort", "")),
            "ForeignAddr": str(conn.get("ForeignAddr", "")),
            "ForeignPort": str(conn.get("ForeignPort", "")),
            "ForeignClass": classify_ip(conn.get("ForeignAddr")),
            "pid": key[1],
        })
    return {
        "UniqueOwners": [{"Owner": owner, "PID": pid} for owner, pid in owners],
        "GroupedConnections": [{"Owner": owner, "PID": pid, "Connections": conns} for (owner, pid), conns in owners.items()],
    }


def suspicious_pids_from_malfind(malfind: list) -> list[str]:
    pids = []
    for region in malfind or []:
        protection = str(region.get("Protection", ""))
        notes = str(region.get("Notes", ""))
        hexdump = region.get("Hexdump") or []
        first_line = hexdump[0].lower() if hexdump else ""
        if any(p in protection for p in SUSPICIOUS_PROTECTIONS) and ("MZ" in notes or first_line.startswith("4d 5a") or region.get("PrivateMemory") in (1, "1")):
            pid = str(region.get("PID", ""))
            if pid and pid not in pids:
                pids.append(pid)
    return pids


def hash_file(path: str) -> tuple[str, str]:
    md5, sha256 = hashlib.md5(), hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            md5.update(chunk)
            sha256.update(chunk)
    return md5.hexdigest(), sha256.hexdigest()


def collect_dumped_file_features(dumped_dir: str) -> list[dict]:
    features = []
    if not os.path.isdir(dumped_dir):
        return features
    for root, _dirs, files in os.walk(dumped_dir):
        for name in sorted(files):
            path = os.path.join(root, name)
            try:
                md5, sha256 = hash_file(path)
                features.append({
                    "file_name": name,
                    "path": path,
                    "pid": os.path.basename(root)[4:] if os.path.basename(root).upper().startswith("PID_") else "",
                    "md5": md5,
                    "sha256": sha256,
                    "size": os.path.getsize(path),
                })
            except OSError:
                continue
    return features


def scan_dumped_files_for_ips(dumped_dir: str, limit_per_file: int = 200) -> list[dict]:
    """Extract IPv4 strings from dumped memory files and classify them."""
    hits = []
    if not os.path.isdir(dumped_dir):
        return hits
    for root, _dirs, files in os.walk(dumped_dir):
        for name in files:
            if name.endswith(".json"):
                continue
            path = os.path.join(root, name)
            try:
                with open(path, "rb") as handle:
                    data = handle.read()
            except OSError:
                continue
            seen = set()
            for match in IPV4_RE.finditer(data):
                ip = match.group(0).decode("ascii", errors="ignore")
                if ip in seen:
                    continue
                seen.add(ip)
                kind = classify_ip(ip)
                if kind == "public":
                    hits.append({"file": name, "pid": os.path.basename(root), "ip": ip, "classification": kind})
                if len(seen) >= limit_per_file:
                    break
    return hits


# ------------------------------------------------------------------ VirusTotal
class VirusTotalClient:
    def __init__(self, api_key: str | None = None, delay_seconds: float = 15.0):
        self.api_key = api_key or os.getenv("VIRUSTOTAL_API_KEY")
        self.delay_seconds = delay_seconds  # public API: 4 requests / minute
        self._last_call = 0.0

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _get(self, path: str) -> dict | None:
        wait = self.delay_seconds - (time.time() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.time()
        response = requests.get(f"{VT_BASE}/{path}", headers={"x-apikey": self.api_key}, timeout=60)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def file_report(self, sha256: str) -> dict:
        payload = self._get(f"files/{sha256}")
        if not payload:
            return {"virustotal_detected": 0, "virustotal_total": 0, "virustotal_scan_date": "N/A", "malware_status": "Unknown (not in VirusTotal)", "detections": {}}
        attributes = payload.get("data", {}).get("attributes", {})
        stats = attributes.get("last_analysis_stats", {})
        results = attributes.get("last_analysis_results", {})
        detections = {engine: info.get("result") for engine, info in results.items() if info.get("category") == "malicious"}
        total = sum(stats.get(k, 0) for k in ("malicious", "suspicious", "undetected", "harmless"))
        malicious = stats.get("malicious", 0)
        scan_date = attributes.get("last_analysis_date")
        return {
            "virustotal_detected": malicious,
            "virustotal_total": total,
            "virustotal_scan_date": datetime.utcfromtimestamp(scan_date).strftime("%Y-%m-%d %H:%M:%S") if scan_date else "N/A",
            "malware_status": "Malicious" if malicious > 0 else "Clean",
            "detections": detections,
            "popular_threat_label": attributes.get("popular_threat_classification", {}).get("suggested_threat_label", ""),
        }

    def ip_report(self, ip: str) -> dict:
        payload = self._get(f"ip_addresses/{ip}")
        if not payload:
            return {"ip": ip, "malicious": 0, "suspicious": 0, "harmless": 0, "country": "", "as_owner": "", "status": "Unknown"}
        attributes = payload.get("data", {}).get("attributes", {})
        stats = attributes.get("last_analysis_stats", {})
        return {
            "ip": ip,
            "malicious": stats.get("malicious", 0),
            "suspicious": stats.get("suspicious", 0),
            "harmless": stats.get("harmless", 0),
            "country": attributes.get("country", ""),
            "as_owner": attributes.get("as_owner", ""),
            "reputation": attributes.get("reputation", 0),
            "status": "Malicious" if stats.get("malicious", 0) > 0 else "Clean",
        }


EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def select_files_for_virustotal(folder: str, max_lookups: int = 8) -> list[dict]:
    """Pick the dumped files worth looking up on VirusTotal, most important first.

    Sources are the previous VirusTotal results, the dumped file inventory and the
    files actually present in ``dumped_memory``. Empty files, Volatility's JSON
    output and duplicate hashes are skipped. Order: files that were already in
    the VirusTotal list, then executables, then DLLs, then the largest files.
    """
    candidates = {}

    def add(name, path, sha256, md5, size, previous):
        if not sha256 or sha256 == EMPTY_SHA256 or not size or str(name).lower().endswith(".json"):
            return
        entry = candidates.setdefault(sha256, {"file_name": name, "path": path, "sha256": sha256,
                                               "md5": md5 or "", "size": size, "previous": previous})
        entry["previous"] = entry["previous"] or previous
        entry["md5"] = entry["md5"] or md5 or ""

    previous = load_json(folder, "virustotal_results") or []
    if isinstance(previous, dict):
        previous = [previous]
    for item in previous:
        if isinstance(item, dict):
            add(item.get("filename"), item.get("full_path", ""), item.get("sha256"), item.get("md5"),
                item.get("file_size"), True)
    for item in load_json(folder, "dumped_memory_features") or []:
        if isinstance(item, dict):
            add(item.get("file_name"), item.get("path", ""), item.get("sha256"), item.get("md5"), item.get("size"), False)
    for item in collect_dumped_file_features(os.path.join(folder, "dumped_memory")):
        add(item["file_name"], item["path"], item["sha256"], item["md5"], item["size"], False)

    def priority(entry):
        name = str(entry["file_name"]).lower()
        return (not entry["previous"], ".exe" not in name, ".dll" not in name, -int(entry["size"] or 0))

    return sorted(candidates.values(), key=priority)[:max_lookups]


def check_dumped_files_on_virustotal(folder: str, client: "VirusTotalClient", max_lookups: int = 8,
                                     progress=None) -> list[dict]:
    """Look up dumped file hashes on VirusTotal and save ``virustotal_results.json``.

    Only hashes are sent; the files themselves are never uploaded. Earlier results
    for hashes that are not re-checked are kept.
    """
    progress = progress or (lambda message: None)
    selected = select_files_for_virustotal(folder, max_lookups)
    results = []
    for index, entry in enumerate(selected, 1):
        progress(f"VirusTotal {index}/{len(selected)}: {str(entry['file_name'])[:70]} ... (free API: 4 requests/minute)")
        report = client.file_report(entry["sha256"])
        results.append({"filename": entry["file_name"], "full_path": entry["path"], "md5": entry["md5"],
                        "sha256": entry["sha256"], "file_size": entry["size"], **report})
        progress(f"  -> {report['malware_status']} ({report['virustotal_detected']}/{report['virustotal_total']})")

    checked = {item["sha256"] for item in results}
    previous = load_json(folder, "virustotal_results") or []
    if isinstance(previous, dict):
        previous = [previous]
    kept = [item for item in previous if isinstance(item, dict) and item.get("sha256") not in checked]
    merged = sorted(results + kept, key=lambda item: -(item.get("virustotal_detected") or 0))
    with open(os.path.join(folder, "virustotal_results.json"), "w", encoding="utf-8") as handle:
        json.dump(merged, handle, indent=2)
    return merged


# ------------------------------------------------------------------- pipeline
class MemoryAnalyzer:
    def __init__(self, dump_path: str, output_dir: str, progress=None, cancel_check=None):
        self.dump_path = dump_path
        self.output_dir = output_dir
        self.progress = progress or (lambda message: None)
        self.cancel_check = cancel_check or (lambda: False)
        self.vol = venv_script("vol")
        os.makedirs(output_dir, exist_ok=True)

    def _save(self, name: str, data) -> str:
        path = os.path.join(self.output_dir, f"{name}.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, default=str)
        return path

    def run_plugin(self, plugin: str, extra_args: list[str] | None = None, timeout: int = 3600) -> list:
        command = [self.vol, "-q", "-r", "json", "-f", self.dump_path, plugin, *(extra_args or [])]
        self.progress(f"Running {plugin} ...")
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                creationflags=NO_WINDOW, timeout=timeout)
        if result.returncode != 0:
            tail = (result.stderr or result.stdout or "").strip().splitlines()[-3:]
            raise RuntimeError(f"{plugin} failed (exit {result.returncode}): {' | '.join(tail)}")
        text = result.stdout.strip()
        start = text.find("[")
        if start == -1:
            return []
        return flatten_volatility(json.loads(text[start:]))

    def run_all(self, dump_files: bool = True, use_virustotal: bool = True, max_vt_lookups: int = 8) -> dict:
        outputs = {}
        for name, plugin in VOLATILITY_PLUGINS:
            if self.cancel_check():
                raise RuntimeError("Cancelled")
            try:
                rows = self.run_plugin(plugin)
            except (RuntimeError, subprocess.SubprocessError, ValueError) as error:
                self.progress(f"  ✗ {error}")
                rows = []
            outputs[name] = self._save(name, rows)
            self.progress(f"  ✓ {name}: {len(rows)} row(s)")

        netscan = load_json(self.output_dir, "netscan") or []
        filtered = build_filtered_netscan(netscan)
        outputs["filtered_netscan"] = self._save("filtered_netscan", filtered)
        outputs["filtered_userassist"] = self._save("filtered_userassist", [
            row for row in (load_json(self.output_dir, "userassist") or []) if row.get("Count") not in (None, 0, "0")
        ])

        malfind = load_json(self.output_dir, "malfind") or []
        suspicious = suspicious_pids_from_malfind(malfind)
        self.progress(f"Suspicious PIDs from malfind: {', '.join(suspicious) or 'none'}")

        dumped_dir = os.path.join(self.output_dir, "dumped_memory")
        if dump_files and suspicious:
            for pid in suspicious:
                if self.cancel_check():
                    raise RuntimeError("Cancelled")
                pid_dir = os.path.join(dumped_dir, f"PID_{pid}")
                os.makedirs(pid_dir, exist_ok=True)
                try:
                    rows = self.run_plugin("windows.dumpfiles", ["--pid", pid, "-o", pid_dir])
                except (RuntimeError, subprocess.SubprocessError, ValueError) as error:
                    self.progress(f"  ✗ dumpfiles for PID {pid}: {error}")
                    rows = []
                with open(os.path.join(pid_dir, "dumpfiles.json"), "w", encoding="utf-8") as handle:
                    json.dump(rows, handle, indent=2, default=str)
                self.progress(f"  ✓ PID {pid}: {len(rows)} file object(s) dumped")

        features = collect_dumped_file_features(dumped_dir)
        outputs["dumped_memory_features"] = self._save("dumped_memory_features", features)
        self.progress(f"Hashed {len(features)} dumped file(s)")

        vt = VirusTotalClient()
        if use_virustotal and vt.enabled:
            candidates = sorted(features, key=lambda f: (".exe" not in f["file_name"].lower(), -f["size"]))
            candidates = [f for f in candidates if f["size"] > 0][:max_vt_lookups]
            vt_results = []
            for feature in candidates:
                if self.cancel_check():
                    raise RuntimeError("Cancelled")
                self.progress(f"VirusTotal: {feature['file_name'][:60]} ...")
                try:
                    report = vt.file_report(feature["sha256"])
                except requests.RequestException as error:
                    self.progress(f"  ✗ {error}")
                    continue
                vt_results.append({
                    "filename": feature["file_name"], "full_path": feature["path"], "md5": feature["md5"],
                    "sha256": feature["sha256"], "file_size": feature["size"], **report,
                })
                self.progress(f"  → {report['malware_status']} ({report['virustotal_detected']}/{report['virustotal_total']})")
            outputs["virustotal_results"] = self._save("virustotal_results", vt_results)

            public_ips = sorted({
                conn["ForeignAddr"] for group in filtered["GroupedConnections"] if group["PID"] in suspicious
                for conn in group["Connections"] if conn["ForeignClass"] == "public"
            })
            ip_results = []
            for ip in public_ips[:max_vt_lookups]:
                if self.cancel_check():
                    raise RuntimeError("Cancelled")
                self.progress(f"VirusTotal IP: {ip} ...")
                try:
                    ip_results.append(vt.ip_report(ip))
                except requests.RequestException as error:
                    self.progress(f"  ✗ {error}")
            outputs["virustotal_ip_results"] = self._save("virustotal_ip_results", ip_results)
        elif use_virustotal:
            self.progress("VirusTotal skipped: set VIRUSTOTAL_API_KEY in .env to enable look-ups")
            outputs["virustotal_results"] = self._save("virustotal_results", [
                {"filename": f["file_name"], "full_path": f["path"], "md5": f["md5"], "sha256": f["sha256"],
                 "file_size": f["size"], "virustotal_detected": 0, "virustotal_total": 0,
                 "virustotal_scan_date": "N/A", "malware_status": "Not checked"} for f in features
            ])

        self.progress("Memory analysis finished")
        return outputs
