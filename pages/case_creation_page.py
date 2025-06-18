from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QLineEdit, QTextEdit, QFormLayout, QComboBox, 
    QDateEdit, QSpinBox, QToolButton, QGridLayout, QFileDialog
)
from PyQt5.QtGui import QPixmap, QFont, QIcon
from PyQt5.QtCore import Qt, pyqtSignal, QDate, QSize
from .base_page import BasePage, COLOR_ORANGE, COLOR_DARK, COLOR_GRAY, TAB_NAMES

# Constants
FONT_LABEL = QFont("Cascadia Mono", 13,)
FONT_CARD = QFont("Cascadia Mono", 18, QFont.Weight.Bold)

class CaseCreationPage(BasePage):
    back_requested = pyqtSignal()
    resource_requested = pyqtSignal()

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
        files_label = QLabel("Files")
        files_label.setFont(FONT_LABEL)
        files_label.setStyleSheet(f"color: {COLOR_DARK};")
        fields_layout.addWidget(files_label, 3, 0)
        self.files_button = self.create_folder_button(self._choose_files, 48)
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

        go_to_source_button = self.create_styled_button("Go To Source", self._handle_go_to_source_click)
        self.main_layout.addWidget(go_to_source_button, alignment=Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addStretch()

    def _handle_go_to_source_click(self):
        print("Go To Source button clicked!")
        self.resource_requested.emit()

    def _choose_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files")
        if files:
            self.files_input.setText("; ".join(files))

    def _choose_evidence(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Evidence Files")
        if files:
            self.evidence_input.setText("; ".join(files))