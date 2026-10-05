"""Remote connection page: acquire artifacts, files and memory from the connected host."""
import glob
import json
import logging
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QSizePolicy, QHeaderView, QMessageBox, QProgressDialog, QDialog, QListWidget, QListWidgetItem,
    QAbstractItemView, QFileDialog
)
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtCore import Qt, pyqtSignal, QThread, pyqtSignal as Signal

from .base_page import BasePage, COLOR_ORANGE, COLOR_DARK, TAB_NAMES
from services.evidence_store import record_evidence, list_evidence, human_size
from utils.network import host_reachable
from utils.paths import (NO_WINDOW, PSEXEC_EXE, WINPMEM_EXE, PROCDUMP_EXE, RAWCOPY_EXE, PROJECT_ROOT, asset,
                         case_subdir, CASE_EVIDENCE_SUBDIR)

logger = logging.getLogger(__name__)

FONT_CARD = QFont("Cascadia Mono", 16, QFont.Weight.Bold)
FONT_TABLE_HEADER = QFont("Cascadia Mono", 13, QFont.Weight.Bold)
FONT_TABLE = QFont("Cascadia Mono", 12)
FONT_BTN = QFont("Cascadia Mono", 16, QFont.Weight.Bold)
FONT_SIDEBAR_LABEL = QFont("Cascadia Mono", 12, QFont.Weight.Bold)

# Artifacts offered by the "Targeted locations" dialog. ``locked`` items are copied
# with RawCopy through PsExec because the OS keeps them open.
TARGETED_ARTIFACTS = [
    {"desc": "All users - Desktop", "path": r"C:\Users\*\Desktop\*", "locked": False},
    {"desc": "All users - Documents", "path": r"C:\Users\*\Documents\*", "locked": False},
    {"desc": "All users - Downloads", "path": r"C:\Users\*\Downloads\*", "locked": False},
    {"desc": "Browser profiles (Edge/Chrome)", "path": r"C:\Users\*\AppData\Local\{Microsoft\Edge,Google\Chrome}\User Data\Default\{History,Bookmarks,Login Data,Network\Cookies}", "locked": False},
    {"desc": "User registry hives (NTUSER.DAT)", "path": r"C:\Users\*\NTUSER.DAT", "locked": True},
    {"desc": "System registry hives", "path": r"C:\Windows\System32\config\{SAM,SYSTEM,SOFTWARE,SECURITY}", "locked": True},
    {"desc": "SRUM database", "path": r"C:\Windows\System32\sru\SRUDB.dat", "locked": True},
    {"desc": "Amcache", "path": r"C:\Windows\appcompat\Programs\Amcache.hve", "locked": True},
    {"desc": "Windows Event Logs (Security, System, Application)", "path": r"C:\Windows\System32\winevt\Logs\{Security,System,Application}.evtx", "locked": True},
    {"desc": "Prefetch files", "path": r"C:\Windows\Prefetch\*.pf", "locked": False},
    {"desc": "Scheduled tasks", "path": r"C:\Windows\System32\Tasks\*", "locked": False},
]


def expand_braces(pattern: str) -> list[str]:
    """Expand {a,b} alternatives in a path pattern."""
    start = pattern.find("{")
    if start == -1:
        return [pattern]
    end = pattern.find("}", start)
    if end == -1:
        return [pattern]
    results = []
    for option in pattern[start + 1:end].split(","):
        results.extend(expand_braces(pattern[:start] + option + pattern[end + 1:]))
    return results


def psexec_base(params: dict) -> list[str]:
    return [PSEXEC_EXE, f"\\\\{params['remote_ip']}", "-accepteula", "-u", f"{params['remote_domain']}\\{params['remote_user']}",
            "-p", params["remote_password"], "-h"]


def run_quiet(command, check=True, timeout=None, **kwargs):
    return subprocess.run(command, check=check, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          creationflags=NO_WINDOW, timeout=timeout, **kwargs)


class TargetedAcquisitionThread(QThread):
    """Copy selected artifact groups from the remote host into the case folder."""
    progress_update = Signal(str)
    acquisition_complete = Signal(list, list)  # copied files, errors
    acquisition_failed = Signal(str)

    def __init__(self, params, artifacts, destination, parent=None):
        super().__init__(parent)
        self.params, self.artifacts, self.destination = params, artifacts, destination

    def run(self):
        ip = self.params["remote_ip"]
        share = f"\\\\{ip}\\C$"
        copied, errors = [], []
        try:
            self.progress_update.emit("Connecting to the administrative share ...")
            run_quiet(["net", "use", share, self.params["remote_password"], f"/user:{self.params['remote_domain']}\\{self.params['remote_user']}"], timeout=60)
        except subprocess.CalledProcessError as error:
            self.acquisition_failed.emit(f"Could not connect to {share}: {(error.stderr or error.stdout or '').strip()}")
            return
        try:
            for artifact in self.artifacts:
                if artifact["locked"]:
                    self._acquire_locked(artifact, share, copied, errors)
                else:
                    self._acquire_plain(artifact, share, copied, errors)
        finally:
            run_quiet(["net", "use", share, "/delete", "/y"], check=False)
        self.acquisition_complete.emit(copied, errors)

    def _target_dir(self, artifact):
        safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in artifact["desc"]).strip().replace(" ", "_")
        return os.path.join(self.destination, safe)

    def _acquire_plain(self, artifact, share, copied, errors):
        target_root = self._target_dir(artifact)
        for pattern in expand_braces(artifact["path"]):
            unc_pattern = share + pattern[2:]  # replace "C:" by \\ip\C$
            matches = glob.glob(unc_pattern, recursive=False)
            self.progress_update.emit(f"{artifact['desc']}: {len(matches)} item(s) for {pattern}")
            for source in matches:
                relative = source[len(share) + 1:]
                destination = os.path.join(target_root, relative)
                try:
                    if os.path.isdir(source):
                        shutil.copytree(source, destination, dirs_exist_ok=True)
                        for root, _dirs, files in os.walk(destination):
                            copied.extend(os.path.join(root, f) for f in files)
                    else:
                        os.makedirs(os.path.dirname(destination), exist_ok=True)
                        shutil.copy2(source, destination)
                        copied.append(destination)
                except OSError as error:
                    errors.append(f"{source}: {error}")

    def _acquire_locked(self, artifact, share, copied, errors):
        if not os.path.isfile(RAWCOPY_EXE):
            errors.append("RawCopy.exe missing in the application folder")
            return
        target_root = self._target_dir(artifact)
        os.makedirs(target_root, exist_ok=True)
        remote_tmp = f"C:\\Windows\\Temp\\anubis_{uuid.uuid4().hex[:8]}"
        remote_tmp_unc = share + remote_tmp[2:]
        try:
            os.makedirs(remote_tmp_unc, exist_ok=True)
            shutil.copy2(RAWCOPY_EXE, os.path.join(remote_tmp_unc, "RawCopy.exe"))
        except OSError as error:
            errors.append(f"Could not stage RawCopy on the remote host: {error}")
            return
        for pattern in expand_braces(artifact["path"]):
            unc_pattern = share + pattern[2:]
            matches = glob.glob(unc_pattern) if any(ch in pattern for ch in "*?") else [unc_pattern]
            for source in matches:
                remote_path = "C:" + source[len(share):]
                self.progress_update.emit(f"RawCopy {remote_path} ...")
                try:
                    run_quiet([*psexec_base(self.params), f"{remote_tmp}\\RawCopy.exe", f"/FileNamePath:{remote_path}",
                               f"/OutputPath:{remote_tmp}"], check=False, timeout=600)
                    staged = os.path.join(remote_tmp_unc, os.path.basename(remote_path))
                    if not os.path.isfile(staged):
                        errors.append(f"{remote_path}: RawCopy produced no output (file may not exist)")
                        continue
                    relative = remote_path[3:]
                    destination = os.path.join(target_root, relative)
                    os.makedirs(os.path.dirname(destination), exist_ok=True)
                    shutil.move(staged, destination)
                    copied.append(destination)
                except (OSError, subprocess.SubprocessError) as error:
                    errors.append(f"{remote_path}: {error}")
        try:
            run_quiet([*psexec_base(self.params), "cmd", "/c", f"rmdir /S /Q {remote_tmp}"], check=False, timeout=120)
        except subprocess.SubprocessError:
            pass


class WebBrowserThread(QThread):
    """Runs the external file browser helper and waits for it to close."""
    browser_closed = Signal()

    def __init__(self, command, env=None, parent=None):
        super().__init__(parent)
        self.command = command
        self.env = env

    def run(self):
        try:
            process = subprocess.Popen(self.command, env=self.env, creationflags=NO_WINDOW)
            process.wait()
        except Exception as error:  # noqa: BLE001
            logger.error("Failed to run file browser process: %s", error)
        finally:
            self.browser_closed.emit()


class PingThread(QThread):
    result = Signal(bool)

    def __init__(self, ip, parent=None):
        super().__init__(parent)
        self.ip = ip

    def run(self):
        self.result.emit(host_reachable(self.ip, timeout_ms=2000))


class RemoteConnectionPage(BasePage):
    back_requested = pyqtSignal()
    analysis_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.connection_params = None
        self.browser_thread = None
        self.acquisition_thread = None
        self.ping_thread = None
        self.progress_dialog = None
        self.selected_case_path = None
        self.setup_page_content()

    def set_connection_params(self, params):
        self.connection_params = params
        self._update_sidebar_info()

    def set_case_path(self, case_path):
        self.selected_case_path = case_path
        self._reload_evidence_table()

    def showEvent(self, event):
        """Refresh the table whenever the page is shown: other pages add evidence too."""
        super().showEvent(event)
        self._reload_evidence_table()

    # ---------------------------------------------------------------- layout
    def setup_page_content(self):
        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addLayout(self._setup_tab_bar(TAB_NAMES))
        self.main_layout.addSpacing(20)

        main_hbox = QHBoxLayout()
        main_hbox.setSpacing(30)
        main_hbox.setContentsMargins(40, 0, 40, 0)
        self.sidebar = self._sidebar()
        main_hbox.addWidget(self.sidebar)

        center_content = QWidget()
        center_vbox = QVBoxLayout(center_content)
        center_vbox.setSpacing(20)
        center_vbox.setContentsMargins(0, 0, 0, 0)

        cards_hbox = QHBoxLayout()
        cards_hbox.setSpacing(60)
        cards_hbox.addWidget(self._card("TARGETED\nLOCATIONS", asset("targeted locationsAsset 24@4x.png"), self._handle_targeted_locations_click))
        cards_hbox.addWidget(self._card("FILES &\nFOLDERS", asset("file_foldersAsset 25@4x.png"), self._handle_files_folders_click))
        cards_hbox.addWidget(self._card("MEMORY", asset("memoryAsset 26@4x.png"), self._handle_memory_click))
        center_vbox.addLayout(cards_hbox)

        self.evidence_table = self._evidence_table()
        center_vbox.addWidget(self.evidence_table, 1)

        buttons = QHBoxLayout()
        back_btn = self.create_styled_button("Back", self._handle_back_click, COLOR_DARK, "white")
        buttons.addWidget(back_btn, alignment=Qt.AlignLeft)
        buttons.addStretch()
        analyze_btn = self.create_styled_button("ANALYZE EVIDENCES", self.analysis_requested.emit)
        analyze_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        buttons.addWidget(analyze_btn, alignment=Qt.AlignRight)
        center_vbox.addLayout(buttons)

        main_hbox.addWidget(center_content, stretch=1)
        self.main_layout.addLayout(main_hbox, 1)
        self.main_layout.addSpacing(20)

    def _sidebar(self):
        sidebar = QWidget()
        sidebar.setFixedWidth(280)
        vbox = QVBoxLayout(sidebar)
        vbox.setContentsMargins(16, 24, 16, 24)
        vbox.setSpacing(10)
        icon = QLabel()
        pix = QPixmap(asset("lap_iconAsset 22@4x.png"))
        if not pix.isNull():
            icon.setPixmap(pix.scaled(220, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        icon.setAlignment(Qt.AlignCenter)
        vbox.addWidget(icon)
        self.info_labels = {}
        for label in ("Computer name:", "Username:", "End point IP:", "Computer State:"):
            row = QLabel()
            row.setFont(FONT_SIDEBAR_LABEL)
            row.setWordWrap(True)
            vbox.addWidget(row)
            self.info_labels[label] = row
        self._update_sidebar_info()
        refresh = QPushButton("Refresh")
        refresh.setFont(FONT_SIDEBAR_LABEL)
        refresh.setFixedWidth(110)
        refresh.setStyleSheet(f"""
            QPushButton {{ background-color: {COLOR_DARK}; color: white; border-radius: 8px; padding: 6px 0; border: none; }}
            QPushButton:hover {{ background-color: {COLOR_ORANGE}; }}
        """)
        refresh.clicked.connect(self._handle_refresh_click)
        vbox.addWidget(refresh, alignment=Qt.AlignLeft)
        vbox.addStretch()
        sidebar.setStyleSheet("background: white; border-radius: 18px;")
        return sidebar

    def _update_sidebar_info(self, state=None):
        params = self.connection_params or {}
        connected = bool(params) if state is None else state
        color = "#2e7d32" if connected else "#d32f2f"
        text = "Connected" if connected else ("Unreachable" if params else "Disconnected")
        self.info_labels["Computer name:"].setText(f'<b>Computer name:</b> {params.get("computer_name", params.get("remote_ip", "Not connected"))}')
        self.info_labels["Username:"].setText(f'<b>Username:</b> {params.get("remote_domain", "")}\\{params.get("remote_user", "")}' if params else "<b>Username:</b> Not connected")
        self.info_labels["End point IP:"].setText(f'<b>End point IP:</b> {params.get("remote_ip", "Not connected")}')
        self.info_labels["Computer State:"].setText(f'<b>Computer State:</b> <span style="color:{color};">{text} ●</span>')

    def _card(self, title, icon_path, callback):
        card = QPushButton()
        card.setStyleSheet("""
            QPushButton { border: 2px solid black; border-radius: 10px; background: white; padding: 0px; }
            QPushButton:hover { background-color: #f5f5f5; }
            QPushButton:pressed { background-color: #e0e0e0; }
        """)
        card.setFixedSize(280, 200)
        card.setCursor(Qt.PointingHandCursor)
        layout = QVBoxLayout(card)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)
        icon = QLabel()
        pix = QPixmap(icon_path)
        if not pix.isNull():
            icon.setPixmap(pix.scaled(110, 110, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("background: transparent;")
        layout.addWidget(icon)
        title_label = QLabel(title)
        title_label.setFont(FONT_CARD)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("background: transparent;")
        layout.addWidget(title_label)
        card.clicked.connect(callback)
        return card

    def _evidence_table(self):
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(["Item", "Type", "Acquired at", "Size", ""])
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        table.setColumnWidth(4, 130)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setShowGrid(False)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setFont(FONT_TABLE_HEADER)
        table.setFont(FONT_TABLE)
        table.setStyleSheet(f"""
            QTableWidget {{ background-color: white; border: 1px solid {COLOR_DARK}; border-radius: 8px; gridline-color: transparent; }}
            QHeaderView::section {{ background-color: {COLOR_DARK}; color: white; padding: 12px 10px; border: none; border-right: 1px solid #4A535C; }}
            QTableWidget::item {{ padding-left: 10px; border-bottom: 1px solid #ddd; }}
        """)
        table.setMinimumHeight(260)
        return table

    def _reload_evidence_table(self):
        self.evidence_table.setRowCount(0)
        if not self.selected_case_path:
            return
        for descriptor in list_evidence(self.selected_case_path):
            for item in descriptor.get("files", []):
                self.add_evidence_row(item.get("name", ""), human_size(item.get("size")), descriptor.get("type", ""),
                                      descriptor.get("timestamp", ""), item.get("path"))

    def add_evidence_row(self, file_name, size_str, evidence_type="", timestamp=None, path=None):
        table = self.evidence_table
        row = table.rowCount()
        table.insertRow(row)
        table.setRowHeight(row, 44)
        timestamp = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for col, value in enumerate((file_name, evidence_type, timestamp.replace("T", " "), size_str)):
            item = QTableWidgetItem(str(value))
            item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            if col == 0 and path:
                item.setToolTip(path)
            table.setItem(row, col, item)
        open_btn = QPushButton("OPEN")
        open_btn.setFont(QFont("Cascadia Mono", 9, QFont.Weight.Bold))
        open_btn.setStyleSheet(f"QPushButton {{ background-color: {COLOR_DARK}; color: white; border-radius: 5px; padding: 5px 18px; border: none; }} QPushButton:hover {{ background-color: {COLOR_ORANGE}; }}")
        open_btn.clicked.connect(lambda _c, p=path: self._open_evidence(p))
        cell = QWidget()
        layout = QHBoxLayout(cell)
        layout.addWidget(open_btn)
        layout.setAlignment(Qt.AlignRight)
        layout.setContentsMargins(0, 0, 10, 0)
        table.setCellWidget(row, 4, cell)

    @staticmethod
    def _open_evidence(path):
        if path and os.path.exists(path):
            os.startfile(os.path.dirname(path) if os.path.isfile(path) else path)

    # ------------------------------------------------------------- actions
    def _require_connection(self) -> bool:
        if not self.connection_params:
            QMessageBox.warning(self, "No Connection", "Please establish a remote connection first.")
            return False
        return True

    def _require_case(self) -> bool:
        if not self.selected_case_path:
            QMessageBox.warning(self, "No Case", "Select or create a case first so evidence can be stored in it.")
            return False
        return True

    def _show_progress(self, title, label):
        self.progress_dialog = QProgressDialog(label, None, 0, 0, self)
        self.progress_dialog.setWindowTitle(title)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setMinimumWidth(520)
        self.progress_dialog.show()

    def _handle_targeted_locations_click(self):
        if not self._require_connection() or not self._require_case():
            return
        dialog = TargetedLocationsDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return
        selected = dialog.get_selected_artifacts()
        destination = os.path.join(case_subdir(self.selected_case_path, CASE_EVIDENCE_SUBDIR), f"targeted_{datetime.now():%Y%m%d_%H%M%S}")
        self._show_progress("Targeted acquisition", "Starting acquisition ...")
        self.acquisition_thread = TargetedAcquisitionThread(self.connection_params, selected, destination)
        self.acquisition_thread.progress_update.connect(self.progress_dialog.setLabelText)
        self.acquisition_thread.acquisition_complete.connect(lambda files, errors: self._on_targeted_complete(files, errors, destination))
        self.acquisition_thread.acquisition_failed.connect(self._on_acquisition_failed)
        self.acquisition_thread.start()

    def _on_targeted_complete(self, files, errors, destination):
        self.progress_dialog.close()
        if files:
            record_evidence(self.selected_case_path, files, "targeted_locations",
                            source=self.connection_params.get("remote_ip", ""), notes="; ".join(errors[:20]), compute_hashes=len(files) <= 200)
            self._reload_evidence_table()
        message = f"Copied {len(files)} file(s) to\n{destination}"
        if errors:
            message += f"\n\n{len(errors)} item(s) could not be copied:\n" + "\n".join(errors[:8])
        (QMessageBox.warning if errors and not files else QMessageBox.information)(self, "Targeted acquisition", message)

    def _on_acquisition_failed(self, error_message):
        if self.progress_dialog:
            self.progress_dialog.close()
        QMessageBox.critical(self, "Acquisition Failed", error_message)

    def _handle_files_folders_click(self):
        if not self._require_connection() or not self._require_case():
            return
        if self.browser_thread and self.browser_thread.isRunning():
            QMessageBox.information(self, "In Progress", "File browser is already running.")
            return
        script_path = os.path.join(PROJECT_ROOT, "utils", "file_browser_launcher.py")
        params = self.connection_params
        command = [sys.executable, script_path, params["remote_ip"], params["remote_domain"], params["remote_user"]]
        # Secrets go through the environment, not the command line, so they do not show in the process list.
        env = dict(os.environ)
        env.update({
            "ANUBIS_REMOTE_PASSWORD": params["remote_password"],
            "ANUBIS_FB_USER": params.get("fb_user", ""),
            "ANUBIS_FB_PASSWORD": params.get("fb_password", ""),
            "ANUBIS_FB_DB": params.get("fb_db", ""),
        })
        self.browser_thread = WebBrowserThread(command, env=env)
        self.browser_thread.browser_closed.connect(self._on_browser_closed)
        self.browser_thread.start()
        QMessageBox.information(self, "Browser Launched",
                                "The remote file browser opens in a separate window. Download the files you need, then close it: "
                                "you will be asked which downloaded files to add to the case.")

    def _on_browser_closed(self):
        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        files, _ = QFileDialog.getOpenFileNames(self, "Select downloaded files to add as evidence", downloads, "All files (*)")
        if not files:
            return
        destination = os.path.join(case_subdir(self.selected_case_path, CASE_EVIDENCE_SUBDIR), f"files_{datetime.now():%Y%m%d_%H%M%S}")
        os.makedirs(destination, exist_ok=True)
        stored = []
        for source in files:
            target = os.path.join(destination, os.path.basename(source))
            try:
                shutil.copy2(source, target)
                stored.append(target)
            except OSError as error:
                QMessageBox.warning(self, "Copy failed", f"{source}: {error}")
        if stored:
            record_evidence(self.selected_case_path, stored, "remote_files", source=self.connection_params.get("remote_ip", ""))
            self._reload_evidence_table()

    def _handle_memory_click(self):
        if not self._require_connection() or not self._require_case():
            return
        MemoryOptionsDialog(self).exec_()

    def _handle_refresh_click(self):
        if not self.connection_params:
            return
        self.ping_thread = PingThread(self.connection_params["remote_ip"])
        self.ping_thread.result.connect(lambda ok: self._update_sidebar_info(ok))
        self.ping_thread.start()
        self._reload_evidence_table()

    def _handle_back_click(self):
        self.back_requested.emit()


class TargetedLocationsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Targeted Locations Acquisition")
        self.setModal(True)
        self.resize(900, 520)
        self.selected_artifacts = []
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        title = QLabel("Select items to acquire from the target machine")
        title.setFont(QFont("Cascadia Mono", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        hint = QLabel("Locked system files (registry hives, SRUM, event logs) are copied with RawCopy through PsExec; everything else through the C$ share.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Description", "Path pattern", "Method"])
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setRowCount(len(TARGETED_ARTIFACTS))
        for i, artifact in enumerate(TARGETED_ARTIFACTS):
            item_desc = QTableWidgetItem(artifact["desc"])
            item_desc.setFlags(item_desc.flags() | Qt.ItemIsUserCheckable)
            item_desc.setCheckState(Qt.Unchecked)
            self.table.setItem(i, 0, item_desc)
            self.table.setItem(i, 1, QTableWidgetItem(artifact["path"]))
            self.table.setItem(i, 2, QTableWidgetItem("RawCopy (locked)" if artifact["locked"] else "Share copy"))
        self.table.resizeRowsToContents()
        layout.addWidget(self.table)

        button_layout = QHBoxLayout()
        dump_button = QPushButton("Acquire")
        dump_button.setFont(FONT_BTN)
        dump_button.setCursor(Qt.PointingHandCursor)
        dump_button.setStyleSheet(f"QPushButton {{ background-color: {COLOR_ORANGE}; color: white; border-radius: 8px; padding: 10px 40px; border: none; }} QPushButton:hover {{ background-color: #E6840D; }}")
        dump_button.clicked.connect(self.on_dump)
        close_button = QPushButton("Close")
        close_button.setFont(FONT_BTN)
        close_button.setCursor(Qt.PointingHandCursor)
        close_button.setStyleSheet(f"QPushButton {{ background-color: {COLOR_DARK}; color: white; border-radius: 8px; padding: 10px 40px; border: none; }} QPushButton:hover {{ background-color: #3C454E; }}")
        close_button.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(dump_button)
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)

    def on_dump(self):
        self.selected_artifacts = [TARGETED_ARTIFACTS[i] for i in range(self.table.rowCount()) if self.table.item(i, 0).checkState() == Qt.Checked]
        if not self.selected_artifacts:
            QMessageBox.warning(self, "No Selection", "Please select at least one item to acquire.")
            return
        self.accept()

    def get_selected_artifacts(self):
        return self.selected_artifacts


class MemoryOptionsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle("Memory Remote Acquisition")
        self.thread = None
        self.progress_dialog = None
        self.setup_ui()

    def setup_ui(self):
        self.setFixedSize(600, 300)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 20)
        main_layout.setSpacing(0)
        header = QLabel("Memory Remote Acquisition Options")
        header.setFont(QFont("Cascadia Mono", 16, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet(f"background-color: {COLOR_DARK}; color: white; padding: 16px;")
        main_layout.addWidget(header)
        main_layout.addSpacing(24)

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(20)
        buttons_layout.setAlignment(Qt.AlignCenter)
        full_dump_btn = QPushButton("Full memory dump\n(winpmem)")
        specific_dump_btn = QPushButton("Dump specific\nprocesses (procdump)")
        full_dump_btn.clicked.connect(self.full_memory_dump)
        specific_dump_btn.clicked.connect(self.dump_specific_processes)
        btn_style = f"""
            QPushButton {{ background-color: {COLOR_DARK}; color: white; border-radius: 8px; padding: 15px 25px;
                           font-family: 'Cascadia Mono'; font-size: 14px; font-weight: bold; }}
            QPushButton:hover {{ background-color: #3C454E; }}
        """
        full_dump_btn.setStyleSheet(btn_style)
        specific_dump_btn.setStyleSheet(btn_style)
        buttons_layout.addWidget(full_dump_btn)
        buttons_layout.addWidget(specific_dump_btn)
        main_layout.addLayout(buttons_layout)
        main_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setFont(QFont("Cascadia Mono", 12, QFont.Weight.Bold))
        close_btn.setStyleSheet(f"QPushButton {{ background-color: {COLOR_ORANGE}; color: white; border-radius: 8px; padding: 10px 40px; border: none; }} QPushButton:hover {{ background-color: #E6840D; }}")
        close_btn.clicked.connect(self.accept)
        main_layout.addWidget(close_btn, alignment=Qt.AlignCenter)
        self.setStyleSheet(f"background-color: white; border: 1px solid {COLOR_DARK};")

    def _show_progress_dialog(self, title, label):
        self.progress_dialog = QProgressDialog(label, None, 0, 0, self)
        self.progress_dialog.setWindowTitle(title)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setMinimumWidth(480)
        self.progress_dialog.show()

    def _evidence_dir(self):
        return case_subdir(self.parent().selected_case_path, CASE_EVIDENCE_SUBDIR)

    def full_memory_dump(self):
        self._show_progress_dialog("Full Memory Dump", "Starting full memory dump...")
        self.thread = MemoryAcquisitionThread("full_dump", self.parent().connection_params, output_dir=self._evidence_dir())
        self.thread.progress_update.connect(self.progress_dialog.setLabelText)
        self.thread.acquisition_complete.connect(lambda files: self.on_acquisition_complete(files, "remote_full_memory_dump"))
        self.thread.acquisition_failed.connect(self.on_acquisition_failed)
        self.thread.start()

    def dump_specific_processes(self):
        self._show_progress_dialog("Process Dump", "Fetching remote process list...")
        self.thread = MemoryAcquisitionThread("list_processes", self.parent().connection_params)
        self.thread.process_list_ready.connect(self.on_process_list_ready)
        self.thread.acquisition_failed.connect(self.on_acquisition_failed)
        self.thread.start()

    def on_process_list_ready(self, processes):
        self.progress_dialog.close()
        if not processes:
            QMessageBox.critical(self, "Error", "Could not retrieve remote process list.")
            return
        dialog = ProcessSelectionDialog(processes, self)
        if dialog.exec_() != QDialog.Accepted:
            return
        pids = dialog.get_selected_pids()
        if not pids:
            QMessageBox.warning(self, "No Selection", "No processes were selected.")
            return
        self._show_progress_dialog("Process Dump", f"Starting dump for {len(pids)} processes...")
        self.thread = MemoryAcquisitionThread("process_dump", self.parent().connection_params, pids=pids, output_dir=self._evidence_dir())
        self.thread.progress_update.connect(self.progress_dialog.setLabelText)
        self.thread.acquisition_complete.connect(lambda files: self.on_acquisition_complete(files, "remote_process_dump"))
        self.thread.acquisition_failed.connect(self.on_acquisition_failed)
        self.thread.start()

    def on_acquisition_complete(self, dump_files, evidence_type):
        self.progress_dialog.close()
        page = self.parent()
        if dump_files:
            record_evidence(page.selected_case_path, dump_files, evidence_type, source=page.connection_params.get("remote_ip", ""),
                            compute_hashes=evidence_type != "remote_full_memory_dump")
            page._reload_evidence_table()
            QMessageBox.information(self, "Success", f"Acquired {len(dump_files)} dump file(s) into\n{self._evidence_dir()}")
        else:
            QMessageBox.warning(self, "Nothing acquired", "No dump files were produced.")
        self.accept()

    def on_acquisition_failed(self, error_message):
        self.progress_dialog.close()
        QMessageBox.critical(self, "Acquisition Failed", error_message)


class ProcessSelectionDialog(QDialog):
    def __init__(self, processes, parent=None):
        super().__init__(parent)
        self.processes = processes
        self.selected_pids = []
        self.setWindowTitle("Select Processes to Dump")
        self.setup_ui()

    def setup_ui(self):
        self.resize(520, 480)
        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        for pid, name in self.processes:
            item = QListWidgetItem(f"{pid}: {name}")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.list_widget.addItem(item)
        dump_button = QPushButton("Dump Selected Processes")
        dump_button.clicked.connect(self.on_submit)
        layout.addWidget(self.list_widget)
        layout.addWidget(dump_button)

    def on_submit(self):
        self.selected_pids = [self.processes[i][0] for i in range(self.list_widget.count()) if self.list_widget.item(i).checkState() == Qt.Checked]
        self.accept()

    def get_selected_pids(self):
        return self.selected_pids


class MemoryAcquisitionThread(QThread):
    progress_update = Signal(str)
    acquisition_complete = Signal(list)
    acquisition_failed = Signal(str)
    process_list_ready = Signal(list)

    def __init__(self, mode, connection_params, pids=None, output_dir=None, parent=None):
        super().__init__(parent)
        self.mode, self.params, self.pids = mode, connection_params, pids
        self.output_dir = output_dir or os.getcwd()

    def run(self):
        try:
            if self.mode == "full_dump":
                self._run_full_dump()
            elif self.mode == "list_processes":
                self._run_list_processes()
            elif self.mode == "process_dump":
                self._run_process_dump()
        except (subprocess.CalledProcessError, subprocess.SubprocessError, FileNotFoundError, OSError) as error:
            message = f"An error occurred: {error}"
            if getattr(error, "stderr", None):
                message += f"\nStderr: {error.stderr}"
            self.acquisition_failed.emit(message)

    def _remote_temp(self, prefix):
        folder = f"{prefix}_{uuid.uuid4().hex[:8]}"
        remote_dir = f"C:\\Windows\\Temp\\{folder}"
        unc_dir = f"\\\\{self.params['remote_ip']}\\C$\\Windows\\Temp\\{folder}"
        return remote_dir, unc_dir

    def _run_full_dump(self):
        if not os.path.isfile(WINPMEM_EXE):
            self.acquisition_failed.emit(f"Tool not found: {WINPMEM_EXE}")
            return
        remote_dir, unc_dir = self._remote_temp("mem_acq")
        remote_dump = f"{remote_dir}\\memory.raw"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        local_dump = os.path.join(self.output_dir, f"memory_{self.params['remote_ip'].replace('.', '_')}_{stamp}.raw")
        self.progress_update.emit("Creating remote temp directory ...")
        run_quiet([*psexec_base(self.params), "cmd", "/c", "mkdir", remote_dir], timeout=120)
        self.progress_update.emit("Copying winpmem to remote host ...")
        run_quiet(["xcopy", WINPMEM_EXE, unc_dir + "\\", "/Y"], timeout=300)
        self.progress_update.emit("Running winpmem on the remote host (this may take several minutes) ...")
        run_quiet([*psexec_base(self.params), "-s", f"{remote_dir}\\{os.path.basename(WINPMEM_EXE)}", remote_dump], check=False, timeout=3600)
        self.progress_update.emit("Copying memory image to the case folder ...")
        os.makedirs(self.output_dir, exist_ok=True)
        run_quiet(["robocopy", unc_dir, self.output_dir, "memory.raw", "/R:1", "/W:5", "/NP"], check=False, timeout=7200)
        staged = os.path.join(self.output_dir, "memory.raw")
        if not os.path.isfile(staged):
            self.acquisition_failed.emit("winpmem produced no image (is the target 64-bit Windows with an admin account?)")
            return
        os.replace(staged, local_dump)
        self.progress_update.emit("Cleaning up remote files ...")
        run_quiet([*psexec_base(self.params), "cmd", "/c", f"rmdir /S /Q {remote_dir}"], check=False, timeout=120)
        self.acquisition_complete.emit([local_dump])

    def _run_list_processes(self):
        result = run_quiet([*psexec_base(self.params), "tasklist", "/FO", "CSV"], timeout=120)
        lines = result.stdout.strip().splitlines()[1:]
        processes = parse_processes(lines)
        if not processes:
            self.acquisition_failed.emit(f"Could not parse remote process list. Raw output:\n{result.stdout[:2000]}")
            return
        self.process_list_ready.emit(processes)

    def _run_process_dump(self):
        if not os.path.isfile(PROCDUMP_EXE):
            self.acquisition_failed.emit(f"Tool not found: {PROCDUMP_EXE}")
            return
        remote_dir, unc_dir = self._remote_temp("proc_dump")
        self.progress_update.emit("Creating remote temp directory ...")
        run_quiet([*psexec_base(self.params), "cmd", "/c", "mkdir", remote_dir], timeout=120)
        self.progress_update.emit("Copying procdump to remote host ...")
        run_quiet(["xcopy", PROCDUMP_EXE, unc_dir + "\\", "/Y"], timeout=300)
        local_output_dir = os.path.join(self.output_dir, f"process_dumps_{datetime.now():%Y%m%d_%H%M%S}")
        os.makedirs(local_output_dir, exist_ok=True)
        local_files = []
        for index, pid in enumerate(self.pids):
            self.progress_update.emit(f"Dumping process {pid} ({index + 1}/{len(self.pids)}) ...")
            file_name = f"process_{pid}.dmp"
            run_quiet([*psexec_base(self.params), f"{remote_dir}\\procdump.exe", "-accepteula", "-ma", str(pid), f"{remote_dir}\\{file_name}"],
                      check=False, timeout=1800)
            run_quiet(["robocopy", unc_dir, local_output_dir, file_name, "/R:1", "/W:5", "/NP"], check=False, timeout=3600)
            local_path = os.path.join(local_output_dir, file_name)
            if os.path.isfile(local_path):
                local_files.append(local_path)
            else:
                logger.warning("Dump for PID %s was not produced", pid)
        self.progress_update.emit("Cleaning up remote files ...")
        run_quiet([*psexec_base(self.params), "cmd", "/c", f"rmdir /S /Q {remote_dir}"], check=False, timeout=120)
        self.acquisition_complete.emit(local_files)


def parse_processes(lines):
    processes = []
    for line in lines:
        parts = line.strip().strip('"').split('","')
        if len(parts) >= 2:
            try:
                processes.append((int(parts[1]), parts[0]))
            except ValueError:
                continue
    processes.sort(key=lambda x: x[0])
    return processes
