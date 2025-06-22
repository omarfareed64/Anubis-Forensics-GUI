import os
import json
from datetime import datetime
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QFrame, QMessageBox, QProgressBar, QListWidget, QListWidgetItem, QFileDialog
)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from .base_page import BasePage, COLOR_ORANGE, COLOR_DARK, COLOR_GRAY
from services.report_service import ReportService
import mistune

MEMORY_ANALYSIS_DIR = "Anubis-Forensics-GUI/memory_analysis"

class ReportGeneratorThread(QThread):
    report_generated = pyqtSignal(str, bool)
    progress_updated = pyqtSignal(str)
    
    def run(self):
        try:
            self.progress_updated.emit("Initializing report service...")
            memory_analysis_dir = MEMORY_ANALYSIS_DIR
            if not os.path.exists(memory_analysis_dir):
                self.report_generated.emit("No memory analysis data found.", False)
                return
            self.progress_updated.emit("Loading analysis data...")
            report_service = ReportService(memory_analysis_dir)
            self.progress_updated.emit("Generating comprehensive report...")
            report_content = report_service.generate_report()
            self.progress_updated.emit("Report generation completed!")
            self.report_generated.emit(report_content, True)
        except Exception as e:
            self.report_generated.emit(f"Report generation failed: {str(e)}", False)

class ReportPage(BasePage):
    def __init__(self):
        super().__init__()
        self.report_generator_thread = None
        self.markdown_content = ""  # Store raw markdown for export
        self._setup_ui()
        self._load_reports()

    def _setup_ui(self):
        # Add tab bar
        tab_layout = self._setup_tab_bar(["Case Info", "Resource", "Analyze Evidence", "Report"])
        self.main_layout.addLayout(tab_layout)
        self.main_layout.addSpacing(30)
        
        # Simple centered layout
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(100, 0, 100, 50)
        content_layout.setSpacing(20)
        
        # Title
        title = QLabel("Forensic Report")
        title.setFont(QFont("Cascadia Mono", 24, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLOR_DARK}; text-align: center;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(title)
        
        # Status and controls
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(20)

        # A more compact button style for this page
        button_style = """
            QPushButton {{
                background-color: {bg_color};
                color: {text_color};
                border-radius: 12px;
                padding: 10px;
                font-family: 'Cascadia Mono';
                font-size: 13px;
                font-weight: bold;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
        """
        
        # Generate button
        self.generate_btn = QPushButton("Generate Report")
        self.generate_btn.setStyleSheet(button_style.format(
            bg_color=COLOR_ORANGE, text_color="white", hover_color="#FF8C42"
        ))
        self.generate_btn.setFixedSize(200, 50)
        self.generate_btn.clicked.connect(self._generate_report)
        controls_layout.addWidget(self.generate_btn)
        
        # Export button
        self.export_btn = QPushButton("Export Markdown")
        self.export_btn.setStyleSheet(button_style.format(
            bg_color=COLOR_DARK, text_color="white", hover_color="#4a4a4a"
        ))
        self.export_btn.setFixedSize(180, 50)
        self.export_btn.clicked.connect(self._export_report)
        self.export_btn.setEnabled(False)
        controls_layout.addWidget(self.export_btn)
        
        # Refresh button
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setStyleSheet(button_style.format(
            bg_color="#28a745", text_color="white", hover_color="#218838"
        ))
        self.refresh_btn.setFixedSize(120, 50)
        self.refresh_btn.clicked.connect(self._load_reports)
        controls_layout.addWidget(self.refresh_btn)
        
        controls_layout.addStretch()
        content_layout.addLayout(controls_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 2px solid {COLOR_DARK};
                border-radius: 8px;
                text-align: center;
                background-color: white;
                height: 30px;
                font-size: 12px;
            }}
            QProgressBar::chunk {{
                background-color: {COLOR_ORANGE};
                border-radius: 6px;
            }}
        """)
        content_layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel("Ready to generate forensic report")
        self.status_label.setFont(QFont("Cascadia Mono", 12))
        self.status_label.setStyleSheet(f"color: {COLOR_DARK}; text-align: center;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(self.status_label)
        
        # Report content
        self.report_content = QTextEdit()
        self.report_content.setFont(QFont("Cascadia Mono", 11))
        self.report_content.setStyleSheet(f"""
            QTextEdit {{
                border: 2px solid {COLOR_DARK};
                border-radius: 12px;
                background-color: white;
                color: {COLOR_DARK};
                padding: 20px;
                margin: 10px;
            }}
        """)
        self.report_content.setReadOnly(True)
        self.report_content.setPlaceholderText("Click 'Generate Report' to create a forensic analysis report...")
        content_layout.addWidget(self.report_content)
        
        self.main_layout.addLayout(content_layout)

    def _display_report(self, markdown_content):
        self.markdown_content = markdown_content
        
        # Basic CSS for styling the HTML report
        html_style = """
        <style>
            body { font-family: 'Cascadia Mono', sans-serif; color: #23292f; }
            h1, h2, h3 { color: #F57C1F; border-bottom: 2px solid #23292f; padding-bottom: 5px; }
            table { border-collapse: collapse; width: 100%; margin: 15px 0; }
            th, td { border: 1px solid #ccc; padding: 10px; text-align: left; }
            th { background-color: #23292f; color: white; }
            tr:nth-child(even) { background-color: #f2f2f2; }
            code { background-color: #eee; padding: 2px 5px; border-radius: 4px; }
            pre { background-color: #eee; padding: 10px; border-radius: 4px; white-space: pre-wrap; }
        </style>
        """
        html_content = mistune.html(markdown_content)
        self.report_content.setHtml(html_style + html_content)
        self.export_btn.setEnabled(True)

    def _load_reports(self):
        # Check if memory_analysis directory exists
        if not os.path.exists(MEMORY_ANALYSIS_DIR):
            self.status_label.setText("No memory analysis data found")
            return
            
        # Check for existing report
        forensic_report = os.path.join(MEMORY_ANALYSIS_DIR, "forensic_report.md")
        if os.path.exists(forensic_report):
            try:
                with open(forensic_report, 'r', encoding='utf-8') as f:
                    content = f.read()
                self._display_report(content)
                self.status_label.setText("Report loaded successfully")
            except Exception as e:
                self.status_label.setText(f"Error loading report: {str(e)}")
        else:
            self.status_label.setText("No existing report found. Click 'Generate Report' to create one.")

    def _generate_report(self):
        if not os.path.exists(MEMORY_ANALYSIS_DIR):
            QMessageBox.warning(self, "No Analysis Data", "No memory analysis data found. Please run analysis first.")
            return
            
        self.generate_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.status_label.setText("Generating report...")
        
        self.report_generator_thread = ReportGeneratorThread()
        self.report_generator_thread.report_generated.connect(self._on_report_generated)
        self.report_generator_thread.progress_updated.connect(self.status_label.setText)
        self.report_generator_thread.start()

    def _on_report_generated(self, report_content, success):
        self.generate_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        if success:
            report_path = os.path.join(MEMORY_ANALYSIS_DIR, "forensic_report.md")
            try:
                with open(report_path, 'w', encoding='utf-8') as f:
                    f.write(report_content)
                self._display_report(report_content)
                self.status_label.setText("Report generated successfully!")
                QMessageBox.information(self, "Success", "Forensic report has been generated successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save report: {str(e)}")
        else:
            QMessageBox.critical(self, "Generation Failed", f"Failed to generate report: {report_content}")
            
        self.status_label.setText("Ready to generate forensic report")

    def _export_report(self):
        if not self.markdown_content:
            QMessageBox.warning(self, "No Report", "No report content to export.")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Report",
            f"forensic_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
            "Markdown Files (*.md);;Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.markdown_content)
                QMessageBox.information(self, "Export Successful", f"Report exported to: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", f"Failed to export report: {str(e)}") 