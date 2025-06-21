from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGraphicsOpacityEffect, QLineEdit
)
from PyQt5.QtGui import QPixmap, QFont, QIcon
from PyQt5.QtCore import Qt, pyqtSignal, QSize

# Constants
FONT_TITLE = QFont("Cascadia Mono", 22, QFont.Weight.Bold)
FONT_TAB = QFont("Archivo", 16, QFont.Weight.Bold)
COLOR_ORANGE = "#F57C1F"
COLOR_DARK = "#23292f"
COLOR_GRAY = "#e5e5e5"

# Common tab names used across pages
TAB_NAMES = ["Case Info", "Resource", "Analyze Evidence", "Report"]

class BasePage(QWidget):
    tab_selected = pyqtSignal(str)
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background-color: {COLOR_GRAY};")
        self.resize(1600, 1100)
        self.watermark = QLabel(self)
        self.tab_buttons = []
        self._setup_watermark()
        self._setup_base_ui()

    def _setup_watermark(self):
        """Setup the watermark logo that appears on all pages"""
        watermark_pixmap = QPixmap("assets/4x/logoAsset 21@4x.png")
        if not watermark_pixmap.isNull():
            scaled = watermark_pixmap.scaled(3000, 3000, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.watermark.setPixmap(scaled)
            opacity_effect = QGraphicsOpacityEffect()
            opacity_effect.setOpacity(0.09)
            self.watermark.setGraphicsEffect(opacity_effect)
            self.watermark.resize(scaled.size())
            self._position_watermark()
            self.watermark.lower()

    def _position_watermark(self):
        """Position the watermark in the bottom-left corner"""
        margin_left = -80
        margin_bottom = -1150
        x = margin_left
        y = self.height() - self.watermark.height() - margin_bottom
        self.watermark.move(x, y)

    def resizeEvent(self, event):
        """Handle window resize to reposition watermark"""
        super().resizeEvent(event)
        self._position_watermark()

    def _setup_base_ui(self):
        """Setup the base UI elements (top bar and main layout)"""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        # Top bar
        self.top_bar = QLabel("Anubis")
        self.top_bar.setFont(FONT_TITLE)
        self.top_bar.setStyleSheet(f"background-color: {COLOR_DARK}; color: {COLOR_ORANGE}; padding: 6px 28px;")
        self.top_bar.setFixedHeight(48)
        self.top_bar.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.main_layout.addWidget(self.top_bar)

        self.main_layout.addSpacing(12)

    def _setup_tab_bar(self, tab_names):
        """Setup the tab bar with the given tab names"""
        tab_bar_layout = QHBoxLayout()
        tab_bar_layout.setContentsMargins(0, 0, 0, 0)
        tab_bar_layout.addStretch(1)

        container = QWidget()
        container.setStyleSheet("background: white; border-radius: 18px;")
        container.setFixedSize(1500, 68)

        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        for i, name in enumerate(tab_names):
            tab_button = QPushButton(name)
            tab_button.setFont(FONT_TAB)
            tab_button.setCheckable(True)
            tab_button.setAutoExclusive(True)
            tab_button.clicked.connect(lambda checked, b=tab_button: self._handle_tab_click(b))
            tab_button.setFixedHeight(68)
            layout.addWidget(tab_button)
            self.tab_buttons.append(tab_button)

            if i < len(tab_names) - 1:
                divider = QFrame()
                divider.setFrameShape(QFrame.HLine)
                divider.setFixedWidth(80)
                divider.setStyleSheet(f"border-top: 2px solid {COLOR_DARK}; margin: 0 20px;")
                layout.addWidget(divider)

        tab_bar_layout.addWidget(container)
        tab_bar_layout.addStretch(1)

        # Mark the first tab as selected initially
        if self.tab_buttons:
            self.tab_buttons[0].setChecked(True)
            self._handle_tab_click(self.tab_buttons[0])

        return tab_bar_layout

    def _handle_tab_click(self, clicked_button):
        """Centralized tab navigation: emit tab_selected with tab name"""
        for button in self.tab_buttons:
            if button == clicked_button:
                button.setFont(FONT_TAB)
                button.setStyleSheet(f"QPushButton {{ color: {COLOR_ORANGE}; background: transparent; border: none; border-radius: 18px; padding: 8px 24px; }}")
            else:
                button.setFont(FONT_TAB)
                button.setStyleSheet(f"QPushButton {{ color: {COLOR_DARK}; background: transparent; border: none; border-radius: 18px; padding: 8px 24px; }}")
        self.tab_selected.emit(clicked_button.text())

    def _select_tab_programmatically(self, tab_name):
        """Programmatically select a tab without emitting the tab_selected signal"""
        for button in self.tab_buttons:
            if button.text() == tab_name:
                button.setChecked(True)
                button.setFont(FONT_TAB)
                button.setStyleSheet(f"QPushButton {{ color: {COLOR_ORANGE}; background: transparent; border: none; border-radius: 18px; padding: 8px 24px; }}")
            else:
                button.setChecked(False)
                button.setFont(FONT_TAB)
                button.setStyleSheet(f"QPushButton {{ color: {COLOR_DARK}; background: transparent; border: none; border-radius: 18px; padding: 8px 24px; }}")
        # Don't emit the signal to avoid recursion

    def get_input_style(self):
        """Common input field styling"""
        return f"""
            QLineEdit {{
                border: 2.5px solid {COLOR_DARK};
                border-radius: 8px;
                padding: 8px 12px;
                background-color: white;
                color: {COLOR_DARK};
                font-family: 'Cascadia Mono';
                font-size: 14px;
                min-height: 20px;
            }}
            QLineEdit:focus {{
                border-color: {COLOR_ORANGE};
                background-color: #fafafa;
            }}
            QLineEdit:hover {{
                border-color: {COLOR_ORANGE};
                background-color: #f8f8f8;
            }}
        """

    def get_button_style(self, bg_color=COLOR_ORANGE, text_color="white", hover_color="#FF8C42"):
        """Common button styling"""
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: {text_color};
                border-radius: 14px;
                padding: 18px 64px;
                font-family: 'Cascadia Mono';
                font-size: 22px;
                font-weight: bold;
                letter-spacing: 1.2px;
                border: none;
                transition: background-color 0.2s ease;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
                transform: translateY(-1px);
                box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            }}
            QPushButton:pressed {{
                background-color: {bg_color};
                transform: translateY(0px);
                box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            }}
        """

    def create_styled_input(self, placeholder="", is_password=False):
        """Create a styled input field"""
        input_field = QLineEdit()
        input_field.setFont(QFont("Cascadia Mono", 14))
        input_field.setStyleSheet(self.get_input_style())
        input_field.setFixedHeight(44)
        if placeholder:
            input_field.setPlaceholderText(placeholder)
        if is_password:
            input_field.setEchoMode(QLineEdit.EchoMode.Password)
        return input_field

    def create_styled_button(self, text, callback=None, bg_color=COLOR_ORANGE, text_color="white"):
        """Create a styled button"""
        button = QPushButton(text)
        button.setFont(QFont("Cascadia Mono", 20, QFont.Weight.Bold))
        button.setStyleSheet(self.get_button_style(bg_color, text_color))
        if callback:
            button.clicked.connect(callback)
        return button

    def create_folder_button(self, callback=None, icon_size=48):
        """Create a standardized folder button with hover effects"""
        folder_button = QPushButton()
        folder_button.setIcon(QIcon(QPixmap("assets/4x/folder_icon@4x.png").scaled(
            icon_size, icon_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
        folder_button.setIconSize(QSize(icon_size, icon_size))
        folder_button.setCursor(Qt.PointingHandCursor)
        folder_button.setStyleSheet(f"""
            QPushButton {{
                border: none;
                padding: 8px;
                background: transparent;
                border-radius: 6px;
            }}
            QPushButton:pressed {{
                background-color: rgba(245, 124, 31, 0.2);
            }}
        """)
        if callback:
            folder_button.clicked.connect(callback)
        return folder_button

    def setup_page_content(self):
        """Override this method in subclasses to add page-specific content"""
        pass 