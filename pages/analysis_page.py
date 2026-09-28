"""Analyze Evidence page: memory, web, SRUM, registry and USB analysis views."""
import csv
import html
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QComboBox, QGroupBox, QGridLayout,
    QStatusBar, QProgressBar, QFileDialog, QAction, QMenu, QApplication, QTabWidget, QTextEdit,
    QScrollArea, QListWidget, QListWidgetItem, QDialog, QTextBrowser, QCheckBox
)
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtCore import Qt, pyqtSignal, QThread, pyqtSignal as Signal, QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView

from .base_page import BasePage, COLOR_ORANGE, COLOR_DARK, TAB_NAMES
from services.registry_analyzer import RegistryAnalyzer, rawcopy_file, SYSTEM_HIVES
from services.web_artifact_extractor import extract_all_web_artifacts, extract_local_user, extract_local_profile
from services.usb_analyzer import get_usb_devices, get_usb_devices_from_hive, analyze_usb_forensics, usb_report_html
from services.srum_analyzer import analyze_srum
from services.memory_analyzer import (MemoryAnalyzer, load_json, classify_ip, scan_dumped_files_for_ips,
                                      collect_dumped_file_features, VirusTotalClient)
from services.evidence_store import record_evidence, human_size
from utils.paths import (case_subdir, memory_analysis_dir, CASE_MEMORY_SUBDIR, CASE_WEB_SUBDIR, CASE_SRUM_SUBDIR,
                         CASE_USB_SUBDIR, CASE_REGISTRY_SUBDIR, CASE_EVIDENCE_SUBDIR, SAMPLE_MEMORY_ANALYSIS_DIR)

FONT_UI = QFont("Segoe UI", 9)
FONT_UI_BOLD = QFont("Segoe UI", 10, QFont.Weight.Bold)
TABLE_STYLE = """
    QTableWidget { gridline-color: #dee2e6; background-color: white; alternate-background-color: #f8f9fa;
                   font-family: 'Segoe UI'; font-size: 9pt; }
    QTableWidget::item { padding: 4px; border-bottom: 1px solid #dee2e6; }
    QTableWidget::item:selected { background-color: #007bff; color: white; }
    QHeaderView::section { background-color: #343a40; color: white; padding: 6px; border: none; font-weight: bold; font-family: 'Segoe UI'; }
"""
SMALL_BUTTON = f"""
    QPushButton {{ background-color: {COLOR_DARK}; color: white; border: none; border-radius: 6px;
                   padding: 8px 14px; font-family: 'Segoe UI'; font-size: 10pt; font-weight: bold; }}
    QPushButton:hover {{ background-color: {COLOR_ORANGE}; }}
    QPushButton:disabled {{ background-color: #999; }}
"""
ACTION_BUTTON = f"""
    QPushButton {{ background-color: {COLOR_ORANGE}; color: white; border: none; border-radius: 8px;
                   padding: 8px 22px; font-family: 'Cascadia Mono'; font-size: 12pt; font-weight: bold; }}
    QPushButton:hover {{ background-color: #FF8C42; }}
"""
INPUT_STYLE = """
    QLineEdit { border: 1px solid #ced4da; border-radius: 4px; padding: 6px; font-family: 'Segoe UI'; font-size: 9pt; background: white; }
    QLineEdit:focus { border-color: #F57C1F; }
"""


class WorkerThread(QThread):
    """Run a callable in the background and deliver its result or error."""
    progress = Signal(str)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, function, *args, pass_progress=False, parent=None, **kwargs):
        super().__init__(parent)
        self.function, self.args, self.kwargs, self.pass_progress = function, args, kwargs, pass_progress
        self.cancelled = False

    def run(self):
        try:
            if self.pass_progress:
                self.kwargs["progress"] = self.progress.emit
            self.done.emit(self.function(*self.args, **self.kwargs))
        except Exception as error:  # noqa: BLE001 - surfaced to the GUI
            self.failed.emit(str(error))


class RegistryWorker(QThread):
    """Worker thread for registry operations."""
    progress_updated = pyqtSignal(str)
    operation_completed = pyqtSignal(str, bool, str)
    header_output = pyqtSignal(str)

    def __init__(self, analyzer, operation, **kwargs):
        super().__init__()
        self.analyzer, self.operation, self.kwargs = analyzer, operation, kwargs

    def run(self):
        self.analyzer.progress_updated.connect(self.progress_updated.emit)
        self.analyzer.header_output.connect(self.header_output.emit)
        try:
            function = getattr(self.analyzer, self.operation)
            success, message = function(**self.kwargs)
        except Exception as error:  # noqa: BLE001
            success, message = False, str(error)
        finally:
            self.analyzer.progress_updated.disconnect(self.progress_updated.emit)
            self.analyzer.header_output.disconnect(self.header_output.emit)
        self.operation_completed.emit(self.operation, success, message)


class HtmlDialog(QDialog):
    def __init__(self, title, html_content, parent=None, size=(1100, 750)):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(*size)
        layout = QVBoxLayout(self)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(html_content)
        layout.addWidget(browser)
        close = QPushButton("Close")
        close.setStyleSheet(SMALL_BUTTON)
        close.clicked.connect(self.accept)
        layout.addWidget(close, alignment=Qt.AlignRight)


def esc(value) -> str:
    return html.escape("" if value is None else str(value))


def render_table_html(title: str, rows: list, columns: list | None = None, max_rows: int = 2000, note: str = "") -> str:
    """Generic HTML table for a list of dicts (Volatility JSON etc.)."""
    if not rows:
        return f"<h3>{esc(title)}</h3><p style='color:#777'>No data available.</p>"
    if columns is None:
        columns = []
        for row in rows:
            for key in row.keys():
                if key not in columns and key not in ("__children", "Hexdump", "Disasm"):
                    columns.append(key)
    header = "".join(f"<th style='padding:6px;border:1px solid #ddd;text-align:left'>{esc(c)}</th>" for c in columns)
    body = ""
    for index, row in enumerate(rows[:max_rows]):
        style = "background-color:#f9f9f9;" if index % 2 == 0 else ""
        cells = "".join(f"<td style='padding:5px;border:1px solid #eee'>{esc(row.get(c, ''))}</td>" for c in columns)
        body += f"<tr style='{style}'>{cells}</tr>"
    more = f"<p style='color:#777'>Showing first {max_rows} of {len(rows)} rows.</p>" if len(rows) > max_rows else ""
    return (f"<div style='font-family:Segoe UI,sans-serif;font-size:10pt'><h3>{esc(title)}</h3>"
            f"{('<p>' + note + '</p>') if note else ''}<p style='color:#555'>{len(rows)} row(s)</p>"
            f"<table width='100%' style='border-collapse:collapse;font-size:9pt'><thead><tr style='background:#343a40;color:white'>{header}</tr></thead>"
            f"<tbody>{body}</tbody></table>{more}</div>")


class AnalysisPage(BasePage):
    back_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.connection_params = None
        self.selected_case_path = None
        self.worker = None
        self.memory_worker = None
        self.registry_worker_thread = None
        self.registry_analyzer = RegistryAnalyzer()
        self.usb_devices = []
        self.displayed_usb_devices = []
        self.memory_dir = memory_analysis_dir(None)
        self.setup_page_content()
        self._select_tab_programmatically("Analyze Evidence")

    # ------------------------------------------------------------ external
    def set_connection_params(self, params):
        self.connection_params = params
        if hasattr(self, "web_source_combo"):
            self.web_source_combo.setItemText(0, f"Remote host ({params.get('remote_ip')})" if params else "Remote host (not connected)")

    def set_case_path(self, case_path):
        self.selected_case_path = case_path
        if not case_path:
            return
        base_output = os.path.join(case_path, CASE_REGISTRY_SUBDIR)
        self.acquire_output_dir_input.setText(os.path.join(base_output, "acquired_hives"))
        self.analyze_input_dir.setText(os.path.join(base_output, "acquired_hives"))
        self.compare_output_dir.setText(os.path.join(base_output, "comparison_results"))
        self.logs_output_dir.setText(os.path.join(base_output, "recovered_hives"))
        self.memory_dir = memory_analysis_dir(case_path)
        self._update_memory_source_label()
        self.srum_output_label.setText(f"Results are saved to {os.path.join(case_path, CASE_SRUM_SUBDIR)}")
        self.case_banner.setText(f"Case: {os.path.basename(case_path)}")
        self.case_banner.setVisible(True)
        self._auto_fill_from_evidence()

    def _auto_fill_from_evidence(self):
        """Pre-fill SRUM / USB inputs with hives found in the case folder."""
        if not self.selected_case_path:
            return
        for root, _dirs, files in os.walk(self.selected_case_path):
            for name in files:
                lowered = name.lower()
                path = os.path.join(root, name)
                if lowered == "srudb.dat" and not self.srum_db_input.text():
                    self.srum_db_input.setText(path)
                elif lowered == "software" and not self.srum_hive_input.text():
                    self.srum_hive_input.setText(path)
                elif lowered == "system" and not self.usb_hive_input.text():
                    self.usb_hive_input.setText(path)

    def _case_dir(self, subdir: str) -> str | None:
        return case_subdir(self.selected_case_path, subdir) if self.selected_case_path else None

    def _require_case(self, feature: str) -> bool:
        if self.selected_case_path:
            return True
        QMessageBox.warning(self, "No Case Selected", f"Select or create a case first so that {feature} results can be stored in it.")
        return False

    def _busy(self) -> bool:
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "In Progress", "Another analysis is still running. Please wait for it to finish.")
            return True
        return False

    def _switch_right_panel_view(self, view_to_show):
        for view in (self.web_view_container, self.usb_view_container, self.registry_view_container,
                     self.srum_view_container, self.memory_view_container, self.placeholder_label):
            view.setVisible(view is view_to_show)

    # ------------------------------------------------------------- layout
    def setup_page_content(self):
        self.main_layout.addLayout(self._setup_tab_bar(TAB_NAMES))
        self.main_layout.addSpacing(12)

        self.case_banner = QLabel("")
        self.case_banner.setFont(QFont("Cascadia Mono", 12, QFont.Weight.Bold))
        self.case_banner.setStyleSheet(f"color: {COLOR_ORANGE}; padding-left: 40px;")
        self.case_banner.setVisible(False)
        self.main_layout.addWidget(self.case_banner)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)
        content_layout.setContentsMargins(40, 0, 40, 20)

        left_panel = QFrame()
        left_panel.setObjectName("artifactPanel")
        left_panel.setFixedWidth(220)
        left_panel.setStyleSheet("QFrame#artifactPanel { background-color: white; border-radius: 18px; }")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(20, 20, 20, 20)
        left_layout.setSpacing(15)
        left_layout.setAlignment(Qt.AlignTop)
        for artifact_name in ("MEMORY", "WEB", "SRUM", "REGISTRY", "USB"):
            button = QPushButton(artifact_name)
            button.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
            button.setStyleSheet(f"""
                QPushButton {{ background-color: {COLOR_DARK}; color: white; border: none; border-radius: 8px; padding: 12px; }}
                QPushButton:hover {{ background-color: {COLOR_ORANGE}; }}
            """)
            button.clicked.connect(lambda _checked, name=artifact_name: self.on_artifact_button_click(name))
            left_layout.addWidget(button)
        content_layout.addWidget(left_panel)

        self.right_panel = QFrame()
        self.right_panel.setObjectName("rightPanel")
        self.right_panel.setStyleSheet(f"QFrame#rightPanel {{ background-color: white; border: 2px solid {COLOR_DARK}; border-radius: 18px; }}")
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(6, 6, 6, 6)

        self.web_view_container = self._build_web_view()
        right_layout.addWidget(self.web_view_container)
        self.srum_view_container = self._build_srum_view()
        right_layout.addWidget(self.srum_view_container)
        self.usb_view_container = self._build_usb_view()
        right_layout.addWidget(self.usb_view_container)
        self.registry_view_container = self.create_registry_view()
        right_layout.addWidget(self.registry_view_container)
        self.memory_view_container = QWidget()
        self._setup_memory_analysis_view()
        right_layout.addWidget(self.memory_view_container)

        self.placeholder_label = QLabel("Select an artifact to view details")
        self.placeholder_label.setFont(QFont("Segoe UI", 16))
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.placeholder_label.setStyleSheet("color: #aaa; border: none;")
        right_layout.addWidget(self.placeholder_label)

        content_layout.addWidget(self.right_panel, 1)
        self.main_layout.addLayout(content_layout, 1)
        self._switch_right_panel_view(self.placeholder_label)

    # ---------------------------------------------------------- dispatch
    def on_artifact_button_click(self, artifact_name):
        if artifact_name == "MEMORY":
            self._switch_right_panel_view(self.memory_view_container)
            self._update_memory_source_label()
        elif artifact_name == "WEB":
            self._switch_right_panel_view(self.web_view_container)
        elif artifact_name == "USB":
            self._switch_right_panel_view(self.usb_view_container)
            if not self.usb_devices:
                self.scan_usb_devices()
        elif artifact_name == "REGISTRY":
            if self.selected_case_path:
                self.set_case_path(self.selected_case_path)
            self._switch_right_panel_view(self.registry_view_container)
        elif artifact_name == "SRUM":
            self._switch_right_panel_view(self.srum_view_container)

    # ============================================================ MEMORY
    def _setup_memory_analysis_view(self):
        memory_layout = QVBoxLayout(self.memory_view_container)
        memory_layout.setContentsMargins(10, 10, 10, 10)
        memory_layout.setSpacing(10)

        toolbar = QHBoxLayout()
        self.memory_source_label = QLabel("")
        self.memory_source_label.setFont(FONT_UI)
        self.memory_source_label.setStyleSheet("color: #555; border: none;")
        toolbar.addWidget(self.memory_source_label, 1)
        run_button = QPushButton("Analyze memory dump (Volatility 3)…")
        run_button.setStyleSheet(SMALL_BUTTON)
        run_button.clicked.connect(self.start_memory_analysis)
        toolbar.addWidget(run_button)
        self.memory_cancel_button = QPushButton("Cancel")
        self.memory_cancel_button.setStyleSheet(SMALL_BUTTON)
        self.memory_cancel_button.setVisible(False)
        self.memory_cancel_button.clicked.connect(self.cancel_memory_analysis)
        toolbar.addWidget(self.memory_cancel_button)
        vt_button = QPushButton("Check IPs on VirusTotal")
        vt_button.setStyleSheet(SMALL_BUTTON)
        vt_button.clicked.connect(self.check_ips_with_virustotal)
        toolbar.addWidget(vt_button)
        refresh_button = QPushButton("Reload")
        refresh_button.setStyleSheet(SMALL_BUTTON)
        refresh_button.clicked.connect(lambda: self._on_memory_tab_click())
        toolbar.addWidget(refresh_button)
        memory_layout.addLayout(toolbar)

        tabs_layout = QHBoxLayout()
        self.memory_tabs = {}
        for name in ("Core Analysis Files", "Volatility", "Memory Dumps"):
            button = QPushButton(name)
            button.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            button.setCheckable(True)
            button.clicked.connect(self._on_memory_tab_click)
            tabs_layout.addWidget(button)
            self.memory_tabs[name] = button
        memory_layout.addLayout(tabs_layout)

        content_layout = QHBoxLayout()
        self.memory_left_panel = QFrame()
        self.memory_left_panel.setObjectName("memoryLeftPanel")
        self.memory_left_panel.setFixedWidth(250)
        self.memory_left_panel.setStyleSheet("QFrame#memoryLeftPanel { background-color: #f0f0f0; border-radius: 10px; }")
        left_panel_layout = QVBoxLayout(self.memory_left_panel)
        left_panel_layout.setContentsMargins(15, 15, 15, 15)
        left_panel_layout.setSpacing(10)
        left_panel_layout.setAlignment(Qt.AlignTop)

        self.memory_right_panel = QFrame()
        self.memory_right_panel.setObjectName("memoryRightPanel")
        self.memory_right_panel.setStyleSheet("QFrame#memoryRightPanel { background-color: white; border: 1px solid #ccc; border-radius: 10px; }")
        right_panel_layout = QVBoxLayout(self.memory_right_panel)
        self.memory_results_view = QTextEdit()
        self.memory_results_view.setReadOnly(True)
        self.memory_results_view.setFont(QFont("Consolas", 10))
        self.memory_results_view.setStyleSheet("border: none; background-color: white; padding: 5px;")
        right_panel_layout.addWidget(self.memory_results_view)

        content_layout.addWidget(self.memory_left_panel)
        content_layout.addWidget(self.memory_right_panel, 1)
        memory_layout.addLayout(content_layout, 1)

        self.memory_sub_option_panels = {
            "Core Analysis Files": self._create_sub_option_panel(["virustotal", "filtered netscan with IPcheck", "virustotal IP"]),
            "Volatility": self._create_sub_option_panel(["malfind", "pslist", "netscan", "userassist", "wininfo", "cmdline"]),
            "Memory Dumps": self._create_sub_option_panel(["dumped memory", "dumped memory malicious ips"]),
        }
        for panel in self.memory_sub_option_panels.values():
            left_panel_layout.addWidget(panel)
        self.memory_tabs["Core Analysis Files"].setChecked(True)
        self._on_memory_tab_click()

    def _create_sub_option_panel(self, button_names):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        buttons = []
        for name in button_names:
            button = QPushButton(name)
            button.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            button.setCheckable(True)
            button.setStyleSheet(f"""
                QPushButton {{ background-color: {COLOR_DARK}; color: white; border: none; border-radius: 8px; padding: 12px; }}
                QPushButton:hover {{ background-color: #555; }}
                QPushButton:checked {{ background-color: {COLOR_ORANGE}; }}
            """)
            button.clicked.connect(self._on_memory_sub_option_click)
            layout.addWidget(button)
            buttons.append(button)
        panel.setProperty("buttons", buttons)
        return panel

    def _update_memory_source_label(self):
        if self.memory_dir == SAMPLE_MEMORY_ANALYSIS_DIR:
            text = f"Showing bundled sample data ({self.memory_dir}). Analyze a memory dump to populate the case."
        elif self.memory_dir:
            text = f"Source: {self.memory_dir}"
        else:
            text = "No memory analysis data. Analyze a memory dump to get started."
        self.memory_source_label.setText(text)

    def _on_memory_tab_click(self):
        sender = self.sender()
        if isinstance(sender, QPushButton) and sender in self.memory_tabs.values():
            self.active_memory_tab = next(name for name, button in self.memory_tabs.items() if button is sender)
        active = getattr(self, "active_memory_tab", "Core Analysis Files")
        for name, button in self.memory_tabs.items():
            is_active = name == active
            button.setChecked(is_active)
            self.memory_sub_option_panels[name].setVisible(is_active)
            button.setStyleSheet(f"background-color: {COLOR_ORANGE if is_active else COLOR_DARK}; color: white; border-radius: 8px; padding: 10px;")
        buttons = self.memory_sub_option_panels[active].property("buttons")
        selected = next((b for b in buttons if b.isChecked()), buttons[0])
        self._show_memory_option(selected)

    def _on_memory_sub_option_click(self):
        self._show_memory_option(self.sender())

    def _show_memory_option(self, clicked_button):
        for panel in self.memory_sub_option_panels.values():
            for button in panel.property("buttons"):
                button.setChecked(button is clicked_button)
        self.memory_results_view.setHtml(self._render_memory_option(clicked_button.text()))

    def _render_memory_option(self, option_name: str) -> str:
        folder = self.memory_dir
        if not folder:
            return "<h3>No memory analysis data</h3><p>Use <b>Analyze memory dump</b> to run Volatility on a .mem / .raw image.</p>"
        if option_name == "virustotal":
            return self._render_virustotal(folder)
        if option_name == "virustotal IP":
            return self._render_virustotal_ip(folder)
        if option_name == "filtered netscan with IPcheck":
            return self._render_filtered_netscan(folder)
        if option_name == "malfind":
            return self._render_malfind(folder)
        if option_name == "dumped memory":
            return self._render_dumped_memory(folder)
        if option_name == "dumped memory malicious ips":
            return self._render_dumped_ips(folder)
        titles = {"pslist": "Pslist: Running Processes", "netscan": "Netscan: Network Connections",
                  "userassist": "UserAssist: Program Execution", "wininfo": "Windows System Information",
                  "cmdline": "Command Lines"}
        rows = load_json(folder, option_name)
        if option_name == "userassist" and not rows:
            rows = load_json(folder, "filtered_userassist")
        if isinstance(rows, dict):
            rows = [rows]
        return render_table_html(titles.get(option_name, option_name), rows or [])

    def _render_virustotal(self, folder):
        results = load_json(folder, "virustotal_results")
        if isinstance(results, dict):
            results = [results]
        if not results:
            return ("<h3>VirusTotal file reputation</h3><p style='color:#777'>No results. Set <code>VIRUSTOTAL_API_KEY</code> "
                    "in <code>.env</code> and run the memory analysis to look up dumped files.</p>")
        cards = ""
        for result in results:
            detected, total = result.get("virustotal_detected", 0), result.get("virustotal_total", 0)
            status = result.get("malware_status", "Unknown")
            color = "#d9534f" if detected else ("#28a745" if status == "Clean" else "#888")
            engines = result.get("detections") or {}
            engine_rows = "".join(f"<tr><td style='padding:4px;border:1px solid #ddd'><b>{esc(e)}</b></td>"
                                  f"<td style='padding:4px;border:1px solid #ddd'>{esc(v)}</td></tr>" for e, v in list(engines.items())[:25])
            cards += f"""
            <div style='border:1px solid #ddd;border-radius:6px;padding:12px;margin-bottom:14px'>
              <b>{esc(result.get('filename'))}</b><br/>
              <span style='font-family:Consolas'>SHA256: {esc(result.get('sha256'))}</span><br/>
              <span style='font-family:Consolas'>MD5: {esc(result.get('md5'))}</span> &nbsp; Size: {esc(human_size(result.get('file_size')))}<br/>
              Detections: <b>{detected} / {total}</b> &nbsp; Status: <span style='color:{color};font-weight:bold'>{esc(status)}</span>
              &nbsp; Scan date: {esc(result.get('virustotal_scan_date', 'N/A'))}
              {('<br/>Threat label: <b>' + esc(result.get('popular_threat_label')) + '</b>') if result.get('popular_threat_label') else ''}
              {('<table style="border-collapse:collapse;margin-top:8px;font-size:9pt">' + engine_rows + '</table>') if engine_rows else ''}
            </div>"""
        return f"<div style='font-family:Segoe UI,sans-serif;font-size:10pt'><h3>VirusTotal file reputation ({len(results)} file(s))</h3>{cards}</div>"

    def _render_virustotal_ip(self, folder):
        results = load_json(folder, "virustotal_ip_results") or []
        if results:
            return render_table_html("VirusTotal IP reputation", results,
                                     ["ip", "status", "malicious", "suspicious", "harmless", "country", "as_owner", "reputation"])
        public = self._public_ips(folder)
        note = ("No VirusTotal IP look-ups stored. Set <code>VIRUSTOTAL_API_KEY</code> in <code>.env</code> and re-run the analysis, "
                "or press <b>Check now</b>." if public else "No public IP addresses in netscan output.")
        rows = [{"ip": ip, "processes": ", ".join(sorted(owners))} for ip, owners in public.items()]
        return render_table_html("Public IP addresses seen in netscan", rows, ["ip", "processes"], note=note)

    def check_ips_with_virustotal(self):
        """Look up every public IP of the current netscan output on VirusTotal."""
        if not self.memory_dir:
            QMessageBox.warning(self, "No data", "No memory analysis data loaded.")
            return
        client = VirusTotalClient()
        if not client.enabled:
            QMessageBox.warning(self, "VirusTotal key missing", "Set VIRUSTOTAL_API_KEY in the .env file first.")
            return
        ips = sorted(self._public_ips(self.memory_dir))
        if not ips:
            QMessageBox.information(self, "Nothing to check", "No public IP addresses in the netscan output.")
            return
        if self.memory_worker and self.memory_worker.isRunning():
            QMessageBox.information(self, "In Progress", "A memory analysis is already running.")
            return
        folder = self.memory_dir
        self.memory_log_lines = []

        def lookup(progress):
            results = []
            for ip in ips:
                progress(f"VirusTotal: {ip} ... (free API: 4 requests/minute)")
                results.append(client.ip_report(ip))
            with open(os.path.join(folder, "virustotal_ip_results.json"), "w", encoding="utf-8") as handle:
                json.dump(results, handle, indent=2)
            return results

        self.memory_worker = WorkerThread(lookup, pass_progress=True)
        self.memory_worker.progress.connect(self._append_memory_log)
        self.memory_worker.done.connect(lambda _r: self._on_memory_tab_click())
        self.memory_worker.failed.connect(lambda m: QMessageBox.critical(self, "VirusTotal failed", m))
        self.memory_worker.start()

    def _public_ips(self, folder) -> dict:
        public = {}
        for conn in load_json(folder, "netscan") or []:
            ip = str(conn.get("ForeignAddr", ""))
            if classify_ip(ip) == "public":
                public.setdefault(ip, set()).add(f"{conn.get('Owner', '-')} ({conn.get('PID', '-')})")
        if not public:
            for group in (load_json(folder, "filtered_netscan") or {}).get("GroupedConnections", []):
                for conn in group.get("Connections", []):
                    ip = str(conn.get("ForeignAddr", ""))
                    if classify_ip(ip) == "public":
                        public.setdefault(ip, set()).add(f"{group.get('Owner', '-')} ({conn.get('pid', '-')})")
        return public

    def _render_filtered_netscan(self, folder):
        data = load_json(folder, "filtered_netscan") or {}
        groups = data.get("GroupedConnections", [])
        if not groups:
            return "<h3>Filtered netscan</h3><p style='color:#777'>No data available.</p>"
        suspicious_pids = set()
        for region in load_json(folder, "malfind") or []:
            suspicious_pids.add(str(region.get("PID")))
        sections = ""
        for group in groups:
            owner, pid = group.get("Owner", "-"), str(group.get("PID", group.get("Connections", [{}])[0].get("pid", "-")))
            rows = ""
            public_count = 0
            for conn in group.get("Connections", []):
                kind = conn.get("ForeignClass") or classify_ip(conn.get("ForeignAddr"))
                if kind == "public":
                    public_count += 1
                color = {"public": "#d9534f", "private": "#0275d8", "local": "#888"}.get(kind, "#333")
                rows += (f"<tr><td style='padding:4px;border:1px solid #eee'>{esc(conn.get('protocol'))}</td>"
                         f"<td style='padding:4px;border:1px solid #eee;font-family:Consolas'>{esc(conn.get('LocalAddr'))}:{esc(conn.get('LocalPort'))}</td>"
                         f"<td style='padding:4px;border:1px solid #eee;font-family:Consolas;color:{color};font-weight:bold'>{esc(conn.get('ForeignAddr'))}:{esc(conn.get('ForeignPort'))}</td>"
                         f"<td style='padding:4px;border:1px solid #eee;color:{color}'>{esc(kind)}</td>"
                         f"<td style='padding:4px;border:1px solid #eee'>{esc(conn.get('State'))}</td></tr>")
            flag = " <span style='color:#d9534f'>&#9888; flagged by malfind</span>" if pid in suspicious_pids else ""
            sections += f"""
            <div style='border:1px solid #ddd;border-radius:6px;padding:10px;margin-bottom:12px'>
              <b>{esc(owner)}</b> (PID {esc(pid)}) — {len(group.get('Connections', []))} socket(s), {public_count} public{flag}
              <table width='100%' style='border-collapse:collapse;font-size:9pt;margin-top:6px'>
                <tr style='background:#343a40;color:white'><th style='padding:5px'>Proto</th><th style='padding:5px'>Local</th>
                <th style='padding:5px'>Foreign</th><th style='padding:5px'>Class</th><th style='padding:5px'>State</th></tr>{rows}
              </table></div>"""
        return (f"<div style='font-family:Segoe UI,sans-serif;font-size:10pt'><h3>Netscan grouped by process with IP classification</h3>"
                f"<p style='color:#555'>Public addresses are highlighted in red; processes flagged by malfind are marked.</p>{sections}</div>")

    def _render_malfind(self, folder):
        regions = load_json(folder, "malfind") or []
        if not regions:
            return "<h3>Malfind</h3><p style='color:#777'>No injected code regions reported.</p>"
        cards = ""
        for region in regions:
            protection = str(region.get("Protection", ""))
            color = "#d9534f" if "EXECUTE" in protection else "#5bc0de"
            hexdump = "<br/>".join(esc(line) for line in region.get("Hexdump", []) or [])
            disasm = "<br/>".join(esc(line) for line in region.get("Disasm", []) or [])
            cards += f"""
            <div style='border:1px solid #ddd;border-radius:5px;padding:12px;margin-bottom:16px'>
              <h4 style='margin:0 0 8px 0;background:#f0f0f0;padding:8px;border-radius:4px'>Process: <b>{esc(region.get('Process'))}</b> (PID {esc(region.get('PID'))})</h4>
              <table width='100%' style='font-size:9pt'>
                <tr><td width='120'><b>Start VPN</b></td><td>{esc(region.get('Start VPN'))}</td><td width='120'><b>End VPN</b></td><td>{esc(region.get('End VPN'))}</td></tr>
                <tr><td><b>Tag</b></td><td>{esc(region.get('Tag'))}</td><td><b>Protection</b></td><td style='color:{color};font-weight:bold'>{esc(protection)}</td></tr>
                <tr><td><b>CommitCharge</b></td><td>{esc(region.get('CommitCharge'))}</td><td><b>Notes</b></td><td>{esc(region.get('Notes'))}</td></tr>
              </table>
              <table width='100%' style='font-size:8pt;margin-top:8px;table-layout:fixed'><tr><th align='left'>Hex dump</th><th align='left'>Disassembly</th></tr>
                <tr><td style='vertical-align:top;background:#fafafa;border:1px solid #eee;padding:6px;font-family:Consolas'>{hexdump}</td>
                    <td style='vertical-align:top;background:#fafafa;border:1px solid #eee;padding:6px;font-family:Consolas'>{disasm}</td></tr></table>
            </div>"""
        return f"<div style='font-family:Segoe UI,sans-serif;font-size:10pt'><h3>Malfind: hidden or injected code ({len(regions)} region(s))</h3>{cards}</div>"

    def _render_dumped_memory(self, folder):
        features = load_json(folder, "dumped_memory_features") or collect_dumped_file_features(os.path.join(folder, "dumped_memory"))
        rows = [{"PID": f.get("pid") or self._pid_from_path(f.get("path", "")), "File": f.get("file_name"),
                 "Size": human_size(f.get("size")), "SHA256": f.get("sha256"), "MD5": f.get("md5", "")} for f in features]
        return render_table_html("Files dumped from suspicious processes", rows, ["PID", "File", "Size", "SHA256", "MD5"])

    @staticmethod
    def _pid_from_path(path):
        for part in str(path).replace("/", "\\").split("\\"):
            if part.upper().startswith("PID_"):
                return part[4:]
        return ""

    def _render_dumped_ips(self, folder):
        hits = scan_dumped_files_for_ips(os.path.join(folder, "dumped_memory"))
        vt = {item.get("ip"): item for item in load_json(folder, "virustotal_ip_results") or []}
        for hit in hits:
            info = vt.get(hit["ip"])
            hit["VT malicious"] = info.get("malicious") if info else "n/a"
        note = "Public IPv4 strings carved from the dumped process memory. Cross-check them with the netscan output and VirusTotal."
        return render_table_html("Public IP strings found in dumped memory", hits, ["pid", "file", "ip", "VT malicious"], note=note)

    def start_memory_analysis(self):
        if not self._require_case("memory analysis"):
            return
        if self.memory_worker and self.memory_worker.isRunning():
            QMessageBox.information(self, "In Progress", "A memory analysis is already running.")
            return
        start_dir = os.path.join(self.selected_case_path, CASE_EVIDENCE_SUBDIR)
        dump_path, _ = QFileDialog.getOpenFileName(self, "Select memory image", start_dir if os.path.isdir(start_dir) else "",
                                                   "Memory images (*.mem *.raw *.dmp *.vmem *.bin *.img *.lime);;All files (*)")
        if not dump_path:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Memory analysis options")
        layout = QVBoxLayout(dialog)
        dump_check = QCheckBox("Dump files of suspicious processes (windows.dumpfiles) and hash them")
        dump_check.setChecked(True)
        vt_check = QCheckBox("Query VirusTotal for dumped files and public IPs (needs VIRUSTOTAL_API_KEY)")
        vt_check.setChecked(bool(VirusTotalClient().enabled))
        vt_check.setEnabled(bool(VirusTotalClient().enabled))
        info = QLabel("Volatility downloads Windows symbol tables on first use; this needs internet access and can take several minutes.")
        info.setWordWrap(True)
        for widget in (QLabel(f"Image: {dump_path}"), dump_check, vt_check, info):
            layout.addWidget(widget)
        buttons = QHBoxLayout()
        ok = QPushButton("Start")
        ok.setStyleSheet(SMALL_BUTTON)
        ok.clicked.connect(dialog.accept)
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(SMALL_BUTTON)
        cancel.clicked.connect(dialog.reject)
        buttons.addStretch()
        buttons.addWidget(ok)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)
        if dialog.exec_() != QDialog.Accepted:
            return

        output_dir = self._case_dir(CASE_MEMORY_SUBDIR)
        self.memory_results_view.setHtml(f"<h3>Analyzing {esc(dump_path)}</h3><pre id='log'></pre>")
        self.memory_log_lines = []
        self.memory_cancel_button.setVisible(True)

        analyzer_holder = {}

        def run(progress):
            analyzer = MemoryAnalyzer(dump_path, output_dir, progress=progress,
                                      cancel_check=lambda: self.memory_worker.cancelled if self.memory_worker else False)
            analyzer_holder["analyzer"] = analyzer
            return analyzer.run_all(dump_files=dump_check.isChecked(), use_virustotal=vt_check.isChecked())

        self.memory_worker = WorkerThread(run, pass_progress=True)
        self.memory_worker.progress.connect(self._append_memory_log)
        self.memory_worker.done.connect(lambda outputs: self._on_memory_analysis_done(outputs, dump_path))
        self.memory_worker.failed.connect(self._on_memory_analysis_failed)
        self.memory_worker.start()

    def cancel_memory_analysis(self):
        if self.memory_worker:
            self.memory_worker.cancelled = True
            self._append_memory_log("Cancelling after the current plugin finishes ...")

    def _append_memory_log(self, message):
        self.memory_log_lines.append(message)
        self.memory_results_view.setHtml("<h3>Memory analysis in progress</h3><pre style='font-family:Consolas;font-size:9pt'>"
                                         + "\n".join(esc(l) for l in self.memory_log_lines[-200:]) + "</pre>")
        self.memory_results_view.verticalScrollBar().setValue(self.memory_results_view.verticalScrollBar().maximum())

    def _on_memory_analysis_done(self, outputs, dump_path):
        self.memory_cancel_button.setVisible(False)
        self.memory_dir = memory_analysis_dir(self.selected_case_path)
        self._update_memory_source_label()
        record_evidence(self.selected_case_path, [dump_path], "memory_image_analysis",
                        source="Volatility 3", notes=f"Outputs: {', '.join(sorted(outputs))}", compute_hashes=False)
        QMessageBox.information(self, "Memory analysis finished", f"Results were written to\n{self._case_dir(CASE_MEMORY_SUBDIR)}")
        self._on_memory_tab_click()

    def _on_memory_analysis_failed(self, message):
        self.memory_cancel_button.setVisible(False)
        self._append_memory_log(f"FAILED: {message}")
        QMessageBox.critical(self, "Memory analysis failed", message)

    # =============================================================== WEB
    def _build_web_view(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        toolbar = QHBoxLayout()
        label = QLabel("Source:")
        label.setFont(FONT_UI_BOLD)
        toolbar.addWidget(label)
        self.web_source_combo = QComboBox()
        self.web_source_combo.setFont(FONT_UI)
        self.web_source_combo.addItems(["Remote host (not connected)", "This machine (current user)", "Browser profile folder…", "Windows user folder…"])
        toolbar.addWidget(self.web_source_combo, 1)
        extract = QPushButton("Extract browser artifacts")
        extract.setStyleSheet(SMALL_BUTTON)
        extract.clicked.connect(self.start_web_extraction)
        toolbar.addWidget(extract)
        self.web_open_button = QPushButton("Open report in browser")
        self.web_open_button.setStyleSheet(SMALL_BUTTON)
        self.web_open_button.setEnabled(False)
        self.web_open_button.clicked.connect(lambda: os.startfile(self.web_report_path) if getattr(self, "web_report_path", None) else None)
        toolbar.addWidget(self.web_open_button)
        layout.addLayout(toolbar)
        self.web_status = QLabel("Choose a source and press Extract. Reports are stored inside the case folder.")
        self.web_status.setFont(FONT_UI)
        self.web_status.setStyleSheet("color:#555; border:none;")
        layout.addWidget(self.web_status)
        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view, 1)
        return container

    def start_web_extraction(self):
        if not self._require_case("web artifact extraction") or self._busy():
            return
        choice = self.web_source_combo.currentIndex()
        output_dir = os.path.join(self._case_dir(CASE_WEB_SUBDIR), datetime.now().strftime("%Y%m%d_%H%M%S"))
        if choice == 0:
            if not self.connection_params:
                QMessageBox.warning(self, "Not connected", "Connect to a remote host from the Resource tab first, or choose a local source.")
                return
            params = self.connection_params
            job = WorkerThread(extract_all_web_artifacts, params.get("remote_ip"), params.get("remote_domain"),
                               params.get("remote_user"), params.get("remote_password"), output_dir=output_dir)
            source = f"remote host {params.get('remote_ip')}"
        elif choice == 1:
            job = WorkerThread(extract_local_user, None, output_dir)
            source = "this machine"
        elif choice == 2:
            folder = QFileDialog.getExistingDirectory(self, "Select browser profile folder (e.g. ...\\User Data\\Default)")
            if not folder:
                return
            job = WorkerThread(extract_local_profile, folder, output_dir)
            source = folder
        else:
            folder = QFileDialog.getExistingDirectory(self, "Select a Windows user folder (e.g. C:\\Users\\john or an acquired copy)")
            if not folder:
                return
            job = WorkerThread(extract_local_user, folder, output_dir)
            source = folder
        self.web_status.setText(f"Extracting browser artifacts from {source} ...")
        self.worker = job
        job.done.connect(lambda result: self.on_web_extraction_finished(result, source))
        job.failed.connect(lambda message: self.on_web_extraction_finished({"status": "error", "message": message}, source))
        job.start()

    def on_web_extraction_finished(self, result, source=""):
        if result.get("status") == "success":
            self.web_report_path = result["report_path"]
            self.web_open_button.setEnabled(True)
            self.web_view.setUrl(QUrl.fromLocalFile(result["report_path"]))
            counts = "; ".join(f"{browser}: " + ", ".join(f"{k} {v}" for k, v in c.items()) for browser, c in result.get("counts", {}).items())
            self.web_status.setText(f"Report saved to {result['output_dir']}  |  {counts}")
            record_evidence(self.selected_case_path, [result["report_path"]], "web_artifacts", source=source, compute_hashes=False)
        else:
            self.web_status.setText(f"Error: {result.get('message')}")
            QMessageBox.critical(self, "Extraction Failed", str(result.get("message")))

    # ============================================================== SRUM
    def _build_srum_view(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        form = QGroupBox("SRUM database")
        form.setFont(FONT_UI_BOLD)
        form.setStyleSheet("QGroupBox { border: 1px solid #ccc; border-radius: 6px; margin-top: 10px; padding-top: 6px; } "
                           "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }")
        grid = QGridLayout(form)
        grid.setContentsMargins(12, 12, 12, 12)
        self.srum_db_input = QLineEdit()
        self.srum_db_input.setPlaceholderText(r"Path to SRUDB.dat (acquired copy of C:\Windows\System32\sru\SRUDB.dat)")
        self.srum_db_input.setStyleSheet(INPUT_STYLE)
        self.srum_hive_input = QLineEdit()
        self.srum_hive_input.setPlaceholderText("Optional: SOFTWARE hive from the same machine (resolves user names and Wi-Fi SSIDs)")
        self.srum_hive_input.setStyleSheet(INPUT_STYLE)
        for row, (label, field) in enumerate((("SRUDB.dat:", self.srum_db_input), ("SOFTWARE hive:", self.srum_hive_input))):
            lab = QLabel(label)
            lab.setFont(FONT_UI)
            grid.addWidget(lab, row, 0)
            grid.addWidget(field, row, 1)
            browse = QPushButton("Browse…")
            browse.setStyleSheet(SMALL_BUTTON)
            browse.clicked.connect(lambda _c, f=field: self._browse_into(f))
            grid.addWidget(browse, row, 2)
        buttons = QHBoxLayout()
        acquire = QPushButton("Acquire from this machine (RawCopy, admin)")
        acquire.setStyleSheet(SMALL_BUTTON)
        acquire.clicked.connect(self.acquire_local_srum)
        analyze = QPushButton("Analyze SRUM")
        analyze.setStyleSheet(SMALL_BUTTON)
        analyze.clicked.connect(self.start_srum_analysis)
        buttons.addWidget(acquire)
        buttons.addWidget(analyze)
        buttons.addStretch()
        grid.addLayout(buttons, 2, 0, 1, 3)
        self.srum_output_label = QLabel("Select a case to store SRUM results.")
        self.srum_output_label.setFont(FONT_UI)
        self.srum_output_label.setStyleSheet("color:#555; border:none;")
        grid.addWidget(self.srum_output_label, 3, 0, 1, 3)
        layout.addWidget(form)

        self.srum_tab_widget = QTabWidget()
        self.srum_tab_widget.setStyleSheet("""
            QTabBar::tab { background: #f0f0f0; border: 1px solid #ccc; border-bottom-color: #c2c7d5; border-top-left-radius: 4px;
                           border-top-right-radius: 4px; min-width: 8ex; padding: 8px; font-family: 'Segoe UI'; font-weight: bold; }
            QTabBar::tab:selected { background: white; border-color: #9B9B9B; border-bottom-color: white; }
            QTabWidget::pane { border: 1px solid #ccc; border-top: none; }
        """)
        layout.addWidget(self.srum_tab_widget, 1)
        return container

    def _browse_into(self, field: QLineEdit):
        start = os.path.dirname(field.text()) if field.text() else (self.selected_case_path or "")
        path, _ = QFileDialog.getOpenFileName(self, "Select file", start, "All files (*)")
        if path:
            field.setText(path)

    def acquire_local_srum(self):
        if not self._require_case("SRUM acquisition") or self._busy():
            return
        output_dir = self._case_dir(CASE_SRUM_SUBDIR)
        self.srum_output_label.setText("Copying SRUDB.dat and SOFTWARE with RawCopy (requires Administrator) ...")

        def acquire():
            results = {}
            for name in ("SRUDB.dat", "SOFTWARE"):
                results[name] = rawcopy_file(SYSTEM_HIVES[name], output_dir)
            return results

        self.worker = WorkerThread(acquire)
        self.worker.done.connect(self._on_local_srum_acquired)
        self.worker.failed.connect(lambda m: QMessageBox.critical(self, "Acquisition failed", m))
        self.worker.start()

    def _on_local_srum_acquired(self, results):
        messages, acquired = [], []
        for name, (ok, detail) in results.items():
            messages.append(f"{'✓' if ok else '✗'} {name}: {detail}")
            if ok:
                acquired.append(detail)
                if name == "SRUDB.dat":
                    self.srum_db_input.setText(detail)
                else:
                    self.srum_hive_input.setText(detail)
        self.srum_output_label.setText(" | ".join(messages))
        if acquired:
            record_evidence(self.selected_case_path, acquired, "srum_acquisition", source="local machine (RawCopy)")
        else:
            QMessageBox.warning(self, "Acquisition failed", "\n".join(messages) + "\n\nRun Anubis as Administrator to copy locked system files.")

    def start_srum_analysis(self):
        srum_path = self.srum_db_input.text().strip()
        hive_path = self.srum_hive_input.text().strip() or None
        if not srum_path or not os.path.isfile(srum_path):
            QMessageBox.warning(self, "File not found", "Select a valid SRUDB.dat file first.")
            return
        if hive_path and not os.path.isfile(hive_path):
            QMessageBox.warning(self, "File not found", f"SOFTWARE hive not found:\n{hive_path}")
            return
        if self._busy():
            return
        self.srum_tab_widget.clear()
        self.srum_output_label.setText("Parsing SRUM database ... this can take a minute for large databases.")
        self.worker = WorkerThread(analyze_srum, srum_path, hive_path, pass_progress=True)
        self.worker.progress.connect(self.srum_output_label.setText)
        self.worker.done.connect(lambda data: self.on_srum_analysis_finished({"status": "success", "data": data, "path": srum_path}))
        self.worker.failed.connect(lambda message: self.on_srum_analysis_finished({"status": "error", "message": message}))
        self.worker.start()

    def on_srum_analysis_finished(self, result):
        if result["status"] != "success":
            self.srum_output_label.setText(f"SRUM analysis error: {result['message']}")
            QMessageBox.critical(self, "SRUM Analysis Failed", result["message"])
            return
        data = result["data"]
        self.display_srum_data(data)
        total = sum(len(rows) - 1 for rows in data.values())
        message = f"{len(data)} table(s), {total} record(s) parsed from {result['path']}"
        if self.selected_case_path:
            output_dir = self._case_dir(CASE_SRUM_SUBDIR)
            written = []
            for name, rows in data.items():
                safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in name).strip().replace(" ", "_")
                path = os.path.join(output_dir, f"SRUM_{safe}.csv")
                with open(path, "w", newline="", encoding="utf-8") as handle:
                    csv.writer(handle).writerows(rows)
                written.append(path)
            record_evidence(self.selected_case_path, written, "srum_analysis", source=result["path"], compute_hashes=False)
            message += f" — CSV exports saved to {output_dir}"
        self.srum_output_label.setText(message)

    def display_srum_data(self, all_tables_data):
        self.srum_tab_widget.clear()
        if not all_tables_data:
            self.srum_output_label.setText("No data found in SRUM database.")
            return
        for tname, table_data in all_tables_data.items():
            if not table_data or len(table_data) < 2:
                continue
            tab = QWidget()
            layout = QVBoxLayout(tab)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(8)

            header_layout = QHBoxLayout()
            info_label = QLabel(f"<b>Table:</b> {tname} &nbsp; <b>Records:</b> {len(table_data) - 1}")
            info_label.setFont(FONT_UI)
            header_layout.addWidget(info_label)
            search_box = QLineEdit()
            search_box.setPlaceholderText("Type to filter table data...")
            search_box.setStyleSheet(INPUT_STYLE)
            header_layout.addWidget(search_box, 1)
            export_btn = QPushButton("Export to CSV")
            export_btn.setStyleSheet(SMALL_BUTTON)
            export_btn.clicked.connect(lambda _checked, data=table_data, name=tname: self.export_srum_csv(data, name))
            header_layout.addWidget(export_btn)
            layout.addLayout(header_layout)

            table = QTableWidget()
            table.setSortingEnabled(False)
            table.setAlternatingRowColors(True)
            table.setSelectionBehavior(QTableWidget.SelectRows)
            table.setEditTriggers(QTableWidget.NoEditTriggers)
            table.verticalHeader().setVisible(False)
            table.setStyleSheet(TABLE_STYLE)
            headings = table_data[0]
            table.setColumnCount(len(headings))
            table.setHorizontalHeaderLabels([str(h) for h in headings])
            table.setRowCount(len(table_data) - 1)
            for row_idx, row_data in enumerate(table_data[1:]):
                for col_idx, cell_data in enumerate(row_data):
                    text = str(cell_data)
                    item = QTableWidgetItem(text)
                    if len(text) == 19 and text[4] == "-" and text[13] == ":":
                        item.setBackground(QColor(255, 248, 220))
                    elif "\\" in text or "/" in text:
                        item.setFont(QFont("Consolas", 9))
                        item.setBackground(QColor(245, 245, 245))
                    table.setItem(row_idx, col_idx, item)
            table.resizeColumnsToContents()
            table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
            for col in range(table.columnCount()):
                table.setColumnWidth(col, max(100, min(table.columnWidth(col), 320)))
            table.setSortingEnabled(True)
            search_box.textChanged.connect(lambda text, t=table: self.filter_srum_table(t, text))
            layout.addWidget(table, 1)

            status_label = QLabel(f"Showing {len(table_data) - 1} records")
            status_label.setObjectName("srumStatus")
            status_label.setFont(FONT_UI)
            layout.addWidget(status_label)
            self.srum_tab_widget.addTab(tab, tname)

    def filter_srum_table(self, table, search_text):
        search_text = search_text.lower()
        for row in range(table.rowCount()):
            visible = not search_text or any(
                table.item(row, col) and search_text in table.item(row, col).text().lower() for col in range(table.columnCount()))
            table.setRowHidden(row, not visible)
        visible_count = sum(1 for row in range(table.rowCount()) if not table.isRowHidden(row))
        status_label = table.parent().findChild(QLabel, "srumStatus")
        if status_label:
            status_label.setText(f"Showing {visible_count} of {table.rowCount()} records")

    def export_srum_csv(self, table_data, table_name):
        if not table_data or len(table_data) < 2:
            QMessageBox.warning(self, "Export Failed", "No data to export.")
            return
        file_path, _ = QFileDialog.getSaveFileName(self, f"Export {table_name} to CSV", f"SRUM_{table_name.replace(' ', '_')}.csv",
                                                   "CSV Files (*.csv);;All Files (*)")
        if file_path:
            try:
                with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
                    csv.writer(csvfile).writerows(table_data)
                QMessageBox.information(self, "Export Successful", f"SRUM data exported to {file_path}")
            except OSError as error:
                QMessageBox.critical(self, "Export Failed", f"Failed to export to CSV: {error}")

    # =============================================================== USB
    def _build_usb_view(self):
        container = QWidget()
        container.setStyleSheet("""
            QGroupBox { border: 1px solid #ccc; border-radius: 6px; margin-top: 10px; font-weight: bold; background-color: #f7f7f7; font-family: 'Segoe UI'; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top center; padding: 0 5px; }
        """)
        usb_layout = QVBoxLayout(container)
        usb_layout.setContentsMargins(0, 0, 0, 0)
        usb_layout.setSpacing(10)

        control_panel = QGroupBox("Controls")
        control_panel.setFont(FONT_UI)
        control_layout = QGridLayout(control_panel)
        control_layout.setContentsMargins(15, 25, 15, 15)
        control_layout.setSpacing(10)

        self.usb_source_combo = QComboBox()
        self.usb_source_combo.setFont(FONT_UI)
        self.usb_source_combo.addItems(["Live registry (this machine)", "Acquired SYSTEM hive"])
        self.usb_hive_input = QLineEdit()
        self.usb_hive_input.setPlaceholderText("Path to acquired SYSTEM hive")
        self.usb_hive_input.setStyleSheet(INPUT_STYLE)
        hive_browse = QPushButton("Browse…")
        hive_browse.setStyleSheet(SMALL_BUTTON)
        hive_browse.clicked.connect(lambda: self._browse_into(self.usb_hive_input))
        scan_button = QPushButton("Scan")
        scan_button.setStyleSheet(SMALL_BUTTON)
        scan_button.clicked.connect(self.scan_usb_devices)

        self.usb_search_box = QLineEdit()
        self.usb_search_box.setPlaceholderText("Type to filter devices...")
        self.usb_search_box.setClearButtonEnabled(True)
        self.usb_search_box.setStyleSheet(INPUT_STYLE)
        self.usb_search_box.textChanged.connect(self.apply_usb_filters)
        self.usb_time_filter = QComboBox()
        self.usb_time_filter.addItems(["All Time", "Last 7 Days", "Last 30 Days", "Last 90 Days", "Last Year"])
        self.usb_time_filter.setFont(FONT_UI)
        self.usb_time_filter.currentIndexChanged.connect(self.apply_usb_filters)
        self.usb_type_filter = QComboBox()
        self.usb_type_filter.addItems(["All devices", "Storage devices only"])
        self.usb_type_filter.setFont(FONT_UI)
        self.usb_type_filter.currentIndexChanged.connect(self.apply_usb_filters)
        self.export_button = QPushButton("Export to CSV")
        self.export_button.setStyleSheet(SMALL_BUTTON.replace(COLOR_DARK, "#17a2b8"))
        self.export_button.clicked.connect(self.export_usb_csv)
        self.forensic_button = QPushButton("Forensic Analysis")
        self.forensic_button.setStyleSheet(SMALL_BUTTON.replace(COLOR_DARK, "#dc3545"))
        self.forensic_button.clicked.connect(self.perform_forensic_analysis)

        labels = {name: QLabel(name) for name in ("Source:", "SYSTEM hive:", "Search:", "Time range:", "Type:")}
        for label in labels.values():
            label.setFont(FONT_UI)
        control_layout.addWidget(labels["Source:"], 0, 0)
        control_layout.addWidget(self.usb_source_combo, 0, 1)
        control_layout.addWidget(labels["SYSTEM hive:"], 0, 2)
        control_layout.addWidget(self.usb_hive_input, 0, 3)
        control_layout.addWidget(hive_browse, 0, 4)
        control_layout.addWidget(scan_button, 0, 5)
        control_layout.addWidget(labels["Search:"], 1, 0)
        control_layout.addWidget(self.usb_search_box, 1, 1)
        control_layout.addWidget(labels["Time range:"], 1, 2)
        control_layout.addWidget(self.usb_time_filter, 1, 3)
        control_layout.addWidget(labels["Type:"], 1, 4)
        control_layout.addWidget(self.usb_type_filter, 1, 5)
        control_layout.addWidget(self.export_button, 2, 0, 1, 2)
        control_layout.addWidget(self.forensic_button, 2, 2, 1, 2)
        control_layout.setColumnStretch(1, 1)
        control_layout.setColumnStretch(3, 1)
        usb_layout.addWidget(control_panel)

        self.usb_table_view = QTableWidget()
        self.usb_table_view.setSortingEnabled(True)
        self.usb_table_view.setAlternatingRowColors(True)
        self.usb_table_view.setSelectionBehavior(QTableWidget.SelectRows)
        self.usb_table_view.setEditTriggers(QTableWidget.NoEditTriggers)
        self.usb_table_view.verticalHeader().setVisible(False)
        self.usb_table_view.horizontalHeader().setStretchLastSection(True)
        self.usb_table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.usb_table_view.customContextMenuRequested.connect(self.show_usb_context_menu)
        self.usb_table_view.doubleClicked.connect(self.show_usb_device_details)
        self.usb_table_view.setStyleSheet(TABLE_STYLE)
        usb_layout.addWidget(self.usb_table_view, 1)

        self.usb_status_bar = QStatusBar()
        self.usb_status_bar.setSizeGripEnabled(False)
        self.usb_status_bar.setFont(FONT_UI)
        self.usb_device_count_label = QLabel()
        self.usb_device_count_label.setFont(FONT_UI)
        self.usb_status_bar.addPermanentWidget(self.usb_device_count_label)
        self.usb_progress_bar = QProgressBar()
        self.usb_progress_bar.setMaximumWidth(250)
        self.usb_progress_bar.setVisible(False)
        self.usb_status_bar.addPermanentWidget(self.usb_progress_bar)
        usb_layout.addWidget(self.usb_status_bar)
        return container

    def scan_usb_devices(self):
        if self._busy():
            return
        if self.usb_source_combo.currentIndex() == 1:
            hive = self.usb_hive_input.text().strip()
            if not os.path.isfile(hive):
                QMessageBox.warning(self, "File not found", "Select an acquired SYSTEM hive first.")
                return
            self.worker = WorkerThread(get_usb_devices_from_hive, hive)
            self.usb_source_description = hive
        else:
            self.worker = WorkerThread(get_usb_devices)
            self.usb_source_description = "live registry"
        self.usb_progress_bar.setVisible(True)
        self.usb_progress_bar.setRange(0, 0)
        self.usb_status_bar.showMessage("Scanning ...")
        self.worker.done.connect(self.on_usb_scan_finished)
        self.worker.failed.connect(lambda message: (self.on_usb_scan_finished([]), QMessageBox.critical(self, "USB scan failed", message)))
        self.worker.start()

    def on_usb_scan_finished(self, devices):
        self.usb_progress_bar.setVisible(False)
        self.usb_status_bar.clearMessage()
        self.usb_devices = devices
        if not devices:
            self.usb_device_count_label.setText("No USB devices found.")
        self.apply_usb_filters()

    def apply_usb_filters(self):
        search_term = self.usb_search_box.text().lower()
        time_filter = self.usb_time_filter.currentText()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        deltas = {"Last 7 Days": 7, "Last 30 Days": 30, "Last 90 Days": 90, "Last Year": 365}
        cutoff = now - timedelta(days=deltas[time_filter]) if time_filter in deltas else None
        storage_only = self.usb_type_filter.currentIndex() == 1
        filtered = []
        for device in self.usb_devices:
            if cutoff and (not device.get("datetime_obj") or device["datetime_obj"] < cutoff):
                continue
            if storage_only and "USBSTOR" not in device.get("Registry Path", "") and device.get("Device Type") not in ("Disk Drive", "Volume", "WPD (Portable Device)"):
                continue
            if search_term and not any(search_term in str(v).lower() for k, v in device.items() if k != "datetime_obj"):
                continue
            filtered.append(device)
        self.display_usb_data(filtered)

    USB_COLUMNS = ["Forensic ID", "Description", "Device Type", "Device Serial", "Hardware ID", "Plug-in Time", "Last Arrival", "Last Removal", "Manufacturer"]

    def display_usb_data(self, devices):
        self.displayed_usb_devices = devices
        self.usb_table_view.setSortingEnabled(False)
        self.usb_table_view.clear()
        self.usb_table_view.setColumnCount(len(self.USB_COLUMNS))
        self.usb_table_view.setHorizontalHeaderLabels(self.USB_COLUMNS)
        self.usb_table_view.setRowCount(len(devices))
        for row, device in enumerate(devices):
            for col, column in enumerate(self.USB_COLUMNS):
                item = QTableWidgetItem(str(device.get(column, "")))
                item.setFont(FONT_UI)
                if column == "Description" and "USBSTOR" in device.get("Registry Path", ""):
                    item.setBackground(QColor(255, 243, 205))
                self.usb_table_view.setItem(row, col, item)
        self.usb_table_view.resizeColumnsToContents()
        self.usb_table_view.setSortingEnabled(True)
        connected = sum(1 for d in devices if d.get("Connected") == "Yes")
        storage = sum(1 for d in devices if "USBSTOR" in d.get("Registry Path", ""))
        self.usb_device_count_label.setText(f"{len(devices)} devices shown ({storage} storage, {connected} connected) — source: {getattr(self, 'usb_source_description', 'live registry')}")

    def show_usb_device_details(self, index):
        if index.row() >= len(self.displayed_usb_devices):
            return
        device = self.displayed_usb_devices[index.row()]
        details = "".join(f"<tr><td style='padding:3px 10px 3px 0'><b>{esc(k)}</b></td><td>{esc(v)}</td></tr>"
                          for k, v in device.items() if k != "datetime_obj")
        HtmlDialog(f"Details for {device.get('Description', 'Device')}", f"<table>{details}</table>", self, size=(800, 600)).exec_()

    def export_usb_csv(self):
        if not self.displayed_usb_devices:
            QMessageBox.warning(self, "Export Failed", "No USB devices to export.")
            return
        default_dir = self._case_dir(CASE_USB_SUBDIR) if self.selected_case_path else ""
        file_path, _ = QFileDialog.getSaveFileName(self, "Export USB Devices", os.path.join(default_dir, "usb_devices.csv"), "CSV Files (*.csv);;All Files (*)")
        if not file_path:
            return
        try:
            with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                columns = [k for k in self.displayed_usb_devices[0].keys() if k != "datetime_obj"]
                writer.writerow(columns)
                for device in self.displayed_usb_devices:
                    writer.writerow([device.get(c, "") for c in columns])
            QMessageBox.information(self, "Export Successful", f"USB devices exported to {file_path}")
        except OSError as error:
            QMessageBox.critical(self, "Export Failed", f"Failed to export to CSV: {error}")

    def perform_forensic_analysis(self):
        if not self.usb_devices:
            QMessageBox.warning(self, "No data", "Scan for USB devices first.")
            return
        analysis = analyze_usb_forensics(self.usb_devices)
        report = usb_report_html(analysis, getattr(self, "usb_source_description", ""))
        if self.selected_case_path:
            output_dir = self._case_dir(CASE_USB_SUBDIR)
            path = os.path.join(output_dir, f"usb_forensic_report_{datetime.now():%Y%m%d_%H%M%S}.html")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(report)
            with open(os.path.join(output_dir, "usb_devices.json"), "w", encoding="utf-8") as handle:
                json.dump([{k: v for k, v in d.items() if k != "datetime_obj"} for d in self.usb_devices], handle, indent=2)
            record_evidence(self.selected_case_path, [path], "usb_analysis", source=getattr(self, "usb_source_description", ""), compute_hashes=False)
        HtmlDialog("USB Forensic Analysis", report, self).exec_()

    def show_usb_context_menu(self, position):
        index = self.usb_table_view.indexAt(position)
        if not index.isValid():
            return
        menu = QMenu()
        copy_cell_action = QAction("Copy Cell", self)
        copy_cell_action.triggered.connect(lambda: self.copy_cell_to_clipboard(index.row(), index.column()))
        menu.addAction(copy_cell_action)
        copy_row_action = QAction("Copy Row", self)
        copy_row_action.triggered.connect(lambda: self.copy_row_to_clipboard(index.row()))
        menu.addAction(copy_row_action)
        menu.exec_(self.usb_table_view.viewport().mapToGlobal(position))

    def copy_cell_to_clipboard(self, row, column):
        item = self.usb_table_view.item(row, column)
        if item:
            QApplication.clipboard().setText(item.text())

    def copy_row_to_clipboard(self, row):
        row_data = [self.usb_table_view.item(row, col).text() for col in range(self.usb_table_view.columnCount()) if self.usb_table_view.item(row, col)]
        QApplication.clipboard().setText("\t".join(row_data))

    # ========================================================== REGISTRY
    def create_registry_view(self):
        container = QFrame()
        container.setStyleSheet("background-color: transparent; border: none;")
        content_layout = QHBoxLayout(container)
        content_layout.addWidget(self.create_registry_options_panel(), 1)
        content_layout.addWidget(self.create_registry_progress_panel(), 1)
        return container

    def create_registry_options_panel(self):
        panel = QScrollArea()
        panel.setWidgetResizable(True)
        panel.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        panel.setStyleSheet("QScrollArea { background: white; border-radius: 12px; border: none; }")
        content_widget = QWidget()
        panel.setWidget(content_widget)
        layout = QVBoxLayout(content_widget)
        title = QLabel("Registry Analysis Options")
        title.setFont(QFont("Cascadia Mono", 16, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLOR_DARK}; margin-bottom: 15px;")
        layout.addWidget(title)
        for group in (self.create_acquire_hives_group(), self.create_analyze_hives_group(), self.create_compare_hives_group(),
                      self.create_apply_logs_group(), self.create_parse_header_group()):
            layout.addWidget(group)
        layout.addStretch()
        return panel

    def _get_group_box_style(self):
        return f"""
            QGroupBox {{ border: 2px solid {COLOR_DARK}; border-radius: 8px; margin-top: 15px; padding: 15px; }}
            QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; left: 10px; padding: 0 5px 0 5px;
                                color: {COLOR_DARK}; font-size: 14px; font-weight: bold; }}
        """

    def _create_small_browse_button(self, callback):
        browse_btn = QPushButton("Browse...")
        browse_btn.setFixedSize(100, 44)
        browse_btn.setStyleSheet(SMALL_BUTTON)
        browse_btn.clicked.connect(callback)
        return browse_btn

    def _create_action_button(self, text, callback):
        button = QPushButton(text)
        button.setStyleSheet(ACTION_BUTTON)
        button.setFixedHeight(40)
        button.clicked.connect(callback)
        return button

    def create_registry_progress_panel(self):
        panel = QWidget()
        panel.setStyleSheet("background: white; border-radius: 12px; padding: 20px;")
        layout = QVBoxLayout(panel)
        title = QLabel("Progress & Results")
        title.setFont(QFont("Cascadia Mono", 18, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLOR_DARK}; margin-bottom: 20px;")
        layout.addWidget(title)
        self.registry_progress_text = QTextEdit()
        self.registry_progress_text.setReadOnly(True)
        self.registry_progress_text.setStyleSheet(f"""
            QTextEdit {{ border: 2px solid {COLOR_DARK}; border-radius: 8px; padding: 10px; font-family: 'Cascadia Mono';
                         font-size: 12px; background-color: #f8f8f8; }}
        """)
        layout.addWidget(self.registry_progress_text)
        return panel

    def create_acquire_hives_group(self):
        group = QGroupBox("1. Acquire Hives (local machine, needs admin)")
        group.setFont(QFont("Cascadia Mono", 12, QFont.Weight.Bold))
        group.setStyleSheet(self._get_group_box_style())
        layout = QVBoxLayout(group)
        layout.setSpacing(10)
        layout.addWidget(QLabel("Username (optional, for NTUSER.DAT and UsrClass.dat):"))
        self.username_input = self.create_styled_input("e.g. john")
        layout.addWidget(self.username_input)
        layout.addWidget(QLabel("Select Hives to Acquire:"))
        self.hive_list = QListWidget()
        self.hive_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.hive_list.setMaximumHeight(150)
        self.hive_list.setStyleSheet(f"border: 1px solid {COLOR_DARK}; border-radius: 5px; padding: 5px;")
        for hive in self.registry_analyzer.get_available_hives():
            self.hive_list.addItem(QListWidgetItem(hive))
        layout.addWidget(self.hive_list)
        layout.addWidget(QLabel("Output Directory:"))
        output_layout = QHBoxLayout()
        self.acquire_output_dir_input = self.create_styled_input()
        output_layout.addWidget(self.acquire_output_dir_input)
        output_layout.addWidget(self._create_small_browse_button(lambda: self.browse_directory(self.acquire_output_dir_input)))
        layout.addLayout(output_layout)
        layout.addWidget(self._create_action_button("Acquire Hives", self.acquire_hives), alignment=Qt.AlignCenter)
        return group

    def create_analyze_hives_group(self):
        group = QGroupBox("2. Analyze Hives (regipy plugins)")
        group.setFont(QFont("Cascadia Mono", 12, QFont.Weight.Bold))
        group.setStyleSheet(self._get_group_box_style())
        layout = QVBoxLayout(group)
        layout.setSpacing(10)
        layout.addWidget(QLabel("Directory of Acquired Hives:"))
        input_layout = QHBoxLayout()
        self.analyze_input_dir = self.create_styled_input()
        input_layout.addWidget(self.analyze_input_dir)
        input_layout.addWidget(self._create_small_browse_button(lambda: self.browse_directory(self.analyze_input_dir)))
        layout.addLayout(input_layout)
        populate_btn = QPushButton("List Hives from Directory")
        populate_btn.setStyleSheet(SMALL_BUTTON)
        populate_btn.setFixedHeight(40)
        populate_btn.clicked.connect(self.populate_hives_for_analysis)
        layout.addWidget(populate_btn, alignment=Qt.AlignLeft)
        layout.addWidget(QLabel("Select Hives to Analyze:"))
        self.analyze_hive_list = QListWidget()
        self.analyze_hive_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.analyze_hive_list.setMaximumHeight(150)
        self.analyze_hive_list.setStyleSheet(f"border: 1px solid {COLOR_DARK}; border-radius: 5px; padding: 5px;")
        layout.addWidget(self.analyze_hive_list)
        layout.addWidget(self._create_action_button("Analyze Selected Hives", self.analyze_hives), alignment=Qt.AlignCenter)
        return group

    def create_compare_hives_group(self):
        group = QGroupBox("3. Compare Registry Hives")
        group.setFont(QFont("Cascadia Mono", 12, QFont.Weight.Bold))
        group.setStyleSheet(self._get_group_box_style())
        layout = QVBoxLayout(group)
        layout.setSpacing(10)
        self.hive1_input = self.create_styled_input("Path to first hive file")
        self.hive2_input = self.create_styled_input("Path to second hive file")
        self.compare_output_dir = self.create_styled_input()
        for label, field, browse in (("First Hive:", self.hive1_input, self.browse_file), ("Second Hive:", self.hive2_input, self.browse_file),
                                     ("Output Directory for Report:", self.compare_output_dir, self.browse_directory)):
            layout.addWidget(QLabel(label))
            row = QHBoxLayout()
            row.addWidget(field)
            row.addWidget(self._create_small_browse_button(lambda _c, f=field, b=browse: b(f)))
            layout.addLayout(row)
        layout.addWidget(self._create_action_button("Compare Hives", self.compare_hives), alignment=Qt.AlignCenter)
        return group

    def create_apply_logs_group(self):
        group = QGroupBox("4. Apply Transaction Logs (.LOG1/.LOG2)")
        group.setFont(QFont("Cascadia Mono", 12, QFont.Weight.Bold))
        group.setStyleSheet(self._get_group_box_style())
        layout = QVBoxLayout(group)
        layout.setSpacing(10)
        self.logs_hive_input = self.create_styled_input("Path to hive file (e.g., SYSTEM, NTUSER.DAT)")
        self.logs_output_dir = self.create_styled_input()
        for label, field, browse in (("Hive File:", self.logs_hive_input, self.browse_file),
                                     ("Output Directory for Recovered Hive:", self.logs_output_dir, self.browse_directory)):
            layout.addWidget(QLabel(label))
            row = QHBoxLayout()
            row.addWidget(field)
            row.addWidget(self._create_small_browse_button(lambda _c, f=field, b=browse: b(f)))
            layout.addLayout(row)
        layout.addWidget(self._create_action_button("Apply Transaction Logs", self.apply_transaction_logs), alignment=Qt.AlignCenter)
        return group

    def create_parse_header_group(self):
        group = QGroupBox("5. Parse Hive Header")
        group.setFont(QFont("Cascadia Mono", 12, QFont.Weight.Bold))
        group.setStyleSheet(self._get_group_box_style())
        layout = QVBoxLayout(group)
        layout.setSpacing(10)
        layout.addWidget(QLabel("Hive File:"))
        row = QHBoxLayout()
        self.header_hive_input = self.create_styled_input("Path to hive file to parse")
        row.addWidget(self.header_hive_input)
        row.addWidget(self._create_small_browse_button(lambda: self.browse_file(self.header_hive_input)))
        layout.addLayout(row)
        layout.addWidget(self._create_action_button("Parse Hive Header", self.parse_hive_header), alignment=Qt.AlignCenter)
        return group

    def populate_hives_for_analysis(self):
        input_dir = self.analyze_input_dir.text()
        if not os.path.isdir(input_dir):
            QMessageBox.warning(self, "Invalid Directory", "Please select a valid directory first.")
            return
        self.analyze_hive_list.clear()
        for item in sorted(os.listdir(input_dir)):
            path = os.path.join(input_dir, item)
            if os.path.isfile(path) and not item.lower().endswith((".log1", ".log2", ".json", ".csv", ".txt")):
                self.analyze_hive_list.addItem(QListWidgetItem(item))

    def acquire_hives(self):
        selected_items = self.hive_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Missing Information", "Please select at least one hive to acquire.")
            return
        output_dir = self.acquire_output_dir_input.text()
        if not output_dir:
            QMessageBox.warning(self, "Missing Information", "Please specify an output directory.")
            return
        self.start_registry_operation("acquire_registry_hives", {
            "output_dir": output_dir, "selected_hives": [item.text() for item in selected_items], "username": self.username_input.text().strip()})

    def analyze_hives(self):
        selected_items = self.analyze_hive_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Missing Information", "Please select at least one hive to analyze.")
            return
        base = self.selected_case_path or self.analyze_input_dir.text()
        analysis_dir = os.path.join(base, CASE_REGISTRY_SUBDIR, "analysis_results") if self.selected_case_path else os.path.join(base, "analysis_results")
        self.start_registry_operation("analyze_registry_hive", {
            "input_dir": self.analyze_input_dir.text(), "analysis_dir": analysis_dir, "selected_hives": [item.text() for item in selected_items]})

    def compare_hives(self):
        hive1, hive2, output_dir = self.hive1_input.text(), self.hive2_input.text(), self.compare_output_dir.text()
        if not all([hive1, hive2, output_dir]):
            QMessageBox.warning(self, "Missing Information", "Please provide paths for both hives and an output directory.")
            return
        self.start_registry_operation("compare_registry_hives", {"hive1_path": hive1, "hive2_path": hive2, "output_dir": output_dir})

    def apply_transaction_logs(self):
        hive_path, output_dir = self.logs_hive_input.text(), self.logs_output_dir.text()
        if not all([hive_path, output_dir]):
            QMessageBox.warning(self, "Missing Information", "Please provide the hive path and an output directory.")
            return
        self.start_registry_operation("apply_transaction_logs", {"hive_path": hive_path, "output_dir": output_dir})

    def parse_hive_header(self):
        hive_path = self.header_hive_input.text()
        if not hive_path:
            QMessageBox.warning(self, "Missing Information", "Please provide the hive path.")
            return
        self.start_registry_operation("parse_hive_header", {"hive_path": hive_path})

    def browse_directory(self, input_field):
        directory = QFileDialog.getExistingDirectory(self, "Select Directory", input_field.text() or self.selected_case_path or "")
        if directory:
            input_field.setText(directory)

    def browse_file(self, input_field):
        start = os.path.dirname(input_field.text()) if input_field.text() else (self.acquire_output_dir_input.text() or "")
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Hive File", start, "All Files (*)")
        if file_path:
            input_field.setText(file_path)

    def start_registry_operation(self, operation, kwargs):
        if self.registry_worker_thread and self.registry_worker_thread.isRunning():
            QMessageBox.warning(self, "In Progress", "Another registry operation is in progress.")
            return
        self.registry_progress_text.clear()
        self.registry_worker_thread = RegistryWorker(self.registry_analyzer, operation, **kwargs)
        self.registry_worker_thread.progress_updated.connect(self.update_registry_progress)
        self.registry_worker_thread.operation_completed.connect(self.handle_registry_operation_completed)
        self.registry_worker_thread.header_output.connect(self.display_header_output)
        self.registry_worker_thread.start()

    def update_registry_progress(self, message):
        self.registry_progress_text.append(message)

    def handle_registry_operation_completed(self, operation, success, message):
        status = "SUCCESS" if success else "FAILED"
        self.registry_progress_text.append(f"--- [{datetime.now().strftime('%H:%M:%S')}] {operation.replace('_', ' ').title()} {status} ---")
        self.registry_progress_text.append(f"{'Details' if success else 'Error'}: {message}\n")
        if success and self.selected_case_path and operation in ("acquire_registry_hives", "analyze_registry_hive", "compare_registry_hives", "apply_transaction_logs"):
            record_evidence(self.selected_case_path, [], f"registry_{operation}", notes=message, compute_hashes=False)

    def display_header_output(self, output):
        self.registry_progress_text.append("=" * 60)
        self.registry_progress_text.append(output)
        self.registry_progress_text.append("=" * 60 + "\n")
