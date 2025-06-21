from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QDialog, QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem, QLineEdit, QHeaderView, QMessageBox
)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt, pyqtSignal
from .base_page import BasePage, COLOR_ORANGE, COLOR_DARK, COLOR_GRAY, TAB_NAMES
import os
import json

# Constants
FONT_CARD = QFont("Cascadia Mono", 24, QFont.Weight.Bold)
FONT_PLUS = QFont("Arial", 80)
FONT_BUTTON = QFont("Cascadia Mono", 22, QFont.Weight.Bold)

class HomePage(BasePage):
    create_case_requested = pyqtSignal()
    add_evidence_requested = pyqtSignal(str)  # Signal with selected case folder path

    def __init__(self):
        super().__init__()
        self.setup_page_content()

    def setup_page_content(self):
        """Setup the page-specific content for the home page"""
        # Add tab bar
        self.main_layout.addLayout(self._setup_tab_bar(TAB_NAMES))

        self.main_layout.addSpacing(40)
        card_layout = QHBoxLayout()
        card_layout.setSpacing(100)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card_layout.addLayout(self._create_card("Create New Case", self.handle_create_case))

        divider = QFrame()
        divider.setFrameShape(QFrame.VLine)
        divider.setLineWidth(2)
        divider.setStyleSheet(f"background: {COLOR_DARK};")
        divider.setFixedHeight(300)
        card_layout.addWidget(divider)

        card_layout.addLayout(self._create_card("Add Evidence To\nExisting Case", self.handle_add_evidence))
        self.main_layout.addLayout(card_layout)

        self.main_layout.addSpacing(40)
        browse_button = self.create_styled_button("Browse Recent Cases", self._handle_browse_cases_click)
        self.main_layout.addWidget(browse_button, alignment=Qt.AlignmentFlag.AlignCenter)

    def _create_card(self, title_text, callback):
        layout = QVBoxLayout()
        layout.setSpacing(12)

        title = QLabel(title_text)
        title.setFont(FONT_CARD)
        title.setStyleSheet(f"color: {COLOR_DARK};")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(title)

        plus_button = QPushButton("+")
        plus_button.setFont(FONT_PLUS)
        plus_button.setFixedSize(260, 340)
        plus_button.setCursor(Qt.CursorShape.PointingHandCursor)
        plus_button.setStyleSheet(f"""
            QPushButton {{
                background-color: white;
                border: 2px solid {COLOR_DARK};
                border-radius: 16px;
                color: {COLOR_DARK};
                transition: all 0.2s ease;
            }}
            QPushButton:hover {{
                background-color: #f8f8f8;
                border-color: {COLOR_ORANGE};
                color: {COLOR_ORANGE};
                transform: translateY(-2px);
                box-shadow: 0 6px 12px rgba(0,0,0,0.15);
            }}
            QPushButton:pressed {{
                transform: translateY(0px);
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
        """)
        plus_button.clicked.connect(callback)
        layout.addWidget(plus_button, alignment=Qt.AlignmentFlag.AlignCenter)
        return layout

    def handle_create_case(self):
        print("Create New Case clicked")
        self.create_case_requested.emit()

    def handle_add_evidence(self):
        cases_dir = os.path.join(os.getcwd(), "cases")
        cases = []
        if os.path.exists(cases_dir):
            for folder in os.listdir(cases_dir):
                folder_path = os.path.join(cases_dir, folder)
                if os.path.isdir(folder_path):
                    info_path = os.path.join(folder_path, "info.json")
                    case_number = ""
                    case_name = ""
                    if os.path.exists(info_path):
                        try:
                            with open(info_path, "r", encoding="utf-8") as f:
                                info = json.load(f)
                            case_number = info.get('number', '')
                            case_name = info.get('name', '')
                        except Exception:
                            case_number = ""
                            case_name = ""
                    cases.append({
                        'number': case_number,
                        'name': case_name,
                        'folder': folder,
                        'path': folder_path
                    })

        if not cases:
            QMessageBox.information(self, "No Cases", "No existing cases found. Please create a case first.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Select Case to Add Evidence")
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: white;
                border-radius: 18px;
            }}
            QLabel {{
                font-family: 'Cascadia Mono';
                font-size: 20px;
                color: {COLOR_DARK};
            }}
            QTableWidget {{
                font-family: 'Cascadia Mono';
                font-size: 18px;
                color: {COLOR_DARK};
                background: #f8f8f8;
                border-radius: 12px;
                padding: 8px;
            }}
            QLineEdit {{
                font-family: 'Cascadia Mono';
                font-size: 16px;
                border: 2px solid {COLOR_ORANGE};
                border-radius: 8px;
                padding: 6px 12px;
                margin-bottom: 12px;
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
        layout = QVBoxLayout(dialog)
        label = QLabel("Select a case to add evidence:")
        layout.addWidget(label)

        # Search bar
        search_bar = QLineEdit()
        search_bar.setPlaceholderText("Search by case number, name, or folder...")
        layout.addWidget(search_bar)

        # Table
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Case Number", "Case Name", "Folder"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setRowCount(len(cases))
        for row, case in enumerate(cases):
            table.setItem(row, 0, QTableWidgetItem(case['number']))
            table.setItem(row, 1, QTableWidgetItem(case['name']))
            table.setItem(row, 2, QTableWidgetItem(case['folder']))
        layout.addWidget(table)

        def filter_cases():
            text = search_bar.text().lower()
            for row, case in enumerate(cases):
                visible = (
                    text in case['number'].lower() or
                    text in case['name'].lower() or
                    text in case['folder'].lower()
                )
                table.setRowHidden(row, not visible)
        search_bar.textChanged.connect(filter_cases)

        def select_case():
            current_row = table.currentRow()
            if current_row >= 0:
                selected_case = cases[current_row]
                dialog.accept()
                self.add_evidence_requested.emit(selected_case['path'])
            else:
                QMessageBox.warning(dialog, "No Selection", "Please select a case first.")

        def on_double_click(row, _col):
            if row >= 0:
                selected_case = cases[row]
                dialog.accept()
                self.add_evidence_requested.emit(selected_case['path'])

        table.cellDoubleClicked.connect(on_double_click)

        # Buttons
        button_layout = QHBoxLayout()
        select_btn = QPushButton("Select Case")
        select_btn.clicked.connect(select_case)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(select_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

        dialog.setLayout(layout)
        dialog.setMinimumWidth(700)
        dialog.exec_()

    def _handle_browse_cases_click(self):
        cases_dir = os.path.join(os.getcwd(), "cases")
        cases = []
        if os.path.exists(cases_dir):
            for folder in os.listdir(cases_dir):
                folder_path = os.path.join(cases_dir, folder)
                if os.path.isdir(folder_path):
                    info_path = os.path.join(folder_path, "info.json")
                    case_number = ""
                    case_name = ""
                    if os.path.exists(info_path):
                        try:
                            with open(info_path, "r", encoding="utf-8") as f:
                                info = json.load(f)
                            case_number = info.get('number', '')
                            case_name = info.get('name', '')
                        except Exception:
                            case_number = ""
                            case_name = ""
                    cases.append({
                        'number': case_number,
                        'name': case_name,
                        'folder': folder,
                        'path': folder_path
                    })

        class CaseDetailsDialog(QDialog):
            def __init__(self, case_info, parent=None):
                super().__init__(parent)
                self.setWindowTitle(f"Case Details: {case_info['name'] or case_info['folder']}")
                self.setStyleSheet(parent.styleSheet())
                layout = QVBoxLayout(self)
                for key, value in case_info.items():
                    if key == 'path': continue
                    label = QLabel(f"<b>{key.capitalize()}:</b> {value}")
                    label.setStyleSheet("font-size: 18px; margin-bottom: 8px;")
                    layout.addWidget(label)
                close_btn = QPushButton("Close")
                close_btn.clicked.connect(self.accept)
                layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        dialog = QDialog(self)
        dialog.setWindowTitle("Browse Cases")
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: white;
                border-radius: 18px;
            }}
            QLabel {{
                font-family: 'Cascadia Mono';
                font-size: 20px;
                color: {COLOR_DARK};
            }}
            QTableWidget {{
                font-family: 'Cascadia Mono';
                font-size: 18px;
                color: {COLOR_DARK};
                background: #f8f8f8;
                border-radius: 12px;
                padding: 8px;
            }}
            QLineEdit {{
                font-family: 'Cascadia Mono';
                font-size: 16px;
                border: 2px solid {COLOR_ORANGE};
                border-radius: 8px;
                padding: 6px 12px;
                margin-bottom: 12px;
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
        layout = QVBoxLayout(dialog)
        label = QLabel("Previously Created Cases:")
        layout.addWidget(label)

        # Search bar
        search_bar = QLineEdit()
        search_bar.setPlaceholderText("Search by case number, name, or folder...")
        layout.addWidget(search_bar)

        # Table
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Case Number", "Case Name", "Folder"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setRowCount(len(cases))
        for row, case in enumerate(cases):
            table.setItem(row, 0, QTableWidgetItem(case['number']))
            table.setItem(row, 1, QTableWidgetItem(case['name']))
            table.setItem(row, 2, QTableWidgetItem(case['folder']))
        layout.addWidget(table)

        def filter_cases():
            text = search_bar.text().lower()
            for row, case in enumerate(cases):
                visible = (
                    text in case['number'].lower() or
                    text in case['name'].lower() or
                    text in case['folder'].lower()
                )
                table.setRowHidden(row, not visible)
        search_bar.textChanged.connect(filter_cases)

        def show_details(row, _col):
            if 0 <= row < len(cases):
                dlg = CaseDetailsDialog(cases[row], parent=dialog)
                dlg.exec_()
        table.cellDoubleClicked.connect(show_details)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        dialog.setLayout(layout)
        dialog.setMinimumWidth(700)
        dialog.exec_() 