from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QFileDialog, QMessageBox
)
from PyQt5.QtGui import QPixmap, QFont, QIcon
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from .base_page import BasePage, COLOR_ORANGE, COLOR_DARK, COLOR_GRAY, TAB_NAMES
import datetime
import os
import json

# Constants
FONT_CARD = QFont("Cascadia Mono", 24, QFont.Weight.Bold)

class ResourcePage(BasePage):
    back_requested = pyqtSignal()
    remote_acquisition_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.selected_case_path = None
        self.setup_page_content()

    def set_case_path(self, case_path):
        """Set the case path for storing evidence"""
        self.selected_case_path = case_path
        # Update the case label if it exists
        if hasattr(self, 'case_label'):
            case_name = os.path.basename(case_path)
            self.case_label.setText(f"Selected Case: {case_name}")
            self.case_label.setVisible(True)

    def setup_page_content(self):
        """Setup the page-specific content for the resource page"""
        # Add tab bar
        self.main_layout.addLayout(self._setup_tab_bar(TAB_NAMES))
        self.main_layout.addSpacing(40)

        # Case selection label
        self.case_label = QLabel("No case selected")
        self.case_label.setFont(QFont("Cascadia Mono", 16))
        self.case_label.setStyleSheet(f"color: {COLOR_DARK}; background: white; padding: 8px 16px; border-radius: 8px;")
        self.case_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.case_label.setVisible(False)
        self.main_layout.addWidget(self.case_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.main_layout.addSpacing(100)  # Lower the cards

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
        if not self.selected_case_path:
            QMessageBox.warning(self, "No Case Selected", "Please select a case first from the home page.")
            return
            
        # Open file dialog to select evidence files
        files, _ = QFileDialog.getOpenFileNames(
            self, 
            "Select Evidence Files",
            "",
            "All Files (*.*)"
        )
        
        if files:
            try:
                # Create evidence subfolder in the case directory
                evidence_dir = os.path.join(self.selected_case_path, "evidence")
                os.makedirs(evidence_dir, exist_ok=True)
                
                # Save evidence info
                evidence_info = {
                    "files": files,
                    "timestamp": str(datetime.datetime.now()),
                    "type": "local_image"
                }
                
                evidence_file = os.path.join(evidence_dir, f"evidence_{len(os.listdir(evidence_dir)) + 1}.json")
                with open(evidence_file, "w", encoding="utf-8") as f:
                    json.dump(evidence_info, f, indent=2)
                
                QMessageBox.information(
                    self, 
                    "Success", 
                    f"Evidence files added to case successfully!\nSaved to: {evidence_dir}"
                )
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save evidence: {e}")

    def _handle_tab_click(self, clicked_button):
        """Handle tab button clicks"""
        tab_text = clicked_button.text()
        super()._handle_tab_click(clicked_button)
