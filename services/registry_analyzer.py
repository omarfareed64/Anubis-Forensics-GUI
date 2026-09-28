"""Registry analysis service.

Acquisition of live hives uses RawCopy (they are locked by the OS); everything
else is done in-process with regipy so that no external console scripts have to
be on the PATH.
"""
import json
import os
import subprocess
from datetime import datetime

from PyQt5.QtCore import QObject, pyqtSignal

from utils.paths import NO_WINDOW, RAWCOPY_EXE, RLA_EXE

try:
    import logging

    from regipy.registry import RegistryHive
    from regipy.plugins.utils import run_relevant_plugins
    from regipy.recovery import apply_transaction_logs as regipy_apply_transaction_logs
    REGIPY_AVAILABLE = True
    # regipy logs every missing key at INFO/WARNING level, which floods the console.
    logging.getLogger("regipy").setLevel(logging.ERROR)
except ImportError:  # pragma: no cover - regipy is a hard requirement but keep the GUI alive
    REGIPY_AVAILABLE = False


SYSTEM_HIVES = {
    "SYSTEM": r"C:\Windows\System32\config\SYSTEM",
    "SYSTEM.LOG1": r"C:\Windows\System32\config\SYSTEM.LOG1",
    "SYSTEM.LOG2": r"C:\Windows\System32\config\SYSTEM.LOG2",
    "SOFTWARE": r"C:\Windows\System32\config\SOFTWARE",
    "SOFTWARE.LOG1": r"C:\Windows\System32\config\SOFTWARE.LOG1",
    "SOFTWARE.LOG2": r"C:\Windows\System32\config\SOFTWARE.LOG2",
    "SAM": r"C:\Windows\System32\config\SAM",
    "SAM.LOG1": r"C:\Windows\System32\config\SAM.LOG1",
    "SAM.LOG2": r"C:\Windows\System32\config\SAM.LOG2",
    "SECURITY": r"C:\Windows\System32\config\SECURITY",
    "SECURITY.LOG1": r"C:\Windows\System32\config\SECURITY.LOG1",
    "SECURITY.LOG2": r"C:\Windows\System32\config\SECURITY.LOG2",
    "Amcache.hve": r"C:\Windows\appcompat\Programs\Amcache.hve",
    "Amcache.hve.LOG1": r"C:\Windows\appcompat\Programs\Amcache.hve.LOG1",
    "Amcache.hve.LOG2": r"C:\Windows\appcompat\Programs\Amcache.hve.LOG2",
    "SRUDB.dat": r"C:\Windows\System32\sru\SRUDB.dat",
}


def user_hives(username: str) -> dict:
    return {
        "NTUSER.DAT": rf"C:\Users\{username}\NTUSER.DAT",
        "NTUSER.DAT.LOG1": rf"C:\Users\{username}\NTUSER.DAT.LOG1",
        "NTUSER.DAT.LOG2": rf"C:\Users\{username}\NTUSER.DAT.LOG2",
        "UsrClass.dat": rf"C:\Users\{username}\AppData\Local\Microsoft\Windows\UsrClass.dat",
        "UsrClass.dat.LOG1": rf"C:\Users\{username}\AppData\Local\Microsoft\Windows\UsrClass.dat.LOG1",
        "UsrClass.dat.LOG2": rf"C:\Users\{username}\AppData\Local\Microsoft\Windows\UsrClass.dat.LOG2",
    }


def rawcopy_file(source_path: str, output_dir: str) -> tuple[bool, str]:
    """Copy a locked file with RawCopy. Requires administrator rights."""
    if not os.path.isfile(RAWCOPY_EXE):
        return False, f"RawCopy.exe not found at {RAWCOPY_EXE}"
    os.makedirs(output_dir, exist_ok=True)
    command = [RAWCOPY_EXE, f"/FileNamePath:{source_path}", f"/OutputPath:{output_dir}"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                creationflags=NO_WINDOW, timeout=600)
    except (subprocess.SubprocessError, OSError) as error:
        return False, str(error)
    expected = os.path.join(output_dir, os.path.basename(source_path))
    if result.returncode == 0 and os.path.isfile(expected):
        return True, expected
    return False, (result.stderr or result.stdout or f"exit code {result.returncode}").strip()


class RegistryAnalyzer(QObject):
    """Registry analysis service used by the Analysis page."""

    progress_updated = pyqtSignal(str)
    operation_completed = pyqtSignal(str, bool, str)  # operation_name, success, message
    analysis_result = pyqtSignal(dict)
    header_output = pyqtSignal(str)

    # ------------------------------------------------------------- acquire
    def acquire_registry_hives(self, output_dir, selected_hives, username=""):
        try:
            os.makedirs(output_dir, exist_ok=True)
            catalog = dict(SYSTEM_HIVES)
            if username:
                catalog.update(user_hives(username))

            acquired, failed = [], []
            for hive_name in selected_hives:
                hive_path = catalog.get(hive_name)
                if not hive_path:
                    failed.append(hive_name)
                    self.progress_updated.emit(f"✗ Unknown hive {hive_name}")
                    continue
                self.progress_updated.emit(f"Acquiring {hive_name} from {hive_path} ...")
                ok, detail = rawcopy_file(hive_path, output_dir)
                if ok:
                    acquired.append(hive_name)
                    self.progress_updated.emit(f"✓ {hive_name} saved to {detail}")
                else:
                    failed.append(hive_name)
                    self.progress_updated.emit(f"✗ Failed to acquire {hive_name}: {detail}")

            success = not failed and bool(acquired)
            message = f"Acquired {len(acquired)} hive(s)"
            if failed:
                message += f". Failed: {', '.join(failed)} (run the application as Administrator)"
            return success, message
        except Exception as error:  # noqa: BLE001 - reported to the GUI
            return False, f"Error during hive acquisition: {error}"

    # ------------------------------------------------------------- analyze
    def analyze_registry_hive(self, input_dir, analysis_dir, selected_hives):
        if not REGIPY_AVAILABLE:
            return False, "regipy is not installed"
        try:
            os.makedirs(analysis_dir, exist_ok=True)
            analyzed, failed = [], []
            for hive in selected_hives:
                hive_file = os.path.join(input_dir, hive)
                if not os.path.isfile(hive_file):
                    failed.append(hive)
                    self.progress_updated.emit(f"✗ Hive file not found: {hive_file}")
                    continue
                self.progress_updated.emit(f"Analyzing {hive} ...")
                try:
                    registry_hive = RegistryHive(hive_file)
                    results = run_relevant_plugins(registry_hive, as_json=True, continue_on_error=True)
                except Exception as error:  # noqa: BLE001
                    failed.append(hive)
                    self.progress_updated.emit(f"✗ Failed to analyze {hive}: {error}")
                    continue

                output_file = os.path.join(analysis_dir, f"{hive}.json")
                with open(output_file, "w", encoding="utf-8") as handle:
                    json.dump(results, handle, indent=2, default=str)
                analyzed.append(hive)
                self.progress_updated.emit(f"✓ {hive} ({registry_hive.hive_type}) — {len(results)} plugin(s) produced output:")
                for plugin_name, plugin_data in results.items():
                    count = len(plugin_data) if isinstance(plugin_data, (list, dict)) else 1
                    self.progress_updated.emit(f"    • {plugin_name}: {count} entr{'y' if count == 1 else 'ies'}")
                self.progress_updated.emit(f"    → saved to {output_file}")
                self.analysis_result.emit({"hive": hive, "output": output_file, "plugins": list(results.keys())})

            success = not failed and bool(analyzed)
            message = f"Analyzed {len(analyzed)} hive(s). Results in {analysis_dir}"
            if failed:
                message += f". Failed: {', '.join(failed)}"
            return success, message
        except Exception as error:  # noqa: BLE001
            return False, f"Error during hive analysis: {error}"

    # ------------------------------------------------------------- compare
    def compare_registry_hives(self, hive1_path, hive2_path, output_dir):
        if not REGIPY_AVAILABLE:
            return False, "regipy is not installed"
        try:
            os.makedirs(output_dir, exist_ok=True)
            self.progress_updated.emit(f"Loading {os.path.basename(hive1_path)} ...")
            first = self._snapshot(hive1_path)
            self.progress_updated.emit(f"Loading {os.path.basename(hive2_path)} ...")
            second = self._snapshot(hive2_path)

            added = sorted(set(second) - set(first))
            removed = sorted(set(first) - set(second))
            changed = []
            for path in set(first) & set(second):
                if first[path]["values"] != second[path]["values"]:
                    changed.append(path)
            changed.sort()

            report_rows = [["change", "key_path", "value_name", "old_value", "new_value"]]
            for path in added:
                for name, value in second[path]["values"].items():
                    report_rows.append(["added", path, name, "", value])
                if not second[path]["values"]:
                    report_rows.append(["added", path, "", "", ""])
            for path in removed:
                for name, value in first[path]["values"].items():
                    report_rows.append(["removed", path, name, value, ""])
                if not first[path]["values"]:
                    report_rows.append(["removed", path, "", "", ""])
            for path in changed:
                old_values, new_values = first[path]["values"], second[path]["values"]
                for name in sorted(set(old_values) | set(new_values)):
                    if old_values.get(name) != new_values.get(name):
                        report_rows.append(["modified", path, name, old_values.get(name, ""), new_values.get(name, "")])

            output_file = os.path.join(output_dir, "comparison.csv")
            import csv
            with open(output_file, "w", newline="", encoding="utf-8") as handle:
                csv.writer(handle).writerows(report_rows)

            self.progress_updated.emit(f"✓ Keys added: {len(added)}, removed: {len(removed)}, modified: {len(changed)}")
            for path in (added + removed + changed)[:40]:
                tag = "+" if path in added else "-" if path in removed else "~"
                self.progress_updated.emit(f"    {tag} {path}")
            if len(added) + len(removed) + len(changed) > 40:
                self.progress_updated.emit("    ... (see CSV for the full list)")
            return True, f"Comparison saved to {output_file}"
        except Exception as error:  # noqa: BLE001
            return False, f"Error during hive comparison: {error}"

    @staticmethod
    def _snapshot(hive_path: str) -> dict:
        hive = RegistryHive(hive_path)
        snapshot = {}
        for subkey in hive.recurse_subkeys(as_json=True, fetch_values=True):
            values = {}
            for value in subkey.values or []:
                values[value.get("name", "")] = str(value.get("value", ""))
            snapshot[subkey.path] = {"timestamp": subkey.timestamp, "values": values}
        return snapshot

    # ------------------------------------------------------- transaction logs
    def apply_transaction_logs(self, hive_path, output_dir):
        try:
            os.makedirs(output_dir, exist_ok=True)
            primary = hive_path + ".LOG1"
            secondary = hive_path + ".LOG2"
            if not os.path.isfile(primary):
                # Some acquisitions name the logs NTUSER.LOG1 instead of NTUSER.DAT.LOG1
                base, _ = os.path.splitext(hive_path)
                primary, secondary = base + ".LOG1", base + ".LOG2"
            if not os.path.isfile(primary):
                return False, f"Transaction log not found next to the hive (expected {hive_path}.LOG1)"
            if os.path.getsize(primary) == 0:
                return False, f"{os.path.basename(primary)} is empty: the hive has no pending transactions to apply"
            if not os.path.isfile(secondary) or os.path.getsize(secondary) == 0:
                secondary = None

            restored = os.path.join(output_dir, os.path.basename(hive_path) + ".recovered")
            self.progress_updated.emit(f"Applying {os.path.basename(primary)}" + (f" and {os.path.basename(secondary)}" if secondary else "") + " ...")
            if REGIPY_AVAILABLE:
                restored_path, dirty_pages = regipy_apply_transaction_logs(hive_path, primary, secondary, restored_hive_path=restored)
                self.progress_updated.emit(f"✓ {dirty_pages} dirty page(s) applied")
                return True, f"Recovered hive saved to {restored_path}"

            if os.path.isfile(RLA_EXE):
                self.progress_updated.emit("regipy unavailable, falling back to rla.exe ...")
                result = subprocess.run([RLA_EXE, "-f", hive_path, "--out", output_dir], capture_output=True, text=True,
                                        encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
                if result.returncode == 0:
                    return True, f"Recovered hive saved to {output_dir}"
                return False, result.stderr or result.stdout
            return False, "Neither regipy nor rla.exe is available"
        except Exception as error:  # noqa: BLE001
            return False, f"Error applying transaction logs: {error}"

    # ---------------------------------------------------------------- header
    def parse_hive_header(self, hive_path):
        if not REGIPY_AVAILABLE:
            return False, "regipy is not installed"
        try:
            self.progress_updated.emit(f"Parsing header of {os.path.basename(hive_path)} ...")
            hive = RegistryHive(hive_path)
            lines = ["Registry Hive Header Information", "=" * 50, f"File: {hive_path}", f"Detected hive type: {hive.hive_type}"]
            for key, value in hive.header.items():
                if key.startswith("_"):
                    continue
                if key == "last_modification_time" and isinstance(value, int):
                    try:
                        from regipy.utils import convert_wintime
                        value = f"{value} ({convert_wintime(value, as_json=True)})"
                    except Exception:  # noqa: BLE001
                        pass
                if isinstance(value, bytes):
                    value = value.hex()
                lines.append(f"{key}: {value}")
            dirty = hive.header.get("primary_sequence_num") != hive.header.get("secondary_sequence_num")
            lines.append(f"dirty (sequence numbers differ): {dirty}")
            lines.append("=" * 50)
            self.header_output.emit("\n".join(lines))
            return True, f"Header parsed for {os.path.basename(hive_path)}"
        except Exception as error:  # noqa: BLE001
            return False, f"Error parsing hive header: {error}"

    def get_available_hives(self):
        return list(SYSTEM_HIVES.keys()) + list(user_hives("<user>").keys())
