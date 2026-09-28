"""Helpers for recording evidence items inside a case folder.

Each acquisition writes a small JSON descriptor into ``<case>/evidence`` so the
GUI (and the final report) can list what was collected, when, and where it is.
"""
import hashlib
import json
import os
import re
from datetime import datetime

from utils.paths import CASE_EVIDENCE_SUBDIR, case_subdir


def sha256_of_file(path: str, chunk_size: int = 1024 * 1024) -> str | None:
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(chunk_size), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def human_size(num_bytes: int | None) -> str:
    if num_bytes is None:
        return "Unknown"
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{num_bytes} B"


def record_evidence(case_path: str, files: list[str], evidence_type: str, source: str = "", notes: str = "",
                    compute_hashes: bool = True) -> str:
    """Write an evidence descriptor JSON and return its path."""
    evidence_dir = case_subdir(case_path, CASE_EVIDENCE_SUBDIR)
    items = []
    for file_path in files:
        entry = {"path": file_path, "name": os.path.basename(file_path)}
        if os.path.isfile(file_path):
            entry["size"] = os.path.getsize(file_path)
            if compute_hashes:
                entry["sha256"] = sha256_of_file(file_path)
        items.append(entry)

    descriptor = {
        "type": evidence_type,
        "source": source,
        "notes": notes,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "files": items,
    }
    numbers = [0]
    for name in os.listdir(evidence_dir):
        match = re.fullmatch(r"evidence_(\d+)\.json", name)
        if match:
            numbers.append(int(match.group(1)))
    descriptor_path = os.path.join(evidence_dir, f"evidence_{max(numbers) + 1}.json")
    with open(descriptor_path, "w", encoding="utf-8") as handle:
        json.dump(descriptor, handle, indent=2)
    return descriptor_path


def list_evidence(case_path: str) -> list[dict]:
    """Return all evidence descriptors of a case, oldest first."""
    evidence_dir = os.path.join(case_path, CASE_EVIDENCE_SUBDIR)
    if not os.path.isdir(evidence_dir):
        return []
    descriptors = []
    for name in sorted(os.listdir(evidence_dir)):
        if not (name.startswith("evidence_") and name.endswith(".json")):
            continue
        try:
            with open(os.path.join(evidence_dir, name), "r", encoding="utf-8") as handle:
                data = json.load(handle)
            data["_descriptor"] = name
            # Older descriptors stored a plain list of paths.
            if data.get("files") and isinstance(data["files"][0], str):
                data["files"] = [{"path": p, "name": os.path.basename(p)} for p in data["files"]]
            descriptors.append(data)
        except (OSError, ValueError):
            continue
    return descriptors


def load_case_info(case_path: str) -> dict:
    info_path = os.path.join(case_path, "info.json")
    try:
        with open(info_path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}
