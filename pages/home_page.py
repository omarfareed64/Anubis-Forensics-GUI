from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame
)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt, pyqtSignal
from .base_page import BasePage, COLOR_ORANGE, COLOR_DARK, COLOR_GRAY, TAB_NAMES

# Constants
FONT_CARD = QFont("Cascadia Mono", 24, QFont.Weight.Bold)
FONT_PLUS = QFont("Arial", 80)
FONT_BUTTON = QFont("Cascadia Mono", 22, QFont.Weight.Bold)

class HomePage(BasePage):
    create_case_requested = pyqtSignal()

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
        print("Add Evidence to Existing Case clicked")

    def _handle_browse_cases_click(self):
        print("Browse Recent Cases button clicked!") 