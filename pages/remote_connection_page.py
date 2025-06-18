from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QGroupBox, QFrame, QSizePolicy, QHeaderView
)
from PyQt5.QtGui import QFont, QPixmap, QColor, QIcon
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from .base_page import BasePage, COLOR_ORANGE, COLOR_DARK, COLOR_GRAY, TAB_NAMES

FONT_TAB = QFont("Cascadia Mono", 16, QFont.Weight.Bold)
FONT_CARD = QFont("Cascadia Mono", 16, QFont.Weight.Bold)
FONT_TABLE_HEADER = QFont("Cascadia Mono", 14, QFont.Weight.Bold)
FONT_TABLE = QFont("Cascadia Mono", 13)
FONT_BTN = QFont("Cascadia Mono", 18, QFont.Weight.Bold)
FONT_SIDEBAR_LABEL = QFont("Cascadia Mono", 12, QFont.Weight.Bold)
FONT_SIDEBAR_VALUE = QFont("Cascadia Mono", 11)

class RemoteConnectionPage(BasePage):
    back_requested = pyqtSignal()
    def __init__(self):
        super().__init__()
        self.setup_page_content()

    def setup_page_content(self):
        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        # Add tab bar
        self.main_layout.addLayout(self._setup_tab_bar(TAB_NAMES))
        self.main_layout.addSpacing(20)

        # Main horizontal layout
        main_hbox = QHBoxLayout()
        main_hbox.setSpacing(30)
        main_hbox.setContentsMargins(40, 0, 40, 0)

        # Sidebar
        sidebar = self._sidebar()
        main_hbox.addWidget(sidebar)

        # Center content (cards + table)
        center_content = QWidget()
        center_vbox = QVBoxLayout(center_content)
        center_vbox.setSpacing(24)
        center_vbox.setContentsMargins(0, 0, 0, 0)

        # Cards row
        cards_hbox = QHBoxLayout()
        cards_hbox.setSpacing(60)
        cards_hbox.addWidget(self._card('TARGETED\n LOCATIONS', 'assets/4x/targeted locationsAsset 24@4x.png'))
        cards_hbox.addWidget(self._card('FILES &\n FOLDERS', 'assets/4x/file_foldersAsset 25@4x.png'))
        cards_hbox.addWidget(self._card('MEMORY', 'assets/4x/memoryAsset 26@4x.png'))
        center_vbox.addLayout(cards_hbox)
        center_vbox.addSpacing(18)

        # Table
        table = self._evidence_table()
        center_vbox.addWidget(table)
        center_vbox.addSpacing(24)

        # Analyze button
        analyze_btn = self.create_styled_button("ANALYZE EVIDENCES")
        analyze_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        center_vbox.addWidget(analyze_btn, alignment=Qt.AlignCenter)

        # Back button (bottom left)
        back_btn = self.create_styled_button("Back", self.back_requested.emit, COLOR_DARK, "white")
        center_vbox.addWidget(back_btn, alignment=Qt.AlignLeft)

        main_hbox.addWidget(center_content, stretch=1)
        self.main_layout.addLayout(main_hbox)
        self.main_layout.addStretch()

    def _sidebar(self):
        sidebar = QWidget()
        sidebar.setFixedWidth(260)
        vbox = QVBoxLayout(sidebar)
        vbox.setContentsMargins(16, 24, 16, 24)
        vbox.setSpacing(10)
        # Icon
        icon = QLabel()
        pix = QPixmap('assets/4x/lap_iconAsset 22@4x.png')
        if not pix.isNull():
            icon.setPixmap(pix.scaled(400,400, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        icon.setAlignment(Qt.AlignCenter)
        vbox.addWidget(icon)
        # Info
        info = [
            ("Computer name:", "Elhamd-hardware"),
            ("Username:", "hamra1223"),
            ("End point IP:", "192.168.121.33"),
            ("Computer State:", "Conected")
        ]
        for label, value in info:
            row = QLabel()
            if label == "Computer State:":
                row.setText(f'<b>{label}</b> <span style="color:#2e7d32;">{value}</span> <span style="color:#ff5722; font-size:18px;">●</span>')
            else:
                row.setText(f'<b>{label}</b> <span style="color:#23292f;">{value}</span>')
            row.setFont(FONT_SIDEBAR_LABEL)
            vbox.addWidget(row)
        # Refresh button
        refresh = QPushButton("Refresh")
        refresh.setFont(FONT_SIDEBAR_LABEL)
        refresh.setFixedWidth(100)
        refresh.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_DARK};
                color: white;
                border-radius: 8px;
                padding: 6px 0;
                border: none;
                transition: all 0.2s ease;
            }}
            QPushButton:hover {{
                background-color: {COLOR_ORANGE};
                transform: translateY(-1px);
                box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            }}
            QPushButton:pressed {{
                transform: translateY(0px);
            }}
        """)
        refresh.clicked.connect(self._handle_refresh_click)
        vbox.addWidget(refresh, alignment=Qt.AlignLeft)
        vbox.addStretch()
        sidebar.setStyleSheet("background: white; border-radius: 18px;")
        return sidebar

    def _card(self, title, icon_path):
        card = QPushButton()
        card.setStyleSheet(f"""
            QPushButton {{
                border: 2px solid black;
                border-radius: 10px;
                background: white;
                transition: border-color 0.2s;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: #f5f5f5;
            }}
            QPushButton:pressed {{
                background-color: #e0e0e0;
                transform: translateY(1px);
            }}
        """)
        card.setFixedSize(280, 220)
        card.setCursor(Qt.PointingHandCursor)
        
        # Create layout for the button content
        v = QVBoxLayout(card)
        v.setAlignment(Qt.AlignCenter)
        v.setContentsMargins(0, 0, 0, 0)  # Remove margins to avoid gray background
        
        icon = QLabel()
        pix = QPixmap(icon_path)
        if not pix.isNull():
            icon.setPixmap(pix.scaled(400,400, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            icon.setText("[icon]")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("background: transparent;")  # Ensure no background
        v.addWidget(icon)
        
        title_label = QLabel(title)
        title_label.setFont(FONT_CARD)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("background: transparent;")  # Ensure no background
        v.addWidget(title_label)
        
        # Connect click handler based on card type
        if "TARGETED" in title:
            card.clicked.connect(self._handle_targeted_locations_click)
        elif "FILES" in title:
            card.clicked.connect(self._handle_files_folders_click)
        elif "MEMORY" in title:
            card.clicked.connect(self._handle_memory_click)
        
        return card

    def _handle_targeted_locations_click(self):
        """Handle targeted locations card click"""
        print("Targeted Locations card clicked")
        # TODO: Implement navigation to targeted locations page or functionality
        
    def _handle_files_folders_click(self):
        """Handle files & folders card click"""
        print("Files & Folders card clicked")
        # TODO: Implement navigation to files & folders page or functionality
        
    def _handle_memory_click(self):
        """Handle memory card click"""
        print("Memory card clicked")
        # TODO: Implement navigation to memory page or functionality

    def _evidence_table(self):
        table = QTableWidget(4, 4)
        table.setHorizontalHeaderLabels(["Item", "STARTED AT DATE/TIME", "SIZE", ""])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setFont(FONT_TABLE)
        table.setStyleSheet(f"QHeaderView::section {{background: {COLOR_DARK}; color: white; font-weight: bold; font-size: 15px;}} QTableWidget {{background: white; border-radius: 12px;}}")
        data = [
            ("$MFT", "01/12/2021 - 10:34:02", "5.8 MB"),
            ("Hobatito.exe", "01/12/2021 - 10:34:02", "200 KB"),
            ("EV.LOG", "01/12/2021 - 10:34:02", "88.1 MB"),
            ("Meen.exe", "01/12/2021 - 10:34:02", "501 MB"),
        ]
        for row, (item, dt, size) in enumerate(data):
            table.setItem(row, 0, QTableWidgetItem(item))
            table.setItem(row, 1, QTableWidgetItem(dt))
            table.setItem(row, 2, QTableWidgetItem(size))
            del_btn = QPushButton("DELETE")
            del_btn.setFont(FONT_SIDEBAR_LABEL)
            del_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLOR_ORANGE};
                    color: white;
                    border-radius: 5px;
                    padding: 4px 12px;
                    border: none;
                    transition: all 0.2s ease;
                }}
                QPushButton:hover {{
                    background-color: #d32f2f;
                    transform: translateY(-1px);
                    box-shadow: 0 2px 4px rgba(0,0,0,0.2);
                }}
                QPushButton:pressed {{
                    transform: translateY(0px);
                }}
            """)
            del_btn.clicked.connect(lambda checked, row=row: self._handle_delete_click(table, row))
            table.setCellWidget(row, 3, del_btn)
        table.setFixedHeight(220)
        return table

    def _handle_refresh_click(self):
        """Handle refresh button click"""
        print("Refresh button clicked - refreshing connection data...")
        # TODO: Implement actual refresh logic
        # This could update the sidebar info, table data, etc.
        
    def _handle_delete_click(self, table, row):
        table.removeRow(row)
        print(f"Deleted row {row}")
