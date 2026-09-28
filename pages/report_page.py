"""Report page: builds the forensic report from the case's memory analysis data."""
import os
from datetime import datetime

import mistune
from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QMessageBox, QProgressBar,
                             QFileDialog)
from PyQt5.QtGui import QFont, QTextDocument, QPdfWriter, QPageSize
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QMarginsF

from .base_page import BasePage, COLOR_ORANGE, COLOR_DARK, TAB_NAMES
from services.report_service import ReportService
from services.evidence_store import load_case_info, list_evidence, record_evidence
from utils.paths import memory_analysis_dir, case_subdir, CASE_REPORT_SUBDIR, PROJECT_ROOT, SAMPLE_MEMORY_ANALYSIS_DIR

REPORT_CSS = """
<style>
    body { font-family: 'Segoe UI', sans-serif; color: #23292f; }
    h1 { color: #F57C1F; border-bottom: 3px solid #23292f; padding-bottom: 6px; }
    h2 { color: #23292f; border-bottom: 1px solid #ccc; padding-bottom: 4px; margin-top: 22px; }
    table { border-collapse: collapse; width: 100%; margin: 12px 0; }
    th, td { border: 1px solid #ccc; padding: 6px 8px; text-align: left; font-size: 10pt; }
    th { background-color: #23292f; color: white; }
    tr:nth-child(even) { background-color: #f2f2f2; }
    code { background-color: #eee; padding: 1px 4px; border-radius: 3px; font-family: Consolas, monospace; }
</style>
"""
_markdown = mistune.create_markdown(plugins=["table", "strikethrough"])


class ReportGeneratorThread(QThread):
    report_generated = pyqtSignal(str, bool)
    progress_updated = pyqtSignal(str)

    def __init__(self, memory_dir, case_info, evidence, parent=None):
        super().__init__(parent)
        self.memory_dir, self.case_info, self.evidence = memory_dir, case_info, evidence

    def run(self):
        try:
            service = ReportService(self.memory_dir, self.case_info, self.evidence)
            content = service.generate_report(progress=self.progress_updated.emit)
            self.report_generated.emit(content, True)
        except Exception as error:  # noqa: BLE001
            self.report_generated.emit(f"Report generation failed: {error}", False)


class ReportPage(BasePage):
    def __init__(self):
        super().__init__()
        self.report_generator_thread = None
        self.markdown_content = ""
        self.selected_case_path = None
        self._setup_ui()
        self._load_reports()

    def set_case_path(self, case_path):
        self.selected_case_path = case_path
        self._load_reports()

    # ------------------------------------------------------------------ ui
    def _setup_ui(self):
        self.main_layout.addLayout(self._setup_tab_bar(TAB_NAMES))
        self.main_layout.addSpacing(20)
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(100, 0, 100, 40)
        content_layout.setSpacing(14)

        title = QLabel("Forensic Report")
        title.setFont(QFont("Cascadia Mono", 24, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLOR_DARK};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(title)

        button_style = """
            QPushButton {{ background-color: {bg}; color: white; border-radius: 12px; padding: 10px 18px;
                           font-family: 'Cascadia Mono'; font-size: 13px; font-weight: bold; border: none; }}
            QPushButton:hover {{ background-color: {hover}; }}
            QPushButton:disabled {{ background-color: #aaa; }}
        """
        controls = QHBoxLayout()
        controls.setSpacing(14)
        self.generate_btn = QPushButton("Generate Report")
        self.generate_btn.setStyleSheet(button_style.format(bg=COLOR_ORANGE, hover="#FF8C42"))
        self.generate_btn.clicked.connect(self._generate_report)
        self.export_md_btn = QPushButton("Export Markdown")
        self.export_md_btn.setStyleSheet(button_style.format(bg=COLOR_DARK, hover="#4a4a4a"))
        self.export_md_btn.clicked.connect(lambda: self._export_report("md"))
        self.export_html_btn = QPushButton("Export HTML")
        self.export_html_btn.setStyleSheet(button_style.format(bg=COLOR_DARK, hover="#4a4a4a"))
        self.export_html_btn.clicked.connect(lambda: self._export_report("html"))
        self.export_pdf_btn = QPushButton("Export PDF")
        self.export_pdf_btn.setStyleSheet(button_style.format(bg=COLOR_DARK, hover="#4a4a4a"))
        self.export_pdf_btn.clicked.connect(lambda: self._export_report("pdf"))
        self.refresh_btn = QPushButton("Reload")
        self.refresh_btn.setStyleSheet(button_style.format(bg="#28a745", hover="#218838"))
        self.refresh_btn.clicked.connect(self._load_reports)
        for button in (self.generate_btn, self.export_md_btn, self.export_html_btn, self.export_pdf_btn, self.refresh_btn):
            button.setFixedHeight(46)
            controls.addWidget(button)
        for button in (self.export_md_btn, self.export_html_btn, self.export_pdf_btn):
            button.setEnabled(False)
        controls.addStretch()
        content_layout.addLayout(controls)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{ border: 2px solid {COLOR_DARK}; border-radius: 8px; text-align: center; background-color: white; height: 24px; }}
            QProgressBar::chunk {{ background-color: {COLOR_ORANGE}; border-radius: 6px; }}
        """)
        content_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready to generate forensic report")
        self.status_label.setFont(QFont("Cascadia Mono", 11))
        self.status_label.setStyleSheet(f"color: {COLOR_DARK};")
        self.status_label.setWordWrap(True)
        content_layout.addWidget(self.status_label)

        self.report_content = QTextEdit()
        self.report_content.setFont(QFont("Segoe UI", 11))
        self.report_content.setStyleSheet(f"""
            QTextEdit {{ border: 2px solid {COLOR_DARK}; border-radius: 12px; background-color: white; color: {COLOR_DARK}; padding: 16px; }}
        """)
        self.report_content.setReadOnly(True)
        self.report_content.setPlaceholderText("Click 'Generate Report' to create a forensic analysis report...")
        content_layout.addWidget(self.report_content, 1)
        self.main_layout.addLayout(content_layout, 1)

    # -------------------------------------------------------------- helpers
    def _memory_dir(self):
        return memory_analysis_dir(self.selected_case_path)

    def _reports_dir(self):
        if self.selected_case_path:
            return case_subdir(self.selected_case_path, CASE_REPORT_SUBDIR)
        path = os.path.join(PROJECT_ROOT, "data", "reports")
        os.makedirs(path, exist_ok=True)
        return path

    def _latest_report_path(self):
        return os.path.join(self._reports_dir(), "forensic_report.md")

    def _display_report(self, markdown_content):
        self.markdown_content = markdown_content
        self.report_content.setHtml(REPORT_CSS + _markdown(markdown_content))
        for button in (self.export_md_btn, self.export_html_btn, self.export_pdf_btn):
            button.setEnabled(True)

    def _load_reports(self):
        memory_dir = self._memory_dir()
        source = "no memory analysis data found"
        if memory_dir == SAMPLE_MEMORY_ANALYSIS_DIR:
            source = "bundled sample data (analyze a memory dump in the case to replace it)"
        elif memory_dir:
            source = memory_dir
        case_text = f"Case: {os.path.basename(self.selected_case_path)}" if self.selected_case_path else "No case selected"
        report_path = self._latest_report_path()
        if os.path.isfile(report_path):
            try:
                with open(report_path, "r", encoding="utf-8") as handle:
                    self._display_report(handle.read())
                self.status_label.setText(f"{case_text} | Loaded {report_path} | Data source: {source}")
            except OSError as error:
                self.status_label.setText(f"Error loading report: {error}")
        else:
            self.status_label.setText(f"{case_text} | No report yet. Data source: {source}")

    # ----------------------------------------------------------- generate
    def _generate_report(self):
        memory_dir = self._memory_dir()
        if not memory_dir:
            QMessageBox.warning(self, "No Analysis Data", "No memory analysis data found. Run the memory analysis on the Analyze Evidence tab first.")
            return
        if memory_dir == SAMPLE_MEMORY_ANALYSIS_DIR and self.selected_case_path:
            answer = QMessageBox.question(self, "Sample data", "This case has no memory analysis results yet. Generate the report from the bundled sample data?",
                                          QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                return
        case_info = load_case_info(self.selected_case_path) if self.selected_case_path else {}
        evidence = list_evidence(self.selected_case_path) if self.selected_case_path else []
        self.generate_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.report_generator_thread = ReportGeneratorThread(memory_dir, case_info, evidence)
        self.report_generator_thread.report_generated.connect(self._on_report_generated)
        self.report_generator_thread.progress_updated.connect(self.status_label.setText)
        self.report_generator_thread.start()

    def _on_report_generated(self, report_content, success):
        self.generate_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        if not success:
            QMessageBox.critical(self, "Generation Failed", report_content)
            self.status_label.setText("Report generation failed")
            return
        reports_dir = self._reports_dir()
        stamped = os.path.join(reports_dir, f"forensic_report_{datetime.now():%Y%m%d_%H%M%S}.md")
        try:
            for path in (stamped, self._latest_report_path()):
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write(report_content)
            if self.selected_case_path:
                record_evidence(self.selected_case_path, [stamped], "forensic_report", compute_hashes=False)
        except OSError as error:
            QMessageBox.critical(self, "Save Error", f"Failed to save report: {error}")
        self._display_report(report_content)
        self.status_label.setText(f"Report generated and saved to {stamped}")

    # ------------------------------------------------------------- export
    def _export_report(self, fmt: str):
        if not self.markdown_content:
            QMessageBox.warning(self, "No Report", "No report content to export.")
            return
        filters = {"md": "Markdown Files (*.md)", "html": "HTML Files (*.html)", "pdf": "PDF Files (*.pdf)"}
        default = os.path.join(self._reports_dir(), f"forensic_report_{datetime.now():%Y%m%d_%H%M%S}.{fmt}")
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Report", default, filters[fmt])
        if not file_path:
            return
        try:
            html_content = REPORT_CSS + _markdown(self.markdown_content)
            if fmt == "md":
                with open(file_path, "w", encoding="utf-8") as handle:
                    handle.write(self.markdown_content)
            elif fmt == "html":
                with open(file_path, "w", encoding="utf-8") as handle:
                    handle.write(f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>Forensic Report</title></head><body>{html_content}</body></html>")
            else:
                writer = QPdfWriter(file_path)
                writer.setPageSize(QPageSize(QPageSize.A4))
                writer.setPageMargins(QMarginsF(15, 15, 15, 15))
                document = QTextDocument()
                document.setHtml(html_content)
                document.print_(writer)
            QMessageBox.information(self, "Export Successful", f"Report exported to: {file_path}")
        except Exception as error:  # noqa: BLE001
            QMessageBox.critical(self, "Export Failed", f"Failed to export report: {error}")
