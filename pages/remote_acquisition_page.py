from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QLineEdit, QTextEdit, QFormLayout, QComboBox, 
    QDateEdit, QSpinBox, QToolButton, QGridLayout, QFileDialog,
    QGroupBox, QCheckBox, QRadioButton, QButtonGroup
)
from PyQt5.QtGui import QPixmap, QFont, QIcon
from PyQt5.QtCore import Qt, pyqtSignal, QDate, QSize
from .base_page import BasePage, COLOR_ORANGE, COLOR_DARK, COLOR_GRAY, TAB_NAMES

# Constants
FONT_LABEL = QFont("Cascadia Mono", 13,)
FONT_CARD = QFont("Cascadia Mono", 18, QFont.Weight.ExtraBold)
FONT_GROUP = QFont("Cascadia Mono", 16, QFont.Weight.Bold)
FONT_SECTION = QFont("Cascadia Mono", 20, QFont.Weight.ExtraBold)

class RemoteAcquisitionPage(BasePage):
    back_requested = pyqtSignal()
    connect_requested = pyqtSignal(dict)  # New signal for connection request

    def __init__(self):
        super().__init__()
        self.setup_page_content()

    def setup_page_content(self):
        """Setup the page-specific content for the remote acquisition page"""
        # Add tab bar
        self.main_layout.addLayout(self._setup_tab_bar(TAB_NAMES))
        self.main_layout.addSpacing(40)

        # Create scrollable content container
        content_container = QWidget()
        content_container.setStyleSheet("""
            QWidget {
                background-color: white;
                border-radius: 24px;
            }
        """)
        content_container.setFixedSize(1500, 600)

        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(40, 32, 40, 32)
        content_layout.setSpacing(18)

        # NEW AGENT section
        section1 = QLabel("NEW AGENT")
        section1.setFont(FONT_SECTION)
        section1.setStyleSheet(f"color: {COLOR_DARK}; margin-bottom: 2px;")
        content_layout.addWidget(section1, alignment=Qt.AlignmentFlag.AlignLeft)

        grid1 = QGridLayout()
        grid1.setHorizontalSpacing(32)
        grid1.setVerticalSpacing(10)

        name_label = QLabel("Name")
        name_label.setFont(FONT_LABEL)
        grid1.addWidget(name_label, 0, 0)
        self.agent_name_input = self.create_styled_input()
        grid1.addWidget(self.agent_name_input, 1, 0)

        location_label = QLabel("Agant Location on your machine")
        location_label.setFont(FONT_LABEL)
        grid1.addWidget(location_label, 0, 1)
        
        location_field = QWidget()
        location_field_layout = QHBoxLayout(location_field)
        location_field_layout.setContentsMargins(0, 0, 0, 0)
        location_field_layout.setSpacing(0)
        self.agent_location_input = self.create_styled_input()
        self.agent_location_button = self.create_folder_button(self._choose_agent_location, 48)
        location_field_layout.addWidget(self.agent_location_input)
        location_field_layout.addWidget(self.agent_location_button)
        grid1.addWidget(location_field, 1, 1)

        content_layout.addLayout(grid1)
        content_layout.addSpacing(10)

        # TARGET MACHINE section
        section2 = QLabel("TARGET MACHINE")
        section2.setFont(FONT_SECTION)
        section2.setStyleSheet(f"color: {COLOR_DARK}; margin-bottom: 2px;")
        content_layout.addWidget(section2, alignment=Qt.AlignmentFlag.AlignLeft)

        grid2 = QGridLayout()
        grid2.setHorizontalSpacing(32)
        grid2.setVerticalSpacing(10)

        ip_label = QLabel("IP address")
        ip_label.setFont(FONT_LABEL)
        grid2.addWidget(ip_label, 0, 0)
        self.ip_input = self.create_styled_input()
        grid2.addWidget(self.ip_input, 1, 0)

        domain_label = QLabel("Domain")
        domain_label.setFont(FONT_LABEL)
        grid2.addWidget(domain_label, 0, 1)
        self.domain_input = self.create_styled_input()
        grid2.addWidget(self.domain_input, 1, 1)

        content_layout.addLayout(grid2)
        content_layout.addSpacing(10)

        # Credentials section
        section3 = QLabel("Credentials")
        section3.setFont(FONT_SECTION)
        section3.setStyleSheet(f"color: {COLOR_DARK}; margin-bottom: 2px;")
        content_layout.addWidget(section3, alignment=Qt.AlignmentFlag.AlignLeft)

        grid3 = QGridLayout()
        grid3.setHorizontalSpacing(32)
        grid3.setVerticalSpacing(10)

        user_label = QLabel("User name")
        user_label.setFont(FONT_LABEL)
        grid3.addWidget(user_label, 0, 0)
        self.username_input = self.create_styled_input()
        grid3.addWidget(self.username_input, 1, 0)

        password_label = QLabel("Password")
        password_label.setFont(FONT_LABEL)
        grid3.addWidget(password_label, 0, 1)
        self.password_input = self.create_styled_input(is_password=True)
        grid3.addWidget(self.password_input, 1, 1)

        content_layout.addLayout(grid3)
        content_layout.addSpacing(10)

        self.main_layout.addWidget(content_container, alignment=Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addSpacing(24)

        # Connect button
        connect_button = self.create_styled_button("Connect", self._handle_connect)
        self.main_layout.addWidget(connect_button, alignment=Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addSpacing(20)
        
        # Back button
        back_button = self.create_styled_button("Back", self._handle_back_click, COLOR_DARK, "white")
        self.main_layout.addWidget(back_button, alignment=Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addStretch()

    def _create_group_box(self, title):
        """Create a styled group box"""
        group = QGroupBox(title)
        group.setFont(FONT_GROUP)
        group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                color: {COLOR_DARK};
                border: 2px solid #e0e0e0;
                border-radius: 12px;
                margin-top: 12px;
                padding-top: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 16px;
                padding: 0 8px 0 8px;
            }}
        """)
        return group

    def _choose_agent_location(self):
        """Choose agent location"""
        directory = QFileDialog.getExistingDirectory(self, "Select Agent Location")
        if directory:
            self.agent_location_input.setText(directory)

    def _handle_connect(self):
        """Handle connect button click"""
        # Collect all connection parameters
        connection_params = {
            'agent_name': self.agent_name_input.text().strip(),
            'agent_location': self.agent_location_input.text().strip(),
            'ip_address': self.ip_input.text().strip(),
            'domain': self.domain_input.text().strip(),
            'username': self.username_input.text().strip(),
            'password': self.password_input.text()
        }
        
        # Validate required fields with visual feedback
        missing_fields = []
        
        if not connection_params['agent_name']:
            missing_fields.append("Agent name")
            self.agent_name_input.setStyleSheet(self.get_input_style().replace("border: 2.5px solid #23292f;", "border: 2px solid #d32f2f; background-color: #ffebee;"))
        else:
            self.agent_name_input.setStyleSheet(self.get_input_style())
            
        if not connection_params['ip_address']:
            missing_fields.append("IP address")
            self.ip_input.setStyleSheet(self.get_input_style().replace("border: 2.5px solid #23292f;", "border: 2px solid #d32f2f; background-color: #ffebee;"))
        else:
            self.ip_input.setStyleSheet(self.get_input_style())
            
        if not connection_params['username']:
            missing_fields.append("Username")
            self.username_input.setStyleSheet(self.get_input_style().replace("border: 2.5px solid #23292f;", "border: 2px solid #d32f2f; background-color: #ffebee;"))
        else:
            self.username_input.setStyleSheet(self.get_input_style())
            
        if not connection_params['password']:
            missing_fields.append("Password")
            self.password_input.setStyleSheet(self.get_input_style().replace("border: 2.5px solid #23292f;", "border: 2px solid #d32f2f; background-color: #ffebee;"))
        else:
            self.password_input.setStyleSheet(self.get_input_style())
        
        if missing_fields:
            print(f"Error: The following fields are required: {', '.join(missing_fields)}")
            return
            
        # Emit signal with connection parameters
        print("Connecting with parameters:", {k: v if k != 'password' else '***' for k, v in connection_params.items()})
        self.connect_requested.emit(connection_params)

    def _handle_back_click(self):
        """Handle back button click"""
        self.back_requested.emit()

    def _handle_tab_click(self, clicked_button):
        """Handle tab button clicks"""
        tab_text = clicked_button.text()
        super()._handle_tab_click(clicked_button) 