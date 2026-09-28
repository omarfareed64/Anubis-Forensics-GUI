"""USB device history extraction and triage.

Two sources are supported:

* the live registry of the examiner's machine (``winreg``), and
* an acquired ``SYSTEM`` hive (parsed with regipy), which is what a real
  investigation uses because the evidence comes from the suspect machine.
"""
import html
import os
from datetime import datetime, timedelta, timezone

try:
    import winreg
except ImportError:  # pragma: no cover - non-Windows
    winreg = None

try:
    from regipy.registry import RegistryHive
    from regipy.utils import convert_wintime
except ImportError:  # pragma: no cover
    RegistryHive = None

CLASS_GUID_MAP = {
    "{4d36e965-e325-11ce-bfc1-08002be10318}": "CD-ROM",
    "{4d36e967-e325-11ce-bfc1-08002be10318}": "Disk Drive",
    "{4d36e968-e325-11ce-bfc1-08002be10318}": "Display Adapter",
    "{4d36e96b-e325-11ce-bfc1-08002be10318}": "Keyboard",
    "{4d36e96c-e325-11ce-bfc1-08002be10318}": "Media (Sound/Video)",
    "{4d36e96d-e325-11ce-bfc1-08002be10318}": "Modem",
    "{4d36e96e-e325-11ce-bfc1-08002be10318}": "Monitor",
    "{4d36e96f-e325-11ce-bfc1-08002be10318}": "Mouse",
    "{4d36e972-e325-11ce-bfc1-08002be10318}": "Network Adapter",
    "{4d36e978-e325-11ce-bfc1-08002be10318}": "Ports (COM/LPT)",
    "{4d36e979-e325-11ce-bfc1-08002be10318}": "Printer",
    "{4d36e97b-e325-11ce-bfc1-08002be10318}": "SCSI Adapter",
    "{4d36e97d-e325-11ce-bfc1-08002be10318}": "System Device",
    "{4d36e980-e325-11ce-bfc1-08002be10318}": "Floppy Disk",
    "{36fc9e60-c465-11cf-8056-444553540000}": "USB Controller/Hub",
    "{88bae032-5a81-49f0-bc3d-a4ff138216d6}": "USB Device",
    "{71a27cdd-812a-11d0-bec7-08002be2092f}": "Volume",
    "{745a17a0-74d3-11d0-b6fe-00a0c90f57da}": "HID (Human Interface)",
    "{e0cbf06c-cd8b-4647-bb8a-263b43f0f974}": "Bluetooth",
    "{6bdd1fc6-810f-11d0-bec7-08002be2092f}": "Imaging Device",
    "{eec5ad98-8080-425f-922a-dabf3de3f69a}": "WPD (Portable Device)",
    "{c166523c-fe0c-4a94-a586-f1a80cfbbf3e}": "Audio Endpoint",
    "{5c4c3332-344d-483c-8739-259e934c9cc8}": "Software Component",
    "{62f9c741-b25a-46ce-b54c-9bccce08b6f2}": "Smart Card Reader",
}

DETAIL_KEYS = [
    "Description", "Connected", "Device Type", "Device Name", "Connected Time", "Manufacturer", "Device ID",
    "Registry Path", "Timestamp", "Duration", "Hardware ID", "Device Serial", "Driver Version", "Driver Date",
    "Service Name", "Class GUID", "Location Info", "First Install", "Last Arrival", "Last Removal", "Forensic ID",
    "Plug-in Time", "Source",
]

# Device property GUID that stores install/arrival/removal FILETIMEs (Windows 8+).
DEVICE_PROPERTY_KEY = "{83da6326-97a6-4088-9453-a1923f573b29}"
PROPERTY_TIMES = {"0064": "First Install", "0066": "Last Arrival", "0067": "Last Removal"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _new_details(root_path: str, device_id: str, instance_id: str, source: str) -> dict:
    details = {key: "N/A" for key in DETAIL_KEYS}
    details["Device Name"] = instance_id
    details["Device ID"] = device_id
    details["Registry Path"] = f"{root_path}\\{device_id}\\{instance_id}"
    details["Forensic ID"] = device_id + "_" + instance_id.replace("\\", "_")
    details["Device Serial"] = instance_id.split("&")[0] if "&" in instance_id else instance_id
    details["Source"] = source
    details["datetime_obj"] = None
    return details


def _finish_timestamps(details: dict, install_time: datetime | None):
    if not install_time:
        return
    stamp = install_time.strftime("%Y-%m-%d %H:%M:%S UTC")
    for key in ("Connected Time", "Timestamp", "Plug-in Time"):
        details[key] = stamp
    if details["First Install"] == "N/A":
        details["First Install"] = stamp
    details["datetime_obj"] = install_time
    delta = _utcnow() - install_time
    days, rem = divmod(delta.total_seconds(), 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    details["Duration"] = f"{int(days)}d {int(hours)}h {int(minutes)}m ago"


# ---------------------------------------------------------------- live scan
def get_usb_devices() -> list[dict]:
    """Scan the local Windows registry (live system) for USB device history."""
    devices = []
    if winreg is None:
        return devices

    def read_usb_path(root_path):
        try:
            usb_root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, root_path)
        except OSError:
            return
        for i in range(winreg.QueryInfoKey(usb_root)[0]):
            try:
                device_id = winreg.EnumKey(usb_root, i)
                device_key = winreg.OpenKey(usb_root, device_id)
            except OSError:
                continue
            for j in range(winreg.QueryInfoKey(device_key)[0]):
                try:
                    instance_id = winreg.EnumKey(device_key, j)
                    instance_key = winreg.OpenKey(device_key, instance_id)
                except OSError:
                    continue
                details = _new_details(root_path, device_id, instance_id, "live registry")
                try:
                    details["Description"], _ = winreg.QueryValueEx(instance_key, "FriendlyName")
                    details["Connected"] = "Yes"
                except OSError:
                    try:
                        details["Description"], _ = winreg.QueryValueEx(instance_key, "DeviceDesc")
                    except OSError:
                        details["Description"] = instance_id
                    details["Connected"] = "No"
                details["Description"] = str(details["Description"]).split(";")[-1]
                for key, value_name in [("Manufacturer", "Mfg"), ("Service Name", "Service"), ("Driver Version", "DriverVersion"),
                                        ("Driver Date", "DriverDate"), ("Location Info", "LocationInformation")]:
                    try:
                        value, _ = winreg.QueryValueEx(instance_key, value_name)
                        details[key] = str(value).split(";")[-1]
                    except OSError:
                        pass
                try:
                    class_guid, _ = winreg.QueryValueEx(instance_key, "ClassGUID")
                    details["Class GUID"] = class_guid
                    details["Device Type"] = CLASS_GUID_MAP.get(class_guid.lower(), "Unknown")
                except OSError:
                    pass
                try:
                    hw_id, _ = winreg.QueryValueEx(instance_key, "HardwareID")
                    details["Hardware ID"] = hw_id[0] if isinstance(hw_id, list) and hw_id else hw_id
                except OSError:
                    pass
                # Install / arrival / removal times from device properties.
                for suffix, label in PROPERTY_TIMES.items():
                    try:
                        prop_key = winreg.OpenKey(instance_key, f"Properties\\{DEVICE_PROPERTY_KEY}\\{suffix}")
                        raw, _ = winreg.QueryValueEx(prop_key, "")
                        if isinstance(raw, bytes) and len(raw) >= 8:
                            filetime = int.from_bytes(raw[:8], "little")
                            details[label] = (datetime(1601, 1, 1) + timedelta(microseconds=filetime / 10)).strftime("%Y-%m-%d %H:%M:%S UTC")
                    except OSError:
                        continue
                try:
                    timestamp = winreg.QueryInfoKey(instance_key)[2]
                    install_time = datetime(1601, 1, 1) + timedelta(microseconds=timestamp / 10)
                    _finish_timestamps(details, install_time)
                except OSError:
                    pass
                devices.append(details)
                winreg.CloseKey(instance_key)
            winreg.CloseKey(device_key)
        winreg.CloseKey(usb_root)

    read_usb_path(r"SYSTEM\CurrentControlSet\Enum\USBSTOR")
    read_usb_path(r"SYSTEM\CurrentControlSet\Enum\USB")
    return devices


# -------------------------------------------------------------- hive scan
def get_usb_devices_from_hive(system_hive_path: str) -> list[dict]:
    """Parse USB history from an acquired SYSTEM hive (offline evidence)."""
    if RegistryHive is None:
        raise RuntimeError("regipy is not installed")
    hive = RegistryHive(system_hive_path)
    control_set = "ControlSet001"
    try:
        current = hive.get_key(r"\Select").get_value("Current")
        if isinstance(current, int):
            control_set = f"ControlSet{current:03d}"
    except Exception:  # noqa: BLE001
        pass

    devices = []
    for enum_name in ("USBSTOR", "USB"):
        root_path = f"SYSTEM\\{control_set}\\Enum\\{enum_name}"
        try:
            root = hive.get_key(f"\\{control_set}\\Enum\\{enum_name}")
        except Exception:  # noqa: BLE001
            continue
        for device in root.iter_subkeys():
            for instance in device.iter_subkeys():
                details = _new_details(root_path, device.name, instance.name, os.path.basename(system_hive_path))
                values = {v.name: v.value for v in instance.iter_values(as_json=True)} if hasattr(instance, "iter_values") else {}
                friendly = values.get("FriendlyName")
                details["Description"] = str(friendly or values.get("DeviceDesc") or instance.name).split(";")[-1]
                details["Connected"] = "Unknown (offline hive)"
                for key, value_name in [("Manufacturer", "Mfg"), ("Service Name", "Service"), ("Driver Version", "DriverVersion"),
                                        ("Driver Date", "DriverDate"), ("Location Info", "LocationInformation")]:
                    if values.get(value_name) is not None:
                        details[key] = str(values[value_name]).split(";")[-1]
                class_guid = values.get("ClassGUID")
                if class_guid:
                    details["Class GUID"] = class_guid
                    details["Device Type"] = CLASS_GUID_MAP.get(str(class_guid).lower(), "Unknown")
                hw_id = values.get("HardwareID")
                if hw_id:
                    details["Hardware ID"] = hw_id[0] if isinstance(hw_id, list) and hw_id else hw_id
                for suffix, label in PROPERTY_TIMES.items():
                    try:
                        prop = instance.get_subkey("Properties", raise_on_missing=False)
                        prop = prop.get_subkey(DEVICE_PROPERTY_KEY, raise_on_missing=False) if prop else None
                        prop = prop.get_subkey(suffix, raise_on_missing=False) if prop else None
                        if not prop:
                            continue
                        for value in prop.iter_values():
                            raw = value.value
                            if isinstance(raw, (bytes, bytearray)) and len(raw) >= 8:
                                filetime = int.from_bytes(raw[:8], "little")
                                details[label] = (datetime(1601, 1, 1) + timedelta(microseconds=filetime / 10)).strftime("%Y-%m-%d %H:%M:%S UTC")
                            elif isinstance(raw, int):
                                details[label] = str(convert_wintime(raw, as_json=True))
                            break
                    except Exception:  # noqa: BLE001
                        continue
                try:
                    last_write = convert_wintime(instance.header.last_modified)
                    _finish_timestamps(details, last_write.replace(tzinfo=None))
                except Exception:  # noqa: BLE001
                    pass
                devices.append(details)
    return devices


# ------------------------------------------------------------------ triage
def analyze_usb_forensics(devices: list[dict]) -> dict:
    """Identify noteworthy devices and summarise the collection."""
    now = _utcnow()
    findings = []
    storage = [d for d in devices if "USBSTOR" in d.get("Registry Path", "") or d.get("Device Type") in ("Disk Drive", "Volume", "WPD (Portable Device)")]
    recent = [d for d in devices if d.get("datetime_obj") and now - d["datetime_obj"] <= timedelta(days=7)]
    unknown_mfg = [d for d in storage if d.get("Manufacturer") in ("N/A", "", None) or "Compatible" in str(d.get("Manufacturer"))]
    serials = {}
    for device in storage:
        serials.setdefault(device.get("Device Serial", ""), []).append(device)
    multi_instance = {serial: items for serial, items in serials.items() if serial and len(items) > 1}

    for device in storage:
        reasons = []
        if device in recent:
            reasons.append("connected within the last 7 days")
        if device in unknown_mfg:
            reasons.append("generic or unknown manufacturer")
        if device.get("Last Removal") not in ("N/A", "", None) and device.get("Last Arrival") not in ("N/A", "", None) \
                and device["Last Removal"] > device["Last Arrival"]:
            reasons.append("removed after last arrival (used and unplugged)")
        if device.get("Device Serial", "") in multi_instance:
            reasons.append("same serial seen under multiple device IDs")
        if reasons:
            findings.append({"device": device, "reasons": reasons})

    findings.sort(key=lambda f: (f["device"].get("datetime_obj") or datetime.min), reverse=True)
    return {
        "total": len(devices),
        "storage": len(storage),
        "recent": len(recent),
        "connected": sum(1 for d in devices if d.get("Connected") == "Yes"),
        "findings": findings,
        "timeline": sorted([d for d in devices if d.get("datetime_obj")], key=lambda d: d["datetime_obj"], reverse=True)[:50],
    }


def usb_report_html(analysis: dict, source: str = "") -> str:
    esc = html.escape
    rows = ""
    for finding in analysis["findings"]:
        device = finding["device"]
        rows += (f"<tr><td>{esc(str(device.get('Description')))}</td><td>{esc(str(device.get('Device Serial')))}</td>"
                 f"<td>{esc(str(device.get('Manufacturer')))}</td><td>{esc(str(device.get('Plug-in Time')))}</td>"
                 f"<td>{esc(str(device.get('Last Removal')))}</td><td>{esc('; '.join(finding['reasons']))}</td></tr>")
    timeline = ""
    for device in analysis["timeline"]:
        timeline += (f"<tr><td>{esc(str(device.get('Plug-in Time')))}</td><td>{esc(str(device.get('Description')))}</td>"
                     f"<td>{esc(str(device.get('Device Type')))}</td><td>{esc(str(device.get('Hardware ID')))}</td></tr>")
    return f"""<!DOCTYPE html><html><head><meta charset='utf-8'><title>USB Forensic Analysis</title>
<style>body{{font-family:'Segoe UI',sans-serif;margin:20px;color:#333}}h1{{color:#F57C1F;border-bottom:3px solid #23292f}}
table{{border-collapse:collapse;width:100%;margin-bottom:24px}}th{{background:#23292f;color:#fff;text-align:left;padding:8px}}
td{{padding:6px 8px;border-bottom:1px solid #ddd;font-size:0.92em}}.kpi{{display:inline-block;margin:0 24px 16px 0;font-size:1.1em}}
.kpi b{{font-size:1.6em;color:#F57C1F;display:block}}</style></head><body>
<h1>USB Forensic Analysis</h1><p>Source: {esc(source or 'live registry')} — generated {datetime.now():%Y-%m-%d %H:%M:%S}</p>
<div class='kpi'><b>{analysis['total']}</b>devices</div><div class='kpi'><b>{analysis['storage']}</b>storage devices</div>
<div class='kpi'><b>{analysis['recent']}</b>seen in last 7 days</div><div class='kpi'><b>{len(analysis['findings'])}</b>flagged</div>
<h2>Flagged storage devices</h2><table><tr><th>Description</th><th>Serial</th><th>Manufacturer</th><th>Plug-in time</th><th>Last removal</th><th>Why flagged</th></tr>
{rows or '<tr><td colspan=6>No storage device met the triage rules.</td></tr>'}</table>
<h2>Timeline (most recent first)</h2><table><tr><th>Time</th><th>Description</th><th>Type</th><th>Hardware ID</th></tr>{timeline}</table>
</body></html>"""


if __name__ == "__main__":
    for dev in get_usb_devices():
        print(dev["Forensic ID"], dev["Description"], dev["Plug-in Time"])
