from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QLineEdit, QTextEdit, QFormLayout, QComboBox, 
    QDateEdit, QSpinBox, QToolButton, QGridLayout, QFileDialog,
    QGroupBox, QCheckBox, QRadioButton, QButtonGroup, QDialog, QListWidget, QListWidgetItem,
    QMessageBox
)
from PyQt5.QtGui import QPixmap, QFont, QIcon
from PyQt5.QtCore import Qt, pyqtSignal, QDate, QSize, QThread, pyqtSignal as Signal
from .base_page import BasePage, COLOR_ORANGE, COLOR_DARK, COLOR_GRAY, TAB_NAMES
import os
import sys
import subprocess
import time
import logging
import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("filebrowser.log"),
        logging.StreamHandler()
    ]
)

class RemoteConnectionThread(QThread):
    connection_result = Signal(dict)
    
    def __init__(self, connection_params):
        super().__init__()
        self.connection_params = connection_params
        
    def run(self):
        try:
            remote_ip = self.connection_params['ip_address']
            remote_domain = self.connection_params['domain']
            remote_user = self.connection_params['username']
            remote_password = self.connection_params['password']
            
            # Preemptively kill any existing filebrowser process
            logging.info("[*] Attempting to kill any lingering remote filebrowser processes...")
            try:
                subprocess.run([
                    "PsExec.exe", f"\\\\{remote_ip}", "-accepteula",
                    "-u", f"{remote_domain}\\{remote_user}", "-p", remote_password,
                    "taskkill", "/F", "/IM", "filebrowser.exe"
                ], check=False, capture_output=True, text=True) # Use check=False, it's okay if it fails (process not running)
            except Exception as e:
                logging.warning(f"Failed to pre-emptively kill remote process, this might be okay. Error: {e}")

            filebrowser_exe = "filebrowser.exe"
            if not os.path.isfile(filebrowser_exe):
                self.connection_result.emit({
                    'status': 'error',
                    'message': f"{filebrowser_exe} not found in current directory."
                })
                return

            remote_share = f"\\\\{remote_ip}\\C$"
            remote_path = f"C:\\filebrowser.exe"
            remote_db_path = f"C:\\WINDOWS\\system32\\filebrowser.db"

            # 1. Connect to remote share
            logging.info("[*] Connecting to remote C$ share...")
            subprocess.run([
                "net", "use", remote_share, remote_password, f"/user:{remote_user}"
            ], check=True)

            # 2. Copy filebrowser.exe to C:
            logging.info("[*] Copying filebrowser.exe to remote C drive...")
            try:
                result = subprocess.run([
                "xcopy",
                filebrowser_exe,
                f"{remote_share}\\",
                "/Y"
                ], capture_output=True, text=True)
                logging.error(f"XCOPY STDOUT: {result.stdout}")
                logging.error(f"XCOPY STDERR: {result.stderr}")
                result.check_returncode()
            except subprocess.CalledProcessError as e:
                self.connection_result.emit({
                    'status': 'error',
                    'message': f"XCOPY failed: {e}\nSTDOUT: {e.stdout}\nSTDERR: {e.stderr}"
                })
                return

            # 3. Start filebrowser.exe via PsExec
            logging.info("[*] Launching filebrowser remotely via PsExec...")
            subprocess.Popen([
                "PsExec.exe",
                f"\\\\{remote_ip}",
                "-accepteula",
                "-u", f"{remote_domain}\\{remote_user}",
                "-p", remote_password,
                "-h",
                remote_path,
                "--address", "0.0.0.0",
                "--port", "8080",
                "--noauth",
                "--root", "C:/"
            ])
            
            # Wait a moment for the service to start
            time.sleep(3)
            
            self.connection_result.emit({
                'status': 'success',
                'message': f"Successfully connected to {remote_ip}",
                'remote_ip': remote_ip,
                'remote_domain': remote_domain,
                'remote_user': remote_user,
                'remote_password': remote_password
            })
            
        except subprocess.CalledProcessError as e:
            self.connection_result.emit({
                'status': 'error',
                'message': f"Connection failed: {e}"
            })
        except Exception as e:
            self.connection_result.emit({
                'status': 'error',
                'message': f"Unexpected error: {e}"
            })
        finally:
            # Clean up the network share
            try:
                subprocess.run(["net", "use", remote_share, "/delete"],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
            except (subprocess.SubprocessError, FileNotFoundError):
                pass

# Constants
FONT_LABEL = QFont("Cascadia Mono", 13,)
FONT_CARD = QFont("Cascadia Mono", 18, QFont.Weight.ExtraBold)
FONT_GROUP = QFont("Cascadia Mono", 16, QFont.Weight.Bold)
FONT_SECTION = QFont("Cascadia Mono", 20, QFont.Weight.ExtraBold)

class RemoteAcquisitionPage(BasePage):
    back_requested = pyqtSignal()
    connect_requested = pyqtSignal(dict)  # Signal with connection parameters
    acquisition_state = pyqtSignal(dict)  # e.g., {'status': 'success', 'details': ...}

    def __init__(self):
        super().__init__()
        self.connection_thread = None
        self.selected_case_path = None
        self.setup_page_content()

    def set_case_path(self, case_path):
        """Set the case path for storing evidence"""
        self.selected_case_path = case_path

    def setup_page_content(self):
        """Setup the page-specific content for the remote acquisition page"""
        # Add tab bar
        self.main_layout.addLayout(self._setup_tab_bar(TAB_NAMES))
        self.main_layout.addSpacing(40)

        # Create scrollable content container
        content_container = QWidget()
        content_container.setStyleSheet("""
            QWidget {
                background-color: white;
                border-radius: 24px;
            }
        """)
        content_container.setFixedSize(1500, 600)

        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(40, 32, 40, 32)
        content_layout.setSpacing(18)

        # NEW AGENT section
        section1 = QLabel("NEW AGENT")
        section1.setFont(FONT_SECTION)
        section1.setStyleSheet(f"color: {COLOR_DARK}; margin-bottom: 2px;")
        content_layout.addWidget(section1, alignment=Qt.AlignmentFlag.AlignLeft)

        grid1 = QGridLayout()
        grid1.setHorizontalSpacing(32)
        grid1.setVerticalSpacing(10)

        name_label = QLabel("Name")
        name_label.setFont(FONT_LABEL)
        grid1.addWidget(name_label, 0, 0)
        self.agent_name_input = self.create_styled_input()
        self.agent_name_input.setText("ahmed")
        grid1.addWidget(self.agent_name_input, 1, 0)

        location_label = QLabel("Agent Location on your machine")
        location_label.setFont(FONT_LABEL)
        grid1.addWidget(location_label, 0, 1)
        
        location_field = QWidget()
        location_field_layout = QHBoxLayout(location_field)
        location_field_layout.setContentsMargins(0, 0, 0, 0)
        location_field_layout.setSpacing(0)
        self.agent_location_input = self.create_styled_input()
        self.agent_location_button = self.create_folder_button(self._choose_agent_location, 48)
        location_field_layout.addWidget(self.agent_location_input)
        location_field_layout.addWidget(self.agent_location_button)
        grid1.addWidget(location_field, 1, 1)

        content_layout.addLayout(grid1)
        content_layout.addSpacing(10)

        # TARGET MACHINE section
        section2 = QLabel("TARGET MACHINE")
        section2.setFont(FONT_SECTION)
        section2.setStyleSheet(f"color: {COLOR_DARK}; margin-bottom: 2px;")
        content_layout.addWidget(section2, alignment=Qt.AlignmentFlag.AlignLeft)

        grid2 = QGridLayout()
        grid2.setHorizontalSpacing(32)
        grid2.setVerticalSpacing(10)

        ip_label = QLabel("IP address")
        ip_label.setFont(FONT_LABEL)
        grid2.addWidget(ip_label, 0, 0)
        self.ip_input = self.create_styled_input()
        self.ip_input.setText("172.30.101.228")
        grid2.addWidget(self.ip_input, 1, 0)

        domain_label = QLabel("Domain")
        domain_label.setFont(FONT_LABEL)
        grid2.addWidget(domain_label, 0, 1)
        self.domain_input = self.create_styled_input()
        self.domain_input.setText("fede")
        grid2.addWidget(self.domain_input, 1, 1)

        content_layout.addLayout(grid2)
        content_layout.addSpacing(10)

        # Credentials section
        section3 = QLabel("Credentials")
        section3.setFont(FONT_SECTION)
        section3.setStyleSheet(f"color: {COLOR_DARK}; margin-bottom: 2px;")
        content_layout.addWidget(section3, alignment=Qt.AlignmentFlag.AlignLeft)

        grid3 = QGridLayout()
        grid3.setHorizontalSpacing(32)
        grid3.setVerticalSpacing(10)

        user_label = QLabel("User name")
        user_label.setFont(FONT_LABEL)
        grid3.addWidget(user_label, 0, 0)
        self.username_input = self.create_styled_input()
        self.username_input.setText("vboxuser")
        grid3.addWidget(self.username_input, 1, 0)

        password_label = QLabel("Password")
        password_label.setFont(FONT_LABEL)
        grid3.addWidget(password_label, 0, 1)
        self.password_input = self.create_styled_input(is_password=True)
        self.password_input.setText("123")
        grid3.addWidget(self.password_input, 1, 1)

        content_layout.addLayout(grid3)
        content_layout.addSpacing(10)

        self.main_layout.addWidget(content_container, alignment=Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addSpacing(24)

        # Connect button
        self.connect_button = self.create_styled_button("Connect", self._handle_connect)
        self.main_layout.addWidget(self.connect_button, alignment=Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addSpacing(20)
        
        # Back button
        back_button = self.create_styled_button("Back", self._handle_back_click, COLOR_DARK, "white")
        self.main_layout.addWidget(back_button, alignment=Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addStretch()

    def _create_group_box(self, title):
        """Create a styled group box"""
        group = QGroupBox(title)
        group.setFont(FONT_GROUP)
        group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                color: {COLOR_DARK};
                border: 2px solid #e0e0e0;
                border-radius: 12px;
                margin-top: 12px;
                padding-top: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 16px;
                padding: 0 8px 0 8px;
            }}
        """)
        return group

    def _choose_agent_location(self):
        """Choose agent location"""
        directory = QFileDialog.getExistingDirectory(self, "Select Agent Location")
        if directory:
            self.agent_location_input.setText(directory)

    def _handle_connect(self):
        """Handle connect button click"""
        # Collect all connection parameters
        connection_params = {
            'agent_name': self.agent_name_input.text().strip(),
            'agent_location': self.agent_location_input.text().strip(),
            'ip_address': self.ip_input.text().strip(),
            'domain': self.domain_input.text().strip(),
            'username': self.username_input.text().strip(),
            'password': self.password_input.text()
        }
        
        # Validate required fields with visual feedback
        missing_fields = []
        
        if not connection_params['agent_name']:
            missing_fields.append("Agent name")
            self.agent_name_input.setStyleSheet(self.get_input_style().replace("border: 2.5px solid #23292f;", "border: 2px solid #d32f2f; background-color: #ffebee;"))
        else:
            self.agent_name_input.setStyleSheet(self.get_input_style())
            
        if not connection_params['ip_address']:
            missing_fields.append("IP address")
            self.ip_input.setStyleSheet(self.get_input_style().replace("border: 2.5px solid #23292f;", "border: 2px solid #d32f2f; background-color: #ffebee;"))
        else:
            self.ip_input.setStyleSheet(self.get_input_style())
            
        if not connection_params['username']:
            missing_fields.append("Username")
            self.username_input.setStyleSheet(self.get_input_style().replace("border: 2.5px solid #23292f;", "border: 2px solid #d32f2f; background-color: #ffebee;"))
        else:
            self.username_input.setStyleSheet(self.get_input_style())
            
        if not connection_params['password']:
            missing_fields.append("Password")
            self.password_input.setStyleSheet(self.get_input_style().replace("border: 2.5px solid #23292f;", "border: 2px solid #d32f2f; background-color: #ffebee;"))
        else:
            self.password_input.setStyleSheet(self.get_input_style())
        
        if missing_fields:
            missing_fields_text = '\n• '.join(missing_fields)
            QMessageBox.warning(self, "Missing Fields", f"Please fill in the following required fields:\n• {missing_fields_text}")
            return
        
        # Disable connect button during connection
        self.connect_button.setEnabled(False)
        self.connect_button.setText("Connecting...")
        
        # Start connection in background thread
        self.connection_thread = RemoteConnectionThread(connection_params)
        self.connection_thread.connection_result.connect(self._on_connection_result)
        self.connection_thread.start()

    def _on_connection_result(self, result):
        """Handle connection result"""
        # Re-enable connect button
        self.connect_button.setEnabled(True)
        self.connect_button.setText("Connect")
        
        if result['status'] == 'success':
            QMessageBox.information(self, "Connection Successful", result['message'])
            # Emit signal to go to remote connection page with connection params
            self.connect_requested.emit(result)
        else:
            QMessageBox.critical(self, "Connection Failed", result['message'])

    def _handle_back_click(self):
        """Handle back button click"""
        self.back_requested.emit()

    def _handle_tab_click(self, clicked_button):
        """Handle tab button clicks"""
        tab_text = clicked_button.text()
        super()._handle_tab_click(clicked_button)

class ProcessSelectionDialog(QDialog):
    def __init__(self, processes, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Processes to Dump")
        self.selected_pids = []
        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.MultiSelection)
        for pid, name in processes:
            item = QListWidgetItem(f"{pid}: {name}")
            item.setData(1, pid)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)
        btn = QPushButton("Dump Selected Processes")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

    def get_selected_pids(self):
        return [item.data(1) for item in self.list_widget.selectedItems()]

