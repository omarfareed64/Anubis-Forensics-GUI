from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PyQt5.QtGui import QPixmap, QFont
from PyQt5.QtCore import Qt

# Constants
FONT_TITLE = QFont("Cascadia Mono", 36, QFont.Weight.Bold)
FONT_SUBTITLE = QFont("Josefin Sans", 16, QFont.Weight.DemiBold)
FONT_BUTTON = QFont("Cascadia Mono", 22, QFont.Weight.Bold)

class SplashScreen(QWidget):
    def __init__(self, on_begin_callback=None):
        super().__init__()
        self.setWindowTitle("Anubis Forensics")
        self.setFixedSize(1200, 900)
        self.setStyleSheet("background-color: #0d1117;")
        self.on_begin_callback = on_begin_callback

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        logo = QLabel(self)
        pixmap = QPixmap("assets/4x/logoAsset 21@4x.png")
        if not pixmap.isNull():
            scaled = pixmap.scaled(1500, 1500, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo.setPixmap(scaled)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Anubis")
        title.setFont(FONT_TITLE)
        title.setStyleSheet("color: white;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel("FORENSICS")
        subtitle.setFont(FONT_SUBTITLE)
        subtitle.setStyleSheet("color: #999999; letter-spacing: 2px;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        begin_button = QPushButton("Begin")
        begin_button.setFont(FONT_BUTTON)
        begin_button.setStyleSheet("""
            QPushButton {
                background-color: #F57C1F;
                color: white;
                border-radius: 12px;
                padding: 16px 60px;
                margin-top: 40px;
            }
            QPushButton:hover {
                background-color: #FF8C42;
            }
        """)
        begin_button.clicked.connect(self.begin_clicked)

        layout.addWidget(logo)
        layout.addSpacing(30)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(40)
        layout.addWidget(begin_button, alignment=Qt.AlignmentFlag.AlignCenter)
        self.setLayout(layout)

    def begin_clicked(self):
        if self.on_begin_callback:
            self.on_begin_callback() 