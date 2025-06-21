import subprocess
import os
import json
from datetime import datetime
from PyQt5.QtWidgets import QFileDialog, QMessageBox
from PyQt5.QtCore import QObject, pyqtSignal

class RegistryAnalyzer(QObject):
    """Registry analysis service that integrates regauto backend with GUI"""
    
    # Signals for progress updates
    progress_updated = pyqtSignal(str)
    operation_completed = pyqtSignal(str, bool, str)  # operation_name, success, message
    analysis_result = pyqtSignal(dict)  # For analysis results
    header_output = pyqtSignal(str)  # For header parsing output
    
    def __init__(self):
        super().__init__()
        # Use correct relative paths from the GUI directory
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self.rawcopy_path = os.path.join(base_dir, "Anubis-Forensics-GUI", "RawCopy.exe")
        self.rla_path = os.path.join(base_dir, "Anubis-Forensics-GUI", "rla.exe")
        
    def acquire_registry_hives(self, output_dir, selected_hives, username=""):
        """Acquire selected registry hives using RawCopy"""
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            system_hives = {
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
                "CLASSES_ROOT_HIVE_TYPE": r"C:\Windows\System32\config\CLASSES",
                "BCD_HIVE_TYPE": r"C:\Windows\System32\config\BCD",
            }
            
            # Add user-specific hives if username provided
            if username:
                user_hives = {
                    "NTUSER.DAT": rf"C:\Users\{username}\NTUSER.DAT",
                    "NTUSER.LOG1": rf"C:\Users\{username}\NTUSER.DAT.LOG1", 
                    "NTUSER.LOG2": rf"C:\Users\{username}\NTUSER.DAT.LOG2",
                    "UsrClass.dat": rf"C:\Users\{username}\AppData\Local\Microsoft\Windows\UsrClass.dat",
                    "UsrClass.LOG1": rf"C:\Users\{username}\AppData\Local\Microsoft\Windows\UsrClass.dat.LOG1",
                    "UsrClass.LOG2": rf"C:\Users\{username}\AppData\Local\Microsoft\Windows\UsrClass.dat.LOG2",
                }
                system_hives.update(user_hives)
            
            acquired_hives = []
            failed_hives = []
            
            for hive_name in selected_hives:
                if hive_name in system_hives:
                    hive_path = system_hives[hive_name]
                    self.progress_updated.emit(f"Acquiring {hive_name}...")
                    
                    command = f'"{self.rawcopy_path}" /FileNamePath:"{hive_path}" /OutputPath:"{output_dir}"'
                    result = subprocess.run(
                        command, 
                        shell=True, 
                        capture_output=True, 
                        text=True, 
                        encoding='utf-8',
                        errors='replace'
                    )
                    
                    if result.returncode == 0:
                        acquired_hives.append(hive_name)
                        self.progress_updated.emit(f"✓ {hive_name} acquired successfully")
                    else:
                        failed_hives.append(hive_name)
                        self.progress_updated.emit(f"✗ Failed to acquire {hive_name}: {result.stderr}")
            
            success = len(failed_hives) == 0
            message = f"Acquired {len(acquired_hives)} hives successfully"
            if failed_hives:
                message += f". Failed: {', '.join(failed_hives)}"
                
            self.operation_completed.emit("acquire_hives", success, message)
            return success, message
            
        except Exception as e:
            error_msg = f"Error during hive acquisition: {str(e)}"
            self.operation_completed.emit("acquire_hives", False, error_msg)
            return False, error_msg
    
    def analyze_registry_hive(self, input_dir, analysis_dir, selected_hives):
        """Analyze selected registry hives using regipy"""
        try:
            os.makedirs(analysis_dir, exist_ok=True)
            
            analyzed_hives = []
            failed_hives = []
            
            for hive in selected_hives:
                hive_file = os.path.join(input_dir, hive)
                if os.path.exists(hive_file):
                    self.progress_updated.emit(f"Analyzing {hive}...")
                    
                    output_file = os.path.join(analysis_dir, f"{hive}.json")
                    command = f'regipy-plugins-run "{hive_file}" -o "{output_file}"'
                    result = subprocess.run(
                        command, 
                        shell=True, 
                        capture_output=True, 
                        text=True, 
                        encoding='utf-8',
                        errors='replace'
                    )
                    
                    if result.returncode == 0:
                        analyzed_hives.append(hive)
                        self.progress_updated.emit(f"✓ {hive} analyzed successfully")
                    else:
                        failed_hives.append(hive)
                        self.progress_updated.emit(f"✗ Failed to analyze {hive}: {result.stderr}")
                else:
                    failed_hives.append(hive)
                    self.progress_updated.emit(f"✗ Hive file not found: {hive}")
            
            success = len(failed_hives) == 0
            message = f"Analyzed {len(analyzed_hives)} hives successfully"
            if failed_hives:
                message += f". Failed: {', '.join(failed_hives)}"
                
            self.operation_completed.emit("analyze_hives", success, message)
            return success, message
            
        except Exception as e:
            error_msg = f"Error during hive analysis: {str(e)}"
            self.operation_completed.emit("analyze_hives", False, error_msg)
            return False, error_msg
    
    def compare_registry_hives(self, hive1_path, hive2_path, output_dir):
        """Compare two registry hives using regipy"""
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            self.progress_updated.emit("Comparing registry hives...")
            
            output_file = os.path.join(output_dir, "comparison.csv")
            command = f'regipy-diff "{hive1_path}" "{hive2_path}" -o "{output_file}"'
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                encoding='utf-8',
                errors='replace'
            )
            
            if result.returncode == 0:
                message = f"Comparison completed. Output saved to {output_file}"
                self.progress_updated.emit("✓ Comparison completed successfully")
                self.operation_completed.emit("compare_hives", True, message)
                return True, message
            else:
                error_msg = f"Failed to compare hives: {result.stderr}"
                self.progress_updated.emit(f"✗ {error_msg}")
                self.operation_completed.emit("compare_hives", False, error_msg)
                return False, error_msg
                
        except Exception as e:
            error_msg = f"Error during hive comparison: {str(e)}"
            self.operation_completed.emit("compare_hives", False, error_msg)
            return False, error_msg
    
    def apply_transaction_logs(self, hive_path, output_dir):
        """Apply transaction logs using rla.exe"""
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            self.progress_updated.emit("Applying transaction logs...")
            
            command = f'"{self.rla_path}" -f "{hive_path}" --out "{output_dir}"'
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                encoding='utf-8',
                errors='replace'
            )
            
            if result.returncode == 0:
                message = f"Transaction logs applied successfully. Recovered hive saved to {output_dir}"
                self.progress_updated.emit("✓ Transaction logs applied successfully")
                self.operation_completed.emit("apply_logs", True, message)
                return True, message
            else:
                error_msg = f"Failed to apply transaction logs: {result.stderr}"
                self.progress_updated.emit(f"✗ {error_msg}")
                self.operation_completed.emit("apply_logs", False, error_msg)
                return False, error_msg
                
        except Exception as e:
            error_msg = f"Error applying transaction logs: {str(e)}"
            self.operation_completed.emit("apply_logs", False, error_msg)
            return False, error_msg
    
    def parse_hive_header(self, hive_path):
        """Parse registry hive header using regipy - uses Python script to avoid encoding issues"""
        try:
            self.progress_updated.emit(f"Parsing header for {os.path.basename(hive_path)}...")
            
            # Create a Python script to parse the header with simple output
            import tempfile
            script_content = f'''
import sys
from regipy.registry import RegistryHive

try:
    registry_hive = RegistryHive(hive_path="{hive_path}")
    print("Registry Hive Header Information")
    print("=" * 50)
    for key, value in registry_hive.header.items():
        print(f"{{key}}: {{value}}")
    print("=" * 50)
except Exception as e:
    print(f"Error: {{e}}")
    sys.exit(1)
'''
            
            # Create temporary script file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as script_file:
                script_path = script_file.name
                script_file.write(script_content)
            
            # Create temporary output file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as temp_file:
                temp_output_path = temp_file.name
            
            # Set environment variables to force UTF-8 encoding
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            env['PYTHONLEGACYWINDOWSSTDIO'] = 'utf-8'
            env['PYTHONUTF8'] = '1'
            
            # Run the Python script
            command = f'python "{script_path}" > "{temp_output_path}" 2>&1'
            result = subprocess.run(command, shell=True, env=env)
            
            # Read the output from the temporary file
            output_content = ""
            if os.path.exists(temp_output_path):
                try:
                    with open(temp_output_path, 'r', encoding='utf-8', errors='replace') as f:
                        output_content = f.read()
                except Exception as read_error:
                    output_content = f"Error reading output file: {str(read_error)}"
                
                # Clean up the temporary files
                try:
                    os.unlink(temp_output_path)
                    os.unlink(script_path)
                except:
                    pass
            
            if result.returncode == 0:
                # Emit the header output for display in GUI
                if output_content:
                    self.header_output.emit(output_content)
                
                message = f"Header parsed successfully for {os.path.basename(hive_path)}"
                self.progress_updated.emit("✓ Header parsed successfully")
                self.operation_completed.emit("parse_header", True, message)
                return True, message
            else:
                error_msg = f"Failed to parse header for {os.path.basename(hive_path)}"
                if output_content:
                    error_msg += f"\nOutput: {output_content}"
                self.progress_updated.emit(f"✗ {error_msg}")
                self.operation_completed.emit("parse_header", False, error_msg)
                return False, error_msg
                
        except Exception as e:
            error_msg = f"Error parsing hive header: {str(e)}"
            self.operation_completed.emit("parse_header", False, error_msg)
            return False, error_msg
    
    def get_available_hives(self):
        """Get list of available registry hives"""
        return [
            "SYSTEM", "SYSTEM.LOG1", "SYSTEM.LOG2",
            "SOFTWARE", "SOFTWARE.LOG1", "SOFTWARE.LOG2", 
            "SAM", "SAM.LOG1", "SAM.LOG2",
            "SECURITY", "SECURITY.LOG1", "SECURITY.LOG2",
            "NTUSER.DAT", "NTUSER.LOG1", "NTUSER.LOG2",
            "UsrClass.dat", "UsrClass.LOG1", "UsrClass.LOG2",
            "Amcache.hve", "Amcache.hve.LOG1", "Amcache.hve.LOG2",
            "CLASSES_ROOT_HIVE_TYPE", "BCD_HIVE_TYPE"
        ] 