from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame
)
from PyQt5.QtGui import QPixmap, QFont, QIcon
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from .base_page import BasePage, COLOR_ORANGE, COLOR_DARK, COLOR_GRAY, TAB_NAMES

# Constants
FONT_CARD = QFont("Cascadia Mono", 24, QFont.Weight.Bold)

class ResourcePage(BasePage):
    back_requested = pyqtSignal()
    remote_acquisition_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setup_page_content()

    def setup_page_content(self):
        """Setup the page-specific content for the resource page"""
        # Add tab bar
        self.main_layout.addLayout(self._setup_tab_bar(TAB_NAMES))
        self.main_layout.addSpacing(150)  # Lower the cards

        card_layout = QHBoxLayout()
        card_layout.setSpacing(100)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Remote Acquisition card (with line break)
        remote_card = self._create_card(
            "Remote\nAcquisition",
            "assets/4x/resource iconAsset 22@4x.png",
            self._handle_remote_acquisition_click
        )
        card_layout.addWidget(remote_card)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.VLine)
        divider.setLineWidth(2)
        divider.setStyleSheet(f"background: {COLOR_DARK};")
        divider.setFixedHeight(350)
        card_layout.addWidget(divider)

        # Local Image card
        local_card = self._create_card(
            "Local Image",
            "assets/4x/lap_iconAsset 22@4x.png",
            self._handle_local_image_click
        )
        card_layout.addWidget(local_card)

        self.main_layout.addLayout(card_layout)

    def _create_card(self, title_text, icon_path, callback=None):
        card_widget = QWidget()
        layout = QVBoxLayout(card_widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # Title above the card
        title = QLabel(title_text)
        title.setFont(FONT_CARD)
        title.setStyleSheet(f"color: {COLOR_DARK};")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(title)

        # Card as a button
        card_btn = QPushButton()
        card_btn.setFixedSize(260, 340)
        card_btn.setCursor(Qt.PointingHandCursor)
        card_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: white;
                border: 2.5px solid {COLOR_DARK};
                border-radius: 18px;
                transition: all 0.2s ease;
            }}
            QPushButton:hover {{
                background-color: #f8f8f8;
                border-color: {COLOR_ORANGE};
                transform: translateY(-3px);
                box-shadow: 0 8px 16px rgba(0,0,0,0.15);
            }}
            QPushButton:pressed {{
                transform: translateY(-1px);
                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            }}
        """)
        # Set icon
        pixmap = QPixmap(icon_path)
        if not pixmap.isNull():
            icon = QIcon(pixmap)
            card_btn.setIcon(icon)
            card_btn.setIconSize(QSize(140, 140))
        
        # Connect callback if provided
        if callback:
            card_btn.clicked.connect(callback)
            
        layout.addWidget(card_btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        return card_widget

    def _handle_remote_acquisition_click(self):
        """Handle remote acquisition card click"""
        print("Remote Acquisition clicked")
        self.remote_acquisition_requested.emit()

    def _handle_local_image_click(self):
        """Handle local image card click"""
        print("Local Image clicked")
        # TODO: Implement local image functionality

    def _handle_tab_click(self, clicked_button):
        """Handle tab button clicks"""
        tab_text = clicked_button.text()
        super()._handle_tab_click(clicked_button)
