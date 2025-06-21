import winreg
from datetime import datetime, timedelta

CLASS_GUID_MAP = {
    "{4d36e96f-e325-11ce-bfc1-08002be10318}": "Display Adapter",
    "{4d36e96b-e325-11ce-bfc1-08002be10318}": "Sound",
    "{4d36e96c-e325-11ce-bfc1-08002be10318}": "Media",
    "{4d36e96d-e325-11ce-bfc1-08002be10318}": "Modem",
    "{4d36e972-e325-11ce-bfc1-08002be10318}": "Bluetooth",
    "{4d36e96e-e325-11ce-bfc1-08002be10318}": "Mouse",
    "{745a17a0-74d3-11d0-b6fe-00a0c90f57da}": "HID (Human Interface)",
    "{e0cbf06c-cd8b-4647-bb8a-263b43f0f974}": "Bluetooth",
    "{4d36e967-e325-11ce-bfc1-08002be10318}": "Disk Drive",
    "{4d36e980-e325-11ce-bfc1-08002be10318}": "Floppy Disk",
    "{4d36e981-e325-11ce-bfc1-08002be10318}": "CD-ROM",
    "{4d36e965-e325-11ce-bfc1-08002be10318}": "System Devices",
    "{4d36e968-e325-11ce-bfc1-08002be10318}": "Volume",
    "{4d36e97d-e325-11ce-bfc1-08002be10318}": "USB Controllers",
    "{4d36e978-e325-11ce-bfc1-08002be10318}": "Ports",
    "{4d36e97b-e325-11ce-bfc1-08002be10318}": "USB",
}

def get_usb_devices():
    """Scans the local Windows Registry for a comprehensive history of USB devices."""
    current_time = datetime.utcnow()
    devices = []
    
    def read_usb_path(root_path):
        try:
            reg = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
            usb_root = winreg.OpenKey(reg, root_path)

            for i in range(winreg.QueryInfoKey(usb_root)[0]):
                try:
                    device_id = winreg.EnumKey(usb_root, i)
                    device_key = winreg.OpenKey(usb_root, device_id)

                    for j in range(winreg.QueryInfoKey(device_key)[0]):
                        try:
                            instance_id = winreg.EnumKey(device_key, j)
                            instance_key = winreg.OpenKey(device_key, instance_id)

                            details = {k: "N/A" for k in [
                                "Description", "Connected", "Device Type", "Device Name", "Connected Time",
                                "Manufacturer", "Device ID", "Registry Path", "Timestamp", "Duration",
                                "Hardware ID", "Device Serial", "Driver Version", "Driver Date", "Service Name",
                                "Class GUID", "Device GUID", "Location Info", "Power State", "First Install",
                                "Last Known Good", "Last Removal", "Forensic ID", "Plug-in Time"
                            ]}
                            
                            details["Device Name"] = instance_id
                            details["Device ID"] = device_id
                            details["Registry Path"] = f"{root_path}\\{device_id}\\{instance_id}"
                            details["Forensic ID"] = device_id + "_" + instance_id.replace('\\', '_')
                            
                            try:
                                description, _ = winreg.QueryValueEx(instance_key, "FriendlyName")
                                details["Description"] = description
                                details["Connected"] = "Yes"
                            except Exception:
                                try:
                                    description, _ = winreg.QueryValueEx(instance_key, "DeviceDesc")
                                    details["Description"] = description
                                    details["Connected"] = "No" # Assume not connected if no FriendlyName
                                except Exception:
                                    details["Description"] = instance_id
                                    details["Connected"] = "No"
                            
                            for key, val_name in [("Manufacturer", "Mfg"), ("Service Name", "Service"),
                                                  ("DriverVersion", "DriverVersion"), ("DriverDate", "DriverDate"),
                                                  ("Location Info", "LocationInformation"), ("PowerState", "PowerData")]:
                                try:
                                    details[key], _ = winreg.QueryValueEx(instance_key, val_name)
                                except Exception: pass
                            
                            try:
                                class_guid, _ = winreg.QueryValueEx(instance_key, "ClassGUID")
                                details["Class GUID"] = class_guid
                                details["Device Type"] = CLASS_GUID_MAP.get(class_guid.lower(), "Unknown")
                            except Exception: pass
                            
                            try:
                                hw_id, _ = winreg.QueryValueEx(instance_key, "HardwareID")
                                details["Hardware ID"] = hw_id[0] if isinstance(hw_id, list) and hw_id else hw_id
                            except Exception: pass
                            
                            try:
                                timestamp = winreg.QueryInfoKey(instance_key)[2]
                                install_time_dt = datetime.utcfromtimestamp(timestamp / 1e7 - 11644473600)
                                install_time_str = install_time_dt.strftime('%Y-%m-%d %H:%M:%S UTC')
                                details["Connected Time"] = install_time_str
                                details["Timestamp"] = install_time_str
                                details["First Install"] = install_time_str
                                details["datetime_obj"] = install_time_dt
                                
                                if details["Connected"] == "Yes":
                                    details["Plug-in Time"] = install_time_str
                                    time_diff = current_time - install_time_dt
                                    days, rem = divmod(time_diff.total_seconds(), 86400)
                                    hours, rem = divmod(rem, 3600)
                                    minutes, _ = divmod(rem, 60)
                                    details["Duration"] = f"{int(days)}d {int(hours)}h {int(minutes)}m"
                                    
                            except Exception:
                                details["datetime_obj"] = None
                            
                            devices.append(details)
                            winreg.CloseKey(instance_key)
                        except Exception: continue
                    winreg.CloseKey(device_key)
                except Exception: continue
            winreg.CloseKey(usb_root)
        except Exception: pass

    read_usb_path(r"SYSTEM\CurrentControlSet\Enum\USBSTOR")
    read_usb_path(r"SYSTEM\CurrentControlSet\Enum\USB")

    return devices

if __name__ == '__main__':
    # For standalone testing
    all_devices = get_usb_devices()
    if all_devices:
        for dev in all_devices:
            print(dev)
    else:
        print("No USB devices found or failed to read registry.") 