"""Remote acquisition page: connect to a target host and deploy the FileBrowser agent."""
import json
import logging
import os
import socket
import subprocess
import time

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, QFileDialog, QGroupBox, QMessageBox)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt, pyqtSignal, QThread, pyqtSignal as Signal

from .base_page import BasePage, COLOR_ORANGE, COLOR_DARK, TAB_NAMES
from utils.paths import NO_WINDOW, PSEXEC_EXE, FILEBROWSER_EXE, PROJECT_ROOT

logger = logging.getLogger(__name__)
LAST_CONNECTION_FILE = os.path.join(PROJECT_ROOT, "data", "last_connection.json")

FONT_LABEL = QFont("Cascadia Mono", 13)
FONT_GROUP = QFont("Cascadia Mono", 16, QFont.Weight.Bold)
FONT_SECTION = QFont("Cascadia Mono", 20, QFont.Weight.ExtraBold)


class RemoteConnectionThread(QThread):
    connection_result = Signal(dict)

    def __init__(self, connection_params):
        super().__init__()
        self.connection_params = connection_params

    def _fail(self, message):
        self.connection_result.emit({"status": "error", "message": message})

    def run(self):
        remote_ip = self.connection_params["ip_address"]
        remote_domain = self.connection_params["domain"]
        remote_user = self.connection_params["username"]
        remote_password = self.connection_params["password"]
        remote_share = f"\\\\{remote_ip}\\C$"
        try:
            if not os.path.isfile(PSEXEC_EXE):
                return self._fail(f"PsExec.exe not found at {PSEXEC_EXE}")
            if not os.path.isfile(FILEBROWSER_EXE):
                return self._fail(f"filebrowser.exe not found at {FILEBROWSER_EXE}")

            ping = subprocess.run(["ping", "-n", "1", "-w", "3000", remote_ip], capture_output=True, text=True, creationflags=NO_WINDOW)
            if ping.returncode != 0:
                return self._fail(f"{remote_ip} is not reachable (ping failed). Check the IP address and the network.")

            logger.info("Connecting to remote C$ share ...")
            net_use = subprocess.run(["net", "use", remote_share, remote_password, f"/user:{remote_domain}\\{remote_user}"],
                                     capture_output=True, text=True, creationflags=NO_WINDOW, timeout=60)
            if net_use.returncode != 0:
                return self._fail(f"Could not connect to {remote_share}:\n{(net_use.stderr or net_use.stdout).strip()}\n\n"
                                  "Check the credentials, that the account is a local administrator on the target, "
                                  "and that File and Printer Sharing (SMB) is enabled.")

            logger.info("Stopping any lingering remote filebrowser process ...")
            subprocess.run([PSEXEC_EXE, f"\\\\{remote_ip}", "-accepteula", "-u", f"{remote_domain}\\{remote_user}", "-p", remote_password,
                            "taskkill", "/F", "/IM", "filebrowser.exe"], check=False, capture_output=True, text=True,
                           creationflags=NO_WINDOW, timeout=120)

            logger.info("Copying filebrowser.exe to the remote C drive ...")
            copy = subprocess.run(["xcopy", FILEBROWSER_EXE, f"{remote_share}\\", "/Y"], capture_output=True, text=True,
                                  creationflags=NO_WINDOW, timeout=600)
            if copy.returncode != 0:
                return self._fail(f"Copying the agent failed:\n{(copy.stderr or copy.stdout).strip()}")

            logger.info("Launching filebrowser remotely via PsExec ...")
            subprocess.Popen([PSEXEC_EXE, f"\\\\{remote_ip}", "-accepteula", "-u", f"{remote_domain}\\{remote_user}", "-p", remote_password,
                              "-h", "C:\\filebrowser.exe", "--address", "0.0.0.0", "--port", "8080", "--noauth", "--root", "C:/"],
                             creationflags=NO_WINDOW)
            time.sleep(3)

            self.connection_result.emit({
                "status": "success",
                "message": f"Successfully connected to {remote_ip}",
                "remote_ip": remote_ip,
                "remote_domain": remote_domain,
                "remote_user": remote_user,
                "remote_password": remote_password,
                "computer_name": self._remote_hostname(remote_ip),
            })
        except subprocess.SubprocessError as error:
            self._fail(f"Connection failed: {error}")
        except Exception as error:  # noqa: BLE001
            self._fail(f"Unexpected error: {error}")
        finally:
            subprocess.run(["net", "use", remote_share, "/delete", "/y"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=NO_WINDOW)

    @staticmethod
    def _remote_hostname(remote_ip):
        try:
            return socket.gethostbyaddr(remote_ip)[0]
        except (socket.herror, socket.gaierror, OSError):
            return remote_ip


class RemoteAcquisitionPage(BasePage):
    back_requested = pyqtSignal()
    connect_requested = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.connection_thread = None
        self.selected_case_path = None
        self._saved = self._load_last_connection()
        self.setup_page_content()

    def set_case_path(self, case_path):
        self.selected_case_path = case_path

    @staticmethod
    def _load_last_connection():
        try:
            with open(LAST_CONNECTION_FILE, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, ValueError):
            return {}

    @staticmethod
    def _save_last_connection(params):
        try:
            os.makedirs(os.path.dirname(LAST_CONNECTION_FILE), exist_ok=True)
            with open(LAST_CONNECTION_FILE, "w", encoding="utf-8") as handle:
                json.dump({k: v for k, v in params.items() if k != "password"}, handle, indent=2)
        except OSError:
            pass

    # ---------------------------------------------------------------- layout
    def setup_page_content(self):
        self.main_layout.addLayout(self._setup_tab_bar(TAB_NAMES))
        self.main_layout.addSpacing(30)

        content_container = QWidget()
        content_container.setStyleSheet("QWidget { background-color: white; border-radius: 24px; }")
        content_container.setFixedSize(1500, 560)
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(40, 28, 40, 28)
        content_layout.setSpacing(14)

        def section(text):
            label = QLabel(text)
            label.setFont(FONT_SECTION)
            label.setStyleSheet(f"color: {COLOR_DARK};")
            content_layout.addWidget(label, alignment=Qt.AlignmentFlag.AlignLeft)

        def field(grid, column, label_text, widget):
            label = QLabel(label_text)
            label.setFont(FONT_LABEL)
            grid.addWidget(label, 0, column)
            grid.addWidget(widget, 1, column)

        section("NEW AGENT")
        grid1 = QGridLayout()
        grid1.setHorizontalSpacing(32)
        self.agent_name_input = self.create_styled_input()
        self.agent_name_input.setText(self._saved.get("agent_name", "anubis-agent"))
        field(grid1, 0, "Name", self.agent_name_input)
        location_field = QWidget()
        location_layout = QHBoxLayout(location_field)
        location_layout.setContentsMargins(0, 0, 0, 0)
        location_layout.setSpacing(0)
        self.agent_location_input = self.create_styled_input()
        self.agent_location_input.setText(self._saved.get("agent_location", FILEBROWSER_EXE))
        location_layout.addWidget(self.agent_location_input)
        location_layout.addWidget(self.create_folder_button(self._choose_agent_location, 48))
        field(grid1, 1, "Agent location on your machine", location_field)
        content_layout.addLayout(grid1)

        section("TARGET MACHINE")
        grid2 = QGridLayout()
        grid2.setHorizontalSpacing(32)
        self.ip_input = self.create_styled_input("e.g. 192.168.56.101")
        self.ip_input.setText(self._saved.get("ip_address", ""))
        field(grid2, 0, "IP address", self.ip_input)
        self.domain_input = self.create_styled_input("Domain, or . for a local account")
        self.domain_input.setText(self._saved.get("domain", "."))
        field(grid2, 1, "Domain (use . for a local account)", self.domain_input)
        content_layout.addLayout(grid2)

        section("CREDENTIALS (local administrator on the target)")
        grid3 = QGridLayout()
        grid3.setHorizontalSpacing(32)
        self.username_input = self.create_styled_input()
        self.username_input.setText(self._saved.get("username", ""))
        field(grid3, 0, "User name", self.username_input)
        self.password_input = self.create_styled_input(is_password=True)
        field(grid3, 1, "Password", self.password_input)
        content_layout.addLayout(grid3)
        content_layout.addStretch()

        self.main_layout.addWidget(content_container, alignment=Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addSpacing(24)

        buttons = QHBoxLayout()
        buttons.setSpacing(24)
        buttons.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.connect_button = self.create_styled_button("Connect", self._handle_connect)
        buttons.addWidget(self.connect_button)
        buttons.addWidget(self.create_styled_button("Back", self._handle_back_click, COLOR_DARK, "white"))
        self.main_layout.addLayout(buttons)
        self.main_layout.addStretch()

    def _choose_agent_location(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select agent executable", PROJECT_ROOT, "Executables (*.exe)")
        if path:
            self.agent_location_input.setText(path)

    # --------------------------------------------------------------- connect
    def _handle_connect(self):
        connection_params = {
            "agent_name": self.agent_name_input.text().strip(),
            "agent_location": self.agent_location_input.text().strip(),
            "ip_address": self.ip_input.text().strip(),
            "domain": self.domain_input.text().strip() or ".",
            "username": self.username_input.text().strip(),
            "password": self.password_input.text(),
        }
        error_style = self.get_input_style().replace("border: 2.5px solid #23292f;", "border: 2px solid #d32f2f; background-color: #ffebee;")
        missing = []
        for key, label, widget in (("agent_name", "Agent name", self.agent_name_input), ("ip_address", "IP address", self.ip_input),
                                   ("username", "Username", self.username_input), ("password", "Password", self.password_input)):
            if not connection_params[key]:
                missing.append(label)
                widget.setStyleSheet(error_style)
            else:
                widget.setStyleSheet(self.get_input_style())
        if missing:
            QMessageBox.warning(self, "Missing Fields", "Please fill in the following required fields:\n• " + "\n• ".join(missing))
            return

        self.connect_button.setEnabled(False)
        self.connect_button.setText("Connecting...")
        self.connection_thread = RemoteConnectionThread(connection_params)
        self.connection_thread.connection_result.connect(lambda result: self._on_connection_result(result, connection_params))
        self.connection_thread.start()

    def _on_connection_result(self, result, connection_params):
        self.connect_button.setEnabled(True)
        self.connect_button.setText("Connect")
        if result["status"] == "success":
            self._save_last_connection(connection_params)
            QMessageBox.information(self, "Connection Successful", result["message"])
            self.connect_requested.emit(result)
        else:
            QMessageBox.critical(self, "Connection Failed", result["message"])

    def _handle_back_click(self):
        self.back_requested.emit()
