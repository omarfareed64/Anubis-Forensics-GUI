"""Tests for re-checking dumped files on VirusTotal. No network access is used."""
import json
import os
import tempfile
import unittest

from services.memory_analyzer import (EMPTY_SHA256, check_dumped_files_on_virustotal,
                                      select_files_for_virustotal)


class FakeVirusTotal:
    """Stands in for VirusTotalClient and records which hashes were requested."""

    def __init__(self, verdicts):
        self.verdicts = verdicts
        self.requested = []
        self.delay_seconds = 0

    def file_report(self, sha256):
        self.requested.append(sha256)
        detected = self.verdicts.get(sha256, 0)
        return {"virustotal_detected": detected, "virustotal_total": 70, "virustotal_scan_date": "2026-01-01 00:00:00",
                "malware_status": "Malicious" if detected else "Clean", "detections": {}}


def write_json(folder, name, data):
    with open(os.path.join(folder, name), "w", encoding="utf-8") as handle:
        json.dump(data, handle)


class VirusTotalFileSelectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = self.tmp.name
        write_json(self.folder, "virustotal_results.json", {
            "filename": "file.ImageSectionObject.oneetx.exe.img", "full_path": "x", "md5": "m1",
            "sha256": "a" * 64, "file_size": 1000, "virustotal_detected": 0, "virustotal_total": 0,
            "malware_status": "Clean"})
        write_json(self.folder, "dumped_memory_features.json", [
            {"file_name": "dumpfiles.json", "path": "p", "sha256": "b" * 64, "size": 50},
            {"file_name": "empty.mum.img", "path": "p", "sha256": EMPTY_SHA256, "size": 0},
            {"file_name": "big.dat", "path": "p", "sha256": "c" * 64, "size": 900000},
            {"file_name": "winhttp.dll.img", "path": "p", "sha256": "d" * 64, "size": 700000},
            {"file_name": "duplicate.exe.img", "path": "p", "sha256": "a" * 64, "size": 1000},
        ])

    def tearDown(self):
        self.tmp.cleanup()

    def test_selection_skips_json_empty_and_duplicates_and_orders_by_importance(self):
        names = [entry["file_name"] for entry in select_files_for_virustotal(self.folder)]
        self.assertEqual(names, ["file.ImageSectionObject.oneetx.exe.img", "winhttp.dll.img", "big.dat"])

    def test_selection_respects_lookup_limit(self):
        self.assertEqual(len(select_files_for_virustotal(self.folder, max_lookups=2)), 2)

    def test_results_are_saved_most_detected_first(self):
        client = FakeVirusTotal({"a" * 64: 37})
        merged = check_dumped_files_on_virustotal(self.folder, client)

        self.assertEqual(len(client.requested), 3)
        self.assertEqual(merged[0]["sha256"], "a" * 64)
        self.assertEqual(merged[0]["virustotal_detected"], 37)
        with open(os.path.join(self.folder, "virustotal_results.json"), encoding="utf-8") as handle:
            saved = json.load(handle)
        self.assertEqual(saved, merged)


if __name__ == "__main__":
    unittest.main()
