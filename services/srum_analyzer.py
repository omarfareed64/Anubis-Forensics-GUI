"""SRUM (System Resource Usage Monitor) analysis.

Parses ``SRUDB.dat`` with the pure-Python ``dissect.esedb`` library. The old
implementation needed the compiled ``pyesedb`` bindings and an Excel template
(``SRUM_TEMPLATE2.XLSX``) that was never shipped with the project, so the SRUM
button could never work. Table names, timestamps, application and user IDs are
now resolved directly from the database (and optionally the SOFTWARE hive).
"""
import os
import struct
from datetime import datetime, timedelta

from dissect.esedb.tools.sru import SKIP_TABLES, SRU

try:
    from regipy.registry import RegistryHive
except ImportError:  # pragma: no cover
    RegistryHive = None

TABLE_NAMES = {
    "{973F5D5C-1D90-4944-BE8E-24B94231A174}": "Network Data Usage",
    "{DD6636C4-8929-4683-974E-22C046A43763}": "Network Connectivity",
    "{DA73FB89-2BEA-4DDC-86B8-6E048C6DA477}": "Energy Estimation",
    "{FEE4E14F-02A9-4550-B5CE-5FA2DA202E37}": "Energy Usage",
    "{FEE4E14F-02A9-4550-B5CE-5FA2DA202E37}LT": "Energy Usage (Long Term)",
    "{D10CA2FE-6FCF-4F6D-848E-B2E99266FA89}": "Application Resource Usage",
    "{D10CA2FE-6FCF-4F6D-848E-B2E99266FA86}": "Push Notifications",
    "{5C8CF1C7-7257-4F13-B223-970EF5939312}": "Application Timeline",
    "{7ACBBAA3-D029-4BE4-9A7A-0885927F1D8F}": "VFU Provider",
    "{B6D82AF1-F780-4E17-8077-6CB9AD8A6FC4}": "Tagged Energy",
    "{17F4D97B-F26A-5E79-3A82-90040A47D13D}": "SDP Volume Provider",
    "{841A7317-3805-518B-C2EA-AD224CB4AF84}": "SDP Physical Disk Provider",
    "{DC3D3B50-BB90-5066-FA4E-A5F90DD8B677}": "SDP CPU Provider",
    "{EEE2F477-0659-5C47-EF03-6D6BEFD441B3}": "SDP Network Provider",
    "{38AD6548-9313-58F8-45C7-D293BAFDC879}": "SDP Performance Counter Provider",
    "{CDF8EBF6-7C0F-5AC2-158F-DBFBEE981152}": "SDP Event Log Provider",
}

# IANA ifType numbers that appear in the high 16 bits of InterfaceLuid.
INTERFACE_TYPES = {
    6: "Ethernet", 23: "PPP", 24: "Software loopback", 37: "ATM", 71: "Wi-Fi (802.11)",
    131: "Tunnel", 144: "IEEE 1394", 237: "WiMAX", 243: "Mobile broadband (WWANPP)", 244: "Mobile broadband (WWANPP2)",
}

FILETIME_COLUMNS = {"ConnectStartTime", "EndTime", "StartTime"}


def load_profile_sids(software_hive: str | None) -> dict:
    """Map SID → user name using ProfileList of a SOFTWARE hive."""
    if not software_hive or not RegistryHive or not os.path.isfile(software_hive):
        return {}
    result = {}
    try:
        hive = RegistryHive(software_hive)
        key = hive.get_key(r"\Microsoft\Windows NT\CurrentVersion\ProfileList")
        for subkey in key.iter_subkeys():
            try:
                image_path = subkey.get_value("ProfileImagePath")
                if image_path:
                    result[subkey.name] = str(image_path).replace("/", "\\").split("\\")[-1]
            except Exception:  # noqa: BLE001
                continue
    except Exception:  # noqa: BLE001
        return result
    return result


def load_wlan_profiles(software_hive: str | None) -> dict:
    """Map wireless ProfileIndex → SSID using WlanSvc metadata of a SOFTWARE hive."""
    if not software_hive or not RegistryHive or not os.path.isfile(software_hive):
        return {}
    result = {}
    try:
        hive = RegistryHive(software_hive)
        interfaces = hive.get_key(r"\Microsoft\WlanSvc\Interfaces")
        for interface in interfaces.iter_subkeys():
            profiles = interface.get_subkey("Profiles", raise_on_missing=False)
            if not profiles:
                continue
            for profile in profiles.iter_subkeys():
                try:
                    index = profile.get_value("ProfileIndex")
                    metadata = profile.get_subkey("MetaData", raise_on_missing=False)
                    if index is None or not metadata:
                        continue
                    for value_name in ("Channel Hints", "Band Channel Hints"):
                        raw = metadata.get_value(value_name)
                        if isinstance(raw, bytes) and len(raw) >= 4:
                            length = struct.unpack("<I", raw[:4])[0]
                            result[str(index)] = raw[4:4 + length].decode("latin1", errors="replace")
                            break
                except Exception:  # noqa: BLE001
                    continue
    except Exception:  # noqa: BLE001
        return result
    return result


def _filetime(value):
    try:
        return (datetime(1601, 1, 1) + timedelta(microseconds=int(value) / 10)).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OverflowError):
        return value


def format_value(column: str, value, sids: dict, wlan: dict) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, bytes):
        return value.hex()
    if column == "UserId" and isinstance(value, str) and value.startswith("S-"):
        name = sids.get(value)
        return f"{value} ({name})" if name else value
    if column == "InterfaceLuid" and isinstance(value, int):
        interface_type = (value >> 48) & 0xFFFF
        label = INTERFACE_TYPES.get(interface_type)
        return f"{value} ({label})" if label else str(value)
    if column == "L2ProfileId" and wlan:
        ssid = wlan.get(str(value))
        return f"{value} ({ssid})" if ssid else str(value)
    if column in FILETIME_COLUMNS and isinstance(value, int) and value > 10**15:
        return str(_filetime(value))
    return str(value)


def analyze_srum(srum_path: str, software_hive: str | None = None, progress=None) -> dict:
    """Return ``{table_name: [header_row, row, row, ...]}`` for every SRUM table."""

    def report(message):
        if progress:
            progress(message)

    sids = load_profile_sids(software_hive)
    wlan = load_wlan_profiles(software_hive)
    if software_hive:
        report(f"SOFTWARE hive: {len(sids)} user profile(s), {len(wlan)} wireless profile(s) resolved")

    results = {}
    with open(srum_path, "rb") as handle:
        sru = SRU(handle)
        for table in sru.esedb.tables():
            if table.name in SKIP_TABLES:
                continue
            friendly = TABLE_NAMES.get(table.name, table.name)
            columns = list(table.column_names)
            report(f"Reading {friendly} ...")
            rows = []
            for entry in sru.get_table_entries(table=table):
                row = []
                for column in columns:
                    try:
                        value = entry[column]
                    except Exception:  # noqa: BLE001 - fall back to the raw value
                        try:
                            value = entry.record.get(column)
                        except Exception:  # noqa: BLE001
                            value = "?"
                    row.append(format_value(column, value, sids, wlan))
                rows.append(row)
            if rows:
                results[friendly] = [columns] + rows
                report(f"  {len(rows)} record(s)")
    return results
