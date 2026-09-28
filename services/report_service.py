"""Forensic report generation.

The report is built in two layers:

1. A deterministic layer that parses the JSON produced by the memory analysis
   pipeline (Volatility output, VirusTotal look-ups, dumped file hashes) and
   turns it into structured findings and Markdown tables. This always works,
   even offline.
2. An optional LLM layer that writes the narrative sections (executive
   summary, propagation analysis, recommendations) from those findings. It uses
   any OpenAI-compatible chat completions endpoint (Together AI by default) and
   is enabled by setting ``LLM_API_KEY`` (or ``TOGETHER_API_KEY``).

The previous implementation depended on llama-index, sentence-transformers and
torch (several gigabytes) and embedded an API key in the source code.
"""
import ipaddress
import json
import os
from datetime import datetime
from random import randint

import requests

from config import config

DEFAULT_API_BASE = "https://api.together.xyz/v1"
DEFAULT_MODEL = "meta-llama/Llama-3.3-70B-Instruct-Turbo"

SUSPICIOUS_PROTECTIONS = ("PAGE_EXECUTE_READWRITE", "PAGE_EXECUTE_WRITECOPY")


def _load_json(path: str):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def classify_ip(value: str) -> str:
    """Return 'public', 'private', 'local' or 'n/a' for a textual address."""
    if not value or value in ("*", "-", "0.0.0.0", "::", "N/A"):
        return "n/a"
    try:
        address = ipaddress.ip_address(value.strip("[]"))
    except ValueError:
        return "n/a"
    if address.is_loopback or address.is_unspecified or address.is_link_local or address.is_multicast:
        return "local"
    if address.is_private or address.is_reserved:
        return "private"
    return "public"


class ReportService:
    def __init__(self, memory_analysis_dir: str, case_info: dict | None = None, evidence: list[dict] | None = None):
        self.memory_analysis_dir = memory_analysis_dir
        self.case_info = case_info or {}
        self.evidence = evidence or []
        self.llm_api_key = os.getenv("LLM_API_KEY") or os.getenv("TOGETHER_API_KEY")
        self.llm_api_base = os.getenv("LLM_API_BASE", DEFAULT_API_BASE).rstrip("/")
        self.llm_model = os.getenv("LLM_MODEL", DEFAULT_MODEL)
        self.llm_used = False
        self.llm_error = None

    # ------------------------------------------------------------------ data
    def load_data(self) -> dict:
        folder = self.memory_analysis_dir
        data = {
            "malfind": _load_json(os.path.join(folder, "malfind.json")) or [],
            "pslist": _load_json(os.path.join(folder, "pslist.json")) or [],
            "netscan": _load_json(os.path.join(folder, "netscan.json")) or [],
            "filtered_netscan": _load_json(os.path.join(folder, "filtered_netscan.json")) or {},
            "cmdline": _load_json(os.path.join(folder, "cmdline.json")) or [],
            "wininfo": _load_json(os.path.join(folder, "wininfo.json")) or [],
            "virustotal": _load_json(os.path.join(folder, "virustotal_results.json")),
            "virustotal_ip": _load_json(os.path.join(folder, "virustotal_ip_results.json")) or [],
            "dumped_files": _load_json(os.path.join(folder, "dumped_memory_features.json")) or [],
        }
        vt = data["virustotal"]
        if isinstance(vt, dict):
            vt = [vt]
        data["virustotal"] = vt or []
        return data

    def build_findings(self, data: dict | None = None) -> dict:
        data = data or self.load_data()

        processes = {}
        children = {}
        for proc in data["pslist"]:
            pid = str(proc.get("PID", ""))
            processes[pid] = proc
            children.setdefault(str(proc.get("PPID", "")), []).append(pid)

        cmdlines = {str(item.get("PID", "")): item.get("Args", item.get("CommandLine", "")) for item in data["cmdline"]}

        suspicious = {}
        for region in data["malfind"]:
            pid = str(region.get("PID", ""))
            indicators = []
            protection = region.get("Protection", "")
            if any(p in protection for p in SUSPICIOUS_PROTECTIONS):
                indicators.append(protection)
            notes = region.get("Notes", "")
            if notes and notes not in ("N/A", ""):
                indicators.append(notes)
            hexdump = region.get("Hexdump") or []
            if hexdump and "4d 5a" in hexdump[0].lower() and "MZ header" not in indicators:
                indicators.append("MZ header")
            entry = suspicious.setdefault(pid, {
                "pid": pid,
                "process": region.get("Process", processes.get(pid, {}).get("ImageFileName", "Unknown")),
                "ppid": str(processes.get(pid, {}).get("PPID", "N/A")),
                "children": children.get(pid, []),
                "indicators": [],
                "regions": 0,
                "cmdline": cmdlines.get(pid, ""),
            })
            entry["regions"] += 1
            for indicator in indicators:
                if indicator not in entry["indicators"]:
                    entry["indicators"].append(indicator)

        # Network connections: flatten either raw netscan or the grouped file.
        connections = []
        if data["netscan"]:
            for conn in data["netscan"]:
                connections.append({
                    "proto": conn.get("Proto", conn.get("protocol", "")),
                    "local": f"{conn.get('LocalAddr', '')}:{conn.get('LocalPort', '')}",
                    "remote_ip": str(conn.get("ForeignAddr", "")),
                    "remote_port": str(conn.get("ForeignPort", "")),
                    "state": conn.get("State", ""),
                    "pid": str(conn.get("PID", conn.get("pid", ""))),
                    "owner": conn.get("Owner", ""),
                })
        elif data["filtered_netscan"]:
            for group in data["filtered_netscan"].get("GroupedConnections", []):
                for conn in group.get("Connections", []):
                    connections.append({
                        "proto": conn.get("protocol", ""),
                        "local": f"{conn.get('LocalAddr', '')}:{conn.get('LocalPort', '')}",
                        "remote_ip": str(conn.get("ForeignAddr", "")),
                        "remote_port": str(conn.get("ForeignPort", "")),
                        "state": conn.get("State", ""),
                        "pid": str(conn.get("pid", "")),
                        "owner": group.get("Owner", ""),
                    })

        vt_ip_lookup = {item.get("ip"): item for item in data["virustotal_ip"] if isinstance(item, dict)}
        network_iocs = []
        seen = set()
        for conn in connections:
            kind = classify_ip(conn["remote_ip"])
            if kind != "public":
                continue
            key = (conn["remote_ip"], conn["remote_port"], conn["pid"])
            if key in seen:
                continue
            seen.add(key)
            conn["classification"] = kind
            conn["suspicious_process"] = conn["pid"] in suspicious
            vt_info = vt_ip_lookup.get(conn["remote_ip"])
            conn["vt_malicious"] = vt_info.get("malicious", 0) if vt_info else None
            network_iocs.append(conn)
        network_iocs.sort(key=lambda c: (not c["suspicious_process"], -(c["vt_malicious"] or 0)))

        malicious_binaries = []
        for result in data["virustotal"]:
            if not isinstance(result, dict):
                continue
            detections = result.get("virustotal_detected", 0) or 0
            total = result.get("virustotal_total", 0) or 0
            malicious_binaries.append({
                "file": result.get("filename", "Unknown"),
                "sha256": result.get("sha256", ""),
                "md5": result.get("md5", ""),
                "pid": self._pid_from_path(result.get("full_path", "") or result.get("path", "")),
                "detections": detections,
                "total": total,
                "status": result.get("malware_status", "Unknown"),
                "signatures": self._top_signatures(result),
            })
        malicious_binaries.sort(key=lambda b: -b["detections"])

        iocs = {
            "hashes": sorted({b["sha256"] for b in malicious_binaries if b["sha256"] and b["detections"] > 0}),
            "files": sorted({b["file"] for b in malicious_binaries if b["detections"] > 0}),
            "ips": sorted({c["remote_ip"] for c in network_iocs if c["suspicious_process"] or (c["vt_malicious"] or 0) > 0}),
            "processes": sorted({s["process"] for s in suspicious.values()}),
        }

        system = {item.get("Variable"): item.get("Value") for item in data["wininfo"] if isinstance(item, dict)}

        return {
            "suspicious_processes": sorted(suspicious.values(), key=lambda s: int(s["pid"]) if s["pid"].isdigit() else 0),
            "malicious_binaries": malicious_binaries,
            "network_iocs": network_iocs,
            "public_connection_count": len(network_iocs),
            "total_connections": len(connections),
            "process_count": len(processes),
            "dumped_file_count": len(data["dumped_files"]),
            "iocs": iocs,
            "system": system,
            "files_used": [name for name in sorted(os.listdir(self.memory_analysis_dir)) if name.endswith(".json")]
            if os.path.isdir(self.memory_analysis_dir) else [],
        }

    @staticmethod
    def _pid_from_path(path: str) -> str:
        for part in path.replace("/", "\\").split("\\"):
            if part.upper().startswith("PID_"):
                return part[4:]
        return "N/A"

    @staticmethod
    def _top_signatures(result: dict, limit: int = 3) -> str:
        detections = result.get("detections") or result.get("engines") or {}
        names = []
        if isinstance(detections, dict):
            for engine, verdict in detections.items():
                if isinstance(verdict, dict):
                    verdict = verdict.get("result")
                if verdict:
                    names.append(f"{engine}: {verdict}")
        elif isinstance(detections, list):
            names = [str(item) for item in detections]
        return "; ".join(names[:limit]) if names else "N/A"

    # -------------------------------------------------------------- markdown
    def render_markdown(self, findings: dict, narrative: dict | None = None) -> str:
        narrative = narrative or {}
        case_id = self.case_info.get("number") or f"DFIR-{randint(1000, 9999)}"
        case_name = self.case_info.get("name", "")
        examiner = self.case_info.get("scan_by", "")
        today = datetime.today().strftime("%Y-%m-%d %H:%M")
        generator = f"{self.llm_model} via {self.llm_api_base}" if self.llm_used else "Anubis rule-based engine (offline)"

        lines = [
            "# Digital Forensics Memory Investigation Report",
            "",
            f"**Case ID:** {case_id}  ",
            f"**Case name:** {case_name or 'N/A'}  ",
            f"**Examiner:** {examiner or 'N/A'}  ",
            f"**Generated:** {today}  ",
            f"**Generated by:** {generator}  ",
            f"**Evidence source:** `{self.memory_analysis_dir}`",
            "",
            "## 1. Executive Summary",
            "",
            narrative.get("executive_summary") or self._default_summary(findings),
            "",
            "## 2. Suspicious Processes Overview",
            "",
        ]

        if findings["suspicious_processes"]:
            lines += ["| PID | Process | Parent PID | Child PIDs | Injection Indicators | Regions | Command line |",
                      "|-----|---------|------------|------------|----------------------|---------|--------------|"]
            for proc in findings["suspicious_processes"]:
                lines.append(
                    f"| {proc['pid']} | {proc['process']} | {proc['ppid']} | {', '.join(proc['children']) or '-'} | "
                    f"{', '.join(proc['indicators']) or '-'} | {proc['regions']} | {self._cell(proc['cmdline'])} |")
        else:
            lines.append("No memory injection indicators were found by malfind.")

        lines += ["", "## 3. Malicious Binaries (VirusTotal Analysis)", ""]
        if findings["malicious_binaries"]:
            lines += ["| File | SHA256 | PID | Detections | Status | Top signatures |",
                      "|------|--------|-----|------------|--------|----------------|"]
            for binary in findings["malicious_binaries"]:
                lines.append(f"| {self._cell(binary['file'])} | `{binary['sha256'][:16]}…` | {binary['pid']} | "
                             f"{binary['detections']}/{binary['total']} | {binary['status']} | {self._cell(binary['signatures'])} |")
        else:
            lines.append("No VirusTotal results are available for the dumped files.")

        lines += ["", "## 4. Network Indicators of Compromise", ""]
        if findings["network_iocs"]:
            lines += ["| Remote IP | Port | Protocol | State | PID | Process | Linked to injection | VT malicious |",
                      "|-----------|------|----------|-------|-----|---------|---------------------|--------------|"]
            for conn in findings["network_iocs"]:
                vt = "n/a" if conn["vt_malicious"] is None else str(conn["vt_malicious"])
                lines.append(f"| {conn['remote_ip']} | {conn['remote_port']} | {conn['proto']} | {conn['state']} | "
                             f"{conn['pid']} | {conn['owner']} | {'YES' if conn['suspicious_process'] else 'no'} | {vt} |")
            lines.append("")
            lines.append(f"{findings['public_connection_count']} connection(s) to public addresses out of "
                         f"{findings['total_connections']} total sockets.")
        else:
            lines.append("No connections to public IP addresses were found.")

        lines += ["", "## 5. Process Relationship Graph Summary", "",
                  narrative.get("relationships") or self._default_relationships(findings),
                  "", "## 6. Extracted Indicators of Compromise (IOCs)", ""]
        iocs = findings["iocs"]
        lines.append(f"- **Processes:** {', '.join(iocs['processes']) or 'none'}")
        lines.append(f"- **File names:** {', '.join(iocs['files']) or 'none'}")
        lines.append(f"- **SHA256 hashes:** {', '.join(f'`{h}`' for h in iocs['hashes']) or 'none'}")
        lines.append(f"- **IP addresses:** {', '.join(iocs['ips']) or 'none'}")

        lines += ["", "## 7. Analyst Recommendations", "",
                  narrative.get("recommendations") or self._default_recommendations(findings),
                  "", "## 8. Appendix", ""]
        system = findings["system"]
        if system:
            lines.append("**System information (Volatility windows.info):**")
            lines.append("")
            for key in ("NtMajorVersion", "NtMinorVersion", "Major/Minor", "Is64Bit", "KeNumberProcessors", "SystemTime", "NtSystemRoot"):
                if key in system:
                    lines.append(f"- {key}: {system[key]}")
            lines.append("")
        lines.append("**Data files used:**")
        lines.append("")
        for name in findings["files_used"]:
            lines.append(f"- `{name}`")
        if self.evidence:
            lines += ["", "**Evidence items in case:**", ""]
            for item in self.evidence:
                names = ", ".join(f["name"] for f in item.get("files", []))
                lines.append(f"- {item.get('timestamp', '')} — {item.get('type', '')}: {names}")
        if self.llm_error:
            lines += ["", f"_LLM narrative unavailable: {self.llm_error}_"]
        return "\n".join(lines) + "\n"

    @staticmethod
    def _cell(text: str, limit: int = 60) -> str:
        text = str(text or "").replace("|", "\\|").replace("\n", " ")
        return text if len(text) <= limit else text[: limit - 1] + "…"

    def _default_summary(self, findings: dict) -> str:
        parts = [f"The memory image contained {findings['process_count']} processes."]
        suspicious = findings["suspicious_processes"]
        if suspicious:
            names = ", ".join(f"{s['process']} (PID {s['pid']})" for s in suspicious)
            parts.append(f"Malfind flagged {len(suspicious)} process(es) with injected or executable private memory: {names}.")
        else:
            parts.append("Malfind did not flag any process.")
        detected = [b for b in findings["malicious_binaries"] if b["detections"] > 0]
        if detected:
            parts.append(f"VirusTotal reported {len(detected)} malicious file(s); the highest detection ratio was "
                         f"{detected[0]['detections']}/{detected[0]['total']} for {detected[0]['file']}.")
        elif findings["malicious_binaries"]:
            parts.append("None of the dumped files were detected by VirusTotal.")
        linked = [c for c in findings["network_iocs"] if c["suspicious_process"]]
        if linked:
            ips = ", ".join(sorted({c['remote_ip'] for c in linked}))
            parts.append(f"Suspicious processes communicated with public addresses: {ips}.")
        elif findings["network_iocs"]:
            parts.append(f"{findings['public_connection_count']} connection(s) to public addresses were observed but none belong to a flagged process.")
        return " ".join(parts)

    def _default_relationships(self, findings: dict) -> str:
        if not findings["suspicious_processes"]:
            return "No suspicious parent/child chains were identified."
        lines = []
        for proc in findings["suspicious_processes"]:
            chain = f"{proc['ppid']} → {proc['process']} ({proc['pid']})"
            if proc["children"]:
                chain += f" → children {', '.join(proc['children'])}"
            related = [c["remote_ip"] for c in findings["network_iocs"] if c["pid"] == proc["pid"]]
            if related:
                chain += f"; network: {', '.join(sorted(set(related)))}"
            lines.append(f"- {chain}")
        return "\n".join(lines)

    def _default_recommendations(self, findings: dict) -> str:
        recs = []
        if findings["suspicious_processes"]:
            recs.append("Isolate the host and terminate the flagged processes after preserving the memory image.")
            recs.append("Dump and reverse-engineer the injected regions (see malfind output) to identify the malware family.")
        if findings["iocs"]["ips"]:
            recs.append("Block the listed IP addresses at the perimeter and search proxy/firewall logs for other hosts contacting them.")
        if findings["iocs"]["hashes"]:
            recs.append("Search the estate for the listed SHA256 hashes and quarantine matching files.")
        recs.append("Correlate the findings with registry (UserAssist, Run keys), SRUM and browser artifacts collected in this case.")
        recs.append("Preserve all evidence files with their hashes recorded in the case evidence folder.")
        return "\n".join(f"{i}. {r}" for i, r in enumerate(recs, 1))

    # ------------------------------------------------------------------- llm
    def _call_llm(self, findings: dict) -> dict | None:
        if not self.llm_api_key:
            self.llm_error = "no LLM_API_KEY / TOGETHER_API_KEY configured"
            return None
        compact = {
            "suspicious_processes": findings["suspicious_processes"],
            "malicious_binaries": findings["malicious_binaries"][:15],
            "network_iocs": findings["network_iocs"][:30],
            "iocs": findings["iocs"],
            "process_count": findings["process_count"],
            "system": findings["system"],
        }
        prompt = (
            "You are a digital forensics expert writing part of a memory investigation report. "
            "Use ONLY the JSON findings below; never invent PIDs, hashes or IPs. "
            "Return a JSON object with exactly three string fields written in Markdown: "
            "\"executive_summary\" (one paragraph), \"relationships\" (bullet list describing parent/child "
            "chains and which processes talk to which IPs), \"recommendations\" (numbered list of containment "
            "and follow-up steps). If a section has no data say so explicitly.\n\nFINDINGS:\n"
            + json.dumps(compact, indent=1)
        )
        try:
            response = requests.post(
                f"{self.llm_api_base}/chat/completions",
                headers={"Authorization": f"Bearer {self.llm_api_key}", "Content-Type": "application/json"},
                json={
                    "model": self.llm_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "max_tokens": 1500,
                },
                timeout=config.api.timeout * 3,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        except (requests.RequestException, KeyError, ValueError) as error:
            self.llm_error = f"{error}"
            return None

        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
        try:
            parsed = json.loads(text)
        except ValueError:
            start, end = text.find("{"), text.rfind("}")
            if start == -1 or end == -1:
                self.llm_error = "model did not return JSON"
                return None
            try:
                parsed = json.loads(text[start:end + 1])
            except ValueError:
                self.llm_error = "model returned invalid JSON"
                return None
        if not isinstance(parsed, dict):
            self.llm_error = "unexpected model output"
            return None
        self.llm_used = True
        return {key: str(value) for key, value in parsed.items() if value}

    # ------------------------------------------------------------------ main
    def generate_report(self, progress=None) -> str:
        def report(message):
            if progress:
                progress(message)

        report("Loading analysis data...")
        data = self.load_data()
        report("Correlating processes, binaries and network connections...")
        findings = self.build_findings(data)
        narrative = None
        if self.llm_api_key:
            report(f"Asking {self.llm_model} for the narrative sections...")
            narrative = self._call_llm(findings)
        report("Rendering Markdown...")
        return self.render_markdown(findings, narrative)
