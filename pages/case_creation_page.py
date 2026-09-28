from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QLineEdit, QTextEdit, QFormLayout, QComboBox, 
    QDateEdit, QSpinBox, QToolButton, QGridLayout, QFileDialog, QMessageBox
)
from PyQt5.QtGui import QPixmap, QFont, QIcon
from PyQt5.QtCore import Qt, pyqtSignal, QDate, QSize
from .base_page import BasePage, COLOR_ORANGE, COLOR_DARK, COLOR_GRAY, TAB_NAMES
import os
import json
from utils.paths import CASES_DIR, build_case_directory, ensure_case_structure

# Constants
FONT_LABEL = QFont("Cascadia Mono", 13,)
FONT_CARD = QFont("Cascadia Mono", 18, QFont.Weight.Bold)

class CaseCreationPage(BasePage):
    back_requested = pyqtSignal()
    resource_requested = pyqtSignal()
    case_created = pyqtSignal(str)  # path of the new case folder

    def __init__(self):
        super().__init__()
        self.setup_page_content()

    def setup_page_content(self):
        """Setup the page-specific content for the case creation page"""
        # Add tab bar
        self.main_layout.addLayout(self._setup_tab_bar(TAB_NAMES))
        self.main_layout.addSpacing(40)

        form_container = QWidget()
        form_container.setStyleSheet("""
            QWidget {
                background-color: white;
                border-radius: 18px;
            }
        """)
        form_container.setFixedSize(1200, 600)

        form_layout = QVBoxLayout(form_container)
        form_layout.setContentsMargins(32, 18, 32, 18)
        form_layout.setSpacing(8)

        # --- Section: Case ---
        case_section = QLabel("Case")
        case_section.setFont(FONT_CARD)
        case_section.setStyleSheet(f"color: {COLOR_DARK}; margin-bottom: 2px;")
        form_layout.addWidget(case_section, alignment=Qt.AlignmentFlag.AlignLeft)

        # --- All Fields in a 2-column Grid ---
        fields_layout = QGridLayout()
        fields_layout.setHorizontalSpacing(32)
        fields_layout.setVerticalSpacing(18)

        # Row 0: Number / Name
        number_label = QLabel("Number")
        number_label.setFont(FONT_LABEL)
        number_label.setStyleSheet(f"color: {COLOR_DARK};")
        fields_layout.addWidget(number_label, 0, 0)
        self.case_number_input = self.create_styled_input()
        fields_layout.addWidget(self.case_number_input, 1, 0)

        name_label = QLabel("Name")
        name_label.setFont(FONT_LABEL)
        name_label.setStyleSheet(f"color: {COLOR_DARK};")
        fields_layout.addWidget(name_label, 0, 1)
        self.case_name_input = self.create_styled_input()
        fields_layout.addWidget(self.case_name_input, 1, 1)

        # Row 2: Locations header
        locations_section = QLabel("Locations")
        locations_section.setFont(FONT_CARD)
        locations_section.setStyleSheet(f"color: {COLOR_DARK}; margin-top: 8px; margin-bottom: 2px;")
        fields_layout.addWidget(locations_section, 2, 0, 1, 2)

        # Row 3: Files / Evidence
        files_label = QLabel("Files Location")
        files_label.setFont(FONT_LABEL)
        files_label.setStyleSheet(f"color: {COLOR_DARK};")
        fields_layout.addWidget(files_label, 3, 0)
        self.files_button = self.create_folder_button(self._choose_files_folder, 48)
        self.files_input = self.create_styled_input()
        files_field_widget = QWidget()
        files_field_layout = QHBoxLayout(files_field_widget)
        files_field_layout.setContentsMargins(0, 0, 0, 0)
        files_field_layout.setSpacing(0)
        files_field_layout.addWidget(self.files_input)
        files_field_layout.addWidget(self.files_button)
        fields_layout.addWidget(files_field_widget, 4, 0)

        evidence_label = QLabel("Evidence")
        evidence_label.setFont(FONT_LABEL)
        evidence_label.setStyleSheet(f"color: {COLOR_DARK};")
        fields_layout.addWidget(evidence_label, 3, 1)
        self.evidence_button = self.create_folder_button(self._choose_evidence, 48)
        self.evidence_input = self.create_styled_input()
        evidence_field_widget = QWidget()
        evidence_field_layout = QHBoxLayout(evidence_field_widget)
        evidence_field_layout.setContentsMargins(0, 0, 0, 0)
        evidence_field_layout.setSpacing(0)
        evidence_field_layout.addWidget(self.evidence_input)
        evidence_field_layout.addWidget(self.evidence_button)
        fields_layout.addWidget(evidence_field_widget, 4, 1)

        # Row 5: Scan header
        scan_section = QLabel("Scan")
        scan_section.setFont(FONT_CARD)
        scan_section.setStyleSheet(f"color: {COLOR_DARK}; margin-top: 8px; margin-bottom: 2px;")
        fields_layout.addWidget(scan_section, 5, 0, 1, 2)

        # Row 6: By / Notes
        by_label = QLabel("By")
        by_label.setFont(FONT_LABEL)
        by_label.setStyleSheet(f"color: {COLOR_DARK};")
        fields_layout.addWidget(by_label, 6, 0)
        self.scan_by_input = self.create_styled_input()
        fields_layout.addWidget(self.scan_by_input, 7, 0)

        notes_label = QLabel("Notes")
        notes_label.setFont(FONT_LABEL)
        notes_label.setStyleSheet(f"color: {COLOR_DARK};")
        fields_layout.addWidget(notes_label, 6, 1)
        self.notes_input = self.create_styled_input()
        fields_layout.addWidget(self.notes_input, 7, 1)

        form_layout.addLayout(fields_layout)
        form_layout.addStretch()

        self.main_layout.addWidget(form_container, alignment=Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addSpacing(16)

        # --- Button Row: Go To Source + Create Case ---
        button_row = QHBoxLayout()
        button_row.setSpacing(24)
        button_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        go_to_source_button = self.create_styled_button("Go To Source", self._handle_go_to_source_click)
        button_row.addWidget(go_to_source_button)

        create_case_button = QPushButton("Create Case")
        create_case_button.setStyleSheet("""
            QPushButton {
                background-color: #1D252D;
                color: white;
                font-size: 18px;
                border-radius: 8px;
                padding: 12px 32px;
            }
            QPushButton:hover {
                background-color: #151A1F;
            }
        """)
        create_case_button.setFixedSize(go_to_source_button.sizeHint())
        create_case_button.clicked.connect(self._handle_create_case_click)
        button_row.addWidget(create_case_button)

        self.main_layout.addLayout(button_row)
        self.main_layout.addStretch()

    def _handle_go_to_source_click(self):
        if getattr(self, "created_case_path", None):
            self.case_created.emit(self.created_case_path)
        else:
            self.resource_requested.emit()

    def _choose_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files")
        if files:
            self.files_input.setText("; ".join(files))

    def _choose_files_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder for Case")
        if folder:
            self.files_input.setText(folder)
            # Set evidence location to the same path by default
            if not self.evidence_input.text().strip():
                self.evidence_input.setText(folder)

    def _choose_evidence(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Evidence Files")
        if files:
            self.evidence_input.setText("; ".join(files))

    def _handle_create_case_click(self):
        # Gather form data
        case_number = self.case_number_input.text().strip()
        case_name = self.case_name_input.text().strip()
        files = self.files_input.text().strip()
        evidence = self.evidence_input.text().strip()
        scan_by = self.scan_by_input.text().strip()
        notes = self.notes_input.text().strip()

        def show_custom_messagebox(icon, title, message):
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle(title)
            msg_box.setText(message)
            msg_box.setIcon(icon)
            msg_box.setStyleSheet(f"""
                QMessageBox {{
                    background-color: white;
                    border-radius: 16px;
                    font-family: 'Cascadia Mono', Arial, sans-serif;
                    font-size: 18px;
                    color: {COLOR_DARK};
                }}
                QPushButton {{
                    background-color: {COLOR_ORANGE};
                    color: white;
                    border-radius: 8px;
                    font-size: 16px;
                    min-width: 80px;
                    min-height: 32px;
                }}
                QPushButton:hover {{
                    background-color: #ff9800;
                }}
            """)
            msg_box.exec_()

        if not case_number or not case_name:
            show_custom_messagebox(QMessageBox.Warning, "Missing Data", "Case number and name are required.")
            return

        parent_dir = CASES_DIR
        os.makedirs(parent_dir, exist_ok=True)

        case_folder = build_case_directory(case_number, case_name, parent_dir=parent_dir)
        if os.path.exists(case_folder):
            show_custom_messagebox(QMessageBox.Warning, "Case Exists", "A case with this number and name already exists in the project cases folder.")
            return
        os.makedirs(case_folder)
        ensure_case_structure(case_folder)

        # Save case info as JSON
        case_info = {
            "number": case_number,
            "name": case_name,
            "files": files,
            "evidence": evidence,
            "scan_by": scan_by,
            "notes": notes
        }
        info_path = os.path.join(case_folder, "info.json")
        try:
            with open(info_path, "w", encoding="utf-8") as f:
                json.dump(case_info, f, indent=2)
            show_custom_messagebox(QMessageBox.Information, "Success", f"Case '{case_name}' created successfully at {case_folder}.")
            self.created_case_path = case_folder
            self.case_created.emit(case_folder)
        except Exception as e:
            show_custom_messagebox(QMessageBox.Critical, "Error", f"Failed to save case: {e}")