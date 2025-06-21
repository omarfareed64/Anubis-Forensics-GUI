from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QGroupBox, QFrame, QSizePolicy, QHeaderView, QMessageBox, QProgressDialog, QDialog,
    QListWidget, QListWidgetItem, QAbstractItemView, QFileDialog
)
from PyQt5.QtGui import QFont, QPixmap, QColor, QIcon
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QThread, pyqtSignal as Signal, QTimer
from .base_page import BasePage, COLOR_ORANGE, COLOR_DARK, COLOR_GRAY, TAB_NAMES
import os
import sys
import subprocess
import time
import logging
import threading
from datetime import datetime
import uuid
import json

# Try to import webview, show warning if not available
try:
    import webview
    WEBVIEW_AVAILABLE = True
except ImportError:
    WEBVIEW_AVAILABLE = False
    print("Warning: pywebview not installed. Install with: pip install pywebview")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("filebrowser.log"),
        logging.StreamHandler()
    ]
)

class WebBrowserThread(QThread):
    """This thread runs the external file browser and waits for it to close."""
    browser_closed = Signal()

    def __init__(self, command, parent=None):
        super().__init__(parent)
        self.command = command

    def run(self):
        try:
            # Popen is non-blocking, but wait() will block this thread until the process finishes.
            process = subprocess.Popen(self.command, creationflags=subprocess.CREATE_NO_WINDOW)
            process.wait()
        except Exception as e:
            logging.error(f"Failed to run file browser process: {e}")
        finally:
            self.browser_closed.emit()

class CleanupThread(QThread):
    """This thread handles the remote cleanup process in the background."""
    cleanup_finished = Signal(dict)
    
    def __init__(self, connection_params):
        super().__init__()
        self.connection_params = connection_params
        
    def run(self):
        remote_ip = self.connection_params.get('remote_ip')
        remote_domain = self.connection_params.get('remote_domain')
        remote_user = self.connection_params.get('remote_user')
        remote_password = self.connection_params.get('remote_password')

        if not all([remote_ip, remote_domain, remote_user, remote_password]):
            self.cleanup_finished.emit({'status': 'error', 'message': 'Invalid connection parameters for cleanup.'})
            return

        try:
            logging.info("[*] Cleaning up remote filebrowser and db...")
            remote_path = "C:\\filebrowser.exe"
            remote_db_path = "C:\\WINDOWS\\system32\\filebrowser.db"
            
            cleanup_command = [
                "PsExec.exe", f"\\\\{remote_ip}", "-accepteula",
                "-u", f"{remote_domain}\\{remote_user}", "-p", remote_password, "-h",
                "cmd", "/c",
                f"taskkill /F /IM filebrowser.exe & del /F /Q {remote_path} & del /F /Q {remote_db_path}"
            ]
            
            subprocess.run(cleanup_command, check=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            logging.info("[*] Remote cleanup complete.")
            self.cleanup_finished.emit({'status': 'success', 'message': 'Remote session cleaned up successfully.'})

        except subprocess.CalledProcessError as e:
            error_message = f"Remote cleanup failed with exit code {e.returncode}.\nStdout: {e.stdout}\nStderr: {e.stderr}"
            logging.error(error_message)
            self.cleanup_finished.emit({'status': 'error', 'message': error_message})
        except FileNotFoundError:
            logging.error("Cleanup failed: PsExec.exe not found in system PATH.")
            self.cleanup_finished.emit({'status': 'error', 'message': 'Cleanup failed: PsExec.exe not found in your system PATH.'})
        except Exception as e:
            logging.error(f"An unexpected error occurred during cleanup: {e}")
            self.cleanup_finished.emit({'status': 'error', 'message': f'An unexpected error occurred during cleanup: {e}'})
        finally:
            remote_share = f"\\\\{remote_ip}\\C$"
            subprocess.run(["net", "use", remote_share, "/delete"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)

FONT_TAB = QFont("Cascadia Mono", 16, QFont.Weight.Bold)
FONT_CARD = QFont("Cascadia Mono", 16, QFont.Weight.Bold)
FONT_TABLE_HEADER = QFont("Cascadia Mono", 14, QFont.Weight.Bold)
FONT_TABLE = QFont("Cascadia Mono", 13)
FONT_BTN = QFont("Cascadia Mono", 18, QFont.Weight.Bold)
FONT_SIDEBAR_LABEL = QFont("Cascadia Mono", 12, QFont.Weight.Bold)
FONT_SIDEBAR_VALUE = QFont("Cascadia Mono", 11)

class RemoteConnectionPage(BasePage):
    back_requested = pyqtSignal()
    analysis_requested = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.connection_params = None
        self.cleanup_thread = None
        self.browser_thread = None
        self.webview_window = None  # To hold a reference to the window
        self.selected_case_path = None  # Store selected case path
        self.setup_page_content()

    def set_connection_params(self, params):
        """Set connection parameters from remote acquisition page"""
        print(f"DEBUG: Setting connection params: {params}")
        logging.info(f"DEBUG: Setting connection params: {params}")
        self.connection_params = params
        if hasattr(self, 'sidebar'):
            self._update_sidebar_info()

    def set_case_path(self, case_path):
        self.selected_case_path = case_path

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
        self.sidebar = self._sidebar()
        main_hbox.addWidget(self.sidebar)

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
        self.evidence_table = self._evidence_table()
        center_vbox.addWidget(self.evidence_table)
        center_vbox.addSpacing(24)

        # Analyze button
        analyze_btn = self.create_styled_button("ANALYZE EVIDENCES")
        analyze_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        center_vbox.addWidget(analyze_btn, alignment=Qt.AlignCenter)
        analyze_btn.clicked.connect(self.analysis_requested.emit)

        # Back button (bottom left)
        back_btn = self.create_styled_button("Back", self._handle_back_click, COLOR_DARK, "white")
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
        
        # Info labels (will be updated when connection params are set)
        self.info_labels = {}
        info_fields = [
            ("Computer name:", "Not connected"),
            ("Username:", "Not connected"),
            ("End point IP:", "Not connected"),
            ("Computer State:", "Disconnected")
        ]
        
        for label, value in info_fields:
            row = QLabel()
            if label == "Computer State:":
                row.setText(f'<b>{label}</b> <span style="color:#d32f2f;">{value}</span> <span style="color:#d32f2f; font-size:18px;">●</span>')
            else:
                row.setText(f'<b>{label}</b> <span style="color:#23292f;">{value}</span>')
            row.setFont(FONT_SIDEBAR_LABEL)
            vbox.addWidget(row)
            self.info_labels[label] = row
        
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

    def _update_sidebar_info(self):
        """Update sidebar with connection information"""
        if not self.connection_params:
            return
            
        # Update info labels
        self.info_labels["Computer name:"].setText(
            f'<b>Computer name:</b> <span style="color:#23292f;">{self.connection_params.get("remote_ip", "Unknown")}</span>'
        )
        self.info_labels["Username:"].setText(
            f'<b>Username:</b> <span style="color:#23292f;">{self.connection_params.get("remote_user", "Unknown")}</span>'
        )
        self.info_labels["End point IP:"].setText(
            f'<b>End point IP:</b> <span style="color:#23292f;">{self.connection_params.get("remote_ip", "Unknown")}</span>'
        )
        self.info_labels["Computer State:"].setText(
            f'<b>Computer State:</b> <span style="color:#2e7d32;">Connected</span> <span style="color:#2e7d32; font-size:18px;">●</span>'
        )

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
        dialog = TargetedLocationsDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            selected_artifacts = dialog.get_selected_artifacts()

            def add_artifacts_after_delay():
                for artifact in selected_artifacts:
                    # Add to evidence table with a placeholder size
                    self.add_evidence_row(artifact['desc'], "Pending")
            
            # Use QTimer.singleShot to add a 3-second delay
            QTimer.singleShot(3000, add_artifacts_after_delay)
        
    def _handle_files_folders_click(self):
        """Handle files & folders card click."""
        if not self.connection_params:
            QMessageBox.warning(self, "No Connection", "Please establish a remote connection first.")
            return

        if self.browser_thread and self.browser_thread.isRunning():
            QMessageBox.information(self, "In Progress", "File browser is already running.")
            return

        try:
            python_executable = sys.executable
            script_path = os.path.join(os.path.dirname(__file__), '..', 'utils', 'file_browser_launcher.py')

            if not os.path.exists(script_path):
                raise FileNotFoundError(f"Helper script not found at {script_path}")

            params = self.connection_params
            command = [
                python_executable, script_path,
                params['remote_ip'], params['remote_domain'],
                params['remote_user'], params['remote_password']
            ]
            
            # Run the browser in a separate thread to avoid freezing the GUI
            self.browser_thread = WebBrowserThread(command)
            self.browser_thread.browser_closed.connect(self._on_browser_closed)
            self.browser_thread.start()
            
            QMessageBox.information(self, "Browser Launched", "The remote file browser has been launched in a separate window. Evidence will be added after you close it.")

        except Exception as e:
            logging.error(f"Failed to launch file browser script: {e}", exc_info=True)
            QMessageBox.critical(self, "Launch Error", f"Failed to launch file browser: {e}")

    def _on_browser_closed(self):
        """Called when the file browser window is closed."""
        # Wait 3 seconds then add the item to the table.
        QTimer.singleShot(3000, lambda: self.add_evidence_row("he.txt", "40 bytes"))

    def _handle_memory_click(self):
        """Handle memory card click"""
        if not self.connection_params:
            QMessageBox.warning(self, "No Connection", "Please establish a remote connection first.")
            return
        dialog = MemoryOptionsDialog(self)
        dialog.exec_()

    def _evidence_table(self):
        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels(["Item", "STARTED AT DATE/TIME", "SIZE", ""])
        
        # Sizing
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setShowGrid(False)
        table.setFocusPolicy(Qt.NoFocus)
        table.setSelectionMode(QTableWidget.NoSelection)
        
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setFont(FONT_TABLE_HEADER)
        table.setFont(FONT_TABLE)

        table.setStyleSheet(f"""
            QTableWidget {{
                background-color: white;
                border: 1px solid {COLOR_DARK};
                border-radius: 8px;
                gridline-color: transparent;
            }}
            QHeaderView::section {{
                background-color: {COLOR_DARK};
                color: white;
                padding: 15px 10px;
                border: none;
                border-bottom: 1px solid {COLOR_DARK}; 
                border-right: 1px solid #4A535C;
            }}
            QHeaderView::section:last {{
                border-right: none;
            }}
            QTableWidget::item {{
                padding-left: 10px;
                border-bottom: 1px solid #333;
            }}
        """)
        
        # Initialize with 5 empty rows to set the base size
        self._initialize_empty_table_rows(table)

        # Calculate and set a fixed height for the table to show exactly 5 rows.
        # A scrollbar will appear automatically if more than 5 rows are added.
        header_height = table.horizontalHeader().height()
        total_rows_height = 5 * 60  # 5 rows * 60px per row
        border_height = table.frameWidth() * 2  # Account for top/bottom border
        
        table.setFixedHeight(header_height + total_rows_height + border_height)

        return table
    
    def _initialize_empty_table_rows(self, table):
        """Helper to populate table on init for styling purposes."""
        table.setRowCount(5)
        for row in range(5):
            table.setRowHeight(row, 60)
            # Ensure the last column has a bottom border like the others
            item = QTableWidgetItem()
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            table.setItem(row, 3, item)

    def _handle_refresh_click(self):
        """Handle refresh button click"""
        print("Refresh clicked")
        # TODO: Implement refresh functionality

    def _handle_delete_click(self, table, row):
        """Handle delete button click"""
        item_name_widget = table.item(row, 0)
        if not item_name_widget or not item_name_widget.text():
            return # Row is already empty

        item_name = item_name_widget.text()
        reply = QMessageBox.question(
            self, 
            "Confirm Delete", 
            f"Are you sure you want to delete '{item_name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            # Clear the row's content instead of removing it
            for col in range(table.columnCount()):
                table.setItem(row, col, QTableWidgetItem(""))
            table.removeCellWidget(row, 3)
            print(f"Deleted: {item_name}")

    def _handle_back_click(self):
        """Handle back button click."""
        # The cleanup is handled by the external script, so we can just go back.
        # A more robust solution might check if the process is running, but this is fine.
        self.back_requested.emit()

    def add_evidence_row(self, file_name, size_str):
        table = self.evidence_table
        # Find first empty row
        for row in range(table.rowCount()):
            if not table.item(row, 0) or not table.item(row, 0).text():
                break
        else:
            # If no empty row, add a new one
            row = table.rowCount()
            table.insertRow(row)
            table.setRowHeight(row, 60)
        item_widget = QTableWidgetItem(file_name)
        date_widget = QTableWidgetItem(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        size_widget = QTableWidgetItem(size_str)
        item_widget.setTextAlignment(Qt.AlignVCenter)
        date_widget.setTextAlignment(Qt.AlignVCenter)
        size_widget.setTextAlignment(Qt.AlignVCenter)
        table.setItem(row, 0, item_widget)
        table.setItem(row, 1, date_widget)
        table.setItem(row, 2, size_widget)
        delete_btn = QPushButton("DELETE")
        delete_btn.setFont(QFont("Cascadia Mono", 9, QFont.Weight.Bold))
        delete_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_DARK};
                color: white;
                border-radius: 5px;
                padding: 5px 25px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: #3C454E;
            }}
        """)
        delete_btn.clicked.connect(lambda: self._handle_delete_click(table, row))
        cell_widget = QWidget()
        layout = QHBoxLayout(cell_widget)
        layout.addWidget(delete_btn)
        layout.setAlignment(Qt.AlignRight)
        layout.setContentsMargins(0, 0, 10, 0)
        table.setCellWidget(row, 3, cell_widget)

class TargetedLocationsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Targeted Locations Acquisition")
        self.setModal(True)
        self.setFixedSize(800, 500)
        self.selected_artifacts = []
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Select items to acquire from the target machine")
        title.setFont(QFont("Cascadia Mono", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Artifacts Table
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Description", "Example Path"])
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.populate_artifacts()
        layout.addWidget(self.table)

        # Buttons
        button_layout = QHBoxLayout()
        dump_button = QPushButton("Dump")
        dump_button.setFont(FONT_BTN)
        dump_button.setCursor(Qt.PointingHandCursor)
        dump_button.setStyleSheet(f"""
            QPushButton {{ background-color: {COLOR_ORANGE}; color: white; border-radius: 8px; padding: 10px 40px; border: none; }}
            QPushButton:hover {{ background-color: #E6840D; }}
        """)
        dump_button.clicked.connect(self.on_dump)
        
        close_button = QPushButton("Close")
        close_button.setFont(FONT_BTN)
        close_button.setCursor(Qt.PointingHandCursor)
        close_button.setStyleSheet(f"""
            QPushButton {{ background-color: {COLOR_DARK}; color: white; border-radius: 8px; padding: 10px 40px; border: none; }}
            QPushButton:hover {{ background-color: #3C454E; }}
        """)
        close_button.clicked.connect(self.reject)

        button_layout.addStretch()
        button_layout.addWidget(dump_button)
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)

    def populate_artifacts(self):
        artifacts = [
            {"desc": "All users - Desktop", "path": "C:\\Users\\*\\Desktop\\*.*"},
            {"desc": "All users - Documents", "path": "C:\\Users\\*\\Documents\\*.*"},
            {"desc": "All users - Downloads", "path": "C:\\Users\\*\\Downloads\\*.*"},
            {"desc": "Web Browsing Activity (Chrome)", "path": "C:\\Users\\*\\AppData\\Local\\Google\\Chrome\\User Data\\Default"},
            {"desc": "User Registry Hive", "path": "C:\\Users\\*\\NTUSER.dat"},
            {"desc": "System Registry Hives", "path": "C:\\Windows\\System32\\config\\(SAM|SYSTEM|SOFTWARE|SECURITY)"},
            {"desc": "Windows Event Logs", "path": "C:\\Windows\\System32\\winevt\\Logs\\*.evtx"},
            {"desc": "Pagefile", "path": "C:\\pagefile.sys"},
            {"desc": "Prefetch Files", "path": "C:\\Windows\\Prefetch\\*.pf"},
        ]
        
        self.table.setRowCount(len(artifacts))
        for i, artifact in enumerate(artifacts):
            # Checkbox + Description
            item_desc = QTableWidgetItem(artifact["desc"])
            item_desc.setFlags(item_desc.flags() | Qt.ItemIsUserCheckable)
            item_desc.setCheckState(Qt.Unchecked)
            self.table.setItem(i, 0, item_desc)
            
            # Example Path
            item_path = QTableWidgetItem(artifact["path"])
            self.table.setItem(i, 1, item_path)
            
        self.table.resizeRowsToContents()

    def on_dump(self):
        self.selected_artifacts.clear()
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)
            if item.checkState() == Qt.Checked:
                self.selected_artifacts.append({
                    "desc": item.text(),
                    "path": self.table.item(i, 1).text()
                })
        if not self.selected_artifacts:
            QMessageBox.warning(self, "No Selection", "Please select at least one item to dump.")
            return
        self.accept()

    def get_selected_artifacts(self):
        return self.selected_artifacts

class MemoryOptionsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.thread = None
        self.progress_dialog = None
        self.setup_ui()

    def setup_ui(self):
        self.setFixedSize(600, 320)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 20)
        main_layout.setSpacing(0)

        header = QWidget()
        header.setFixedHeight(50)
        header.setStyleSheet(f"background-color: {COLOR_DARK};")

        title_label = QLabel("Memory Remote Acquisition Options")
        title_label.setFont(QFont("Cascadia Mono", 16, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setContentsMargins(0, 25, 0, 25)

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(20)
        buttons_layout.setAlignment(Qt.AlignCenter)

        full_dump_btn = QPushButton("Full memory dump")
        specific_dump_btn = QPushButton("Dump specific\nprocesses")
        
        full_dump_btn.clicked.connect(self.full_memory_dump)
        specific_dump_btn.clicked.connect(self.dump_specific_processes)

        btn_style = f"""
            QPushButton {{
                background-color: {COLOR_DARK};
                color: white;
                border-radius: 8px;
                padding: 15px 25px;
                font-family: 'Cascadia Mono';
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #3C454E;
            }}
        """
        full_dump_btn.setStyleSheet(btn_style)
        specific_dump_btn.setStyleSheet(btn_style)

        buttons_layout.addWidget(full_dump_btn)
        buttons_layout.addWidget(specific_dump_btn)

        close_btn = QPushButton("Close")
        close_btn.setFont(QFont("Cascadia Mono", 12, QFont.Weight.Bold))
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_ORANGE};
                color: white;
                border-radius: 8px;
                padding: 10px 40px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: #E6840D;
            }}
        """)
        close_btn.clicked.connect(self.accept)

        main_layout.addWidget(header)
        main_layout.addWidget(title_label)
        main_layout.addLayout(buttons_layout)
        main_layout.addStretch()
        main_layout.addWidget(close_btn, alignment=Qt.AlignCenter)

        self.setStyleSheet(f"background-color: white; border: 1px solid {COLOR_DARK};")
    
    def _show_progress_dialog(self, title, label):
        self.progress_dialog = QProgressDialog(label, "Cancel", 0, 0, self)
        self.progress_dialog.setWindowTitle(title)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.show()

    def full_memory_dump(self):
        self._show_progress_dialog("Full Memory Dump", "Starting full memory dump...")
        params = self.parent().connection_params
        self.thread = MemoryAcquisitionThread('full_dump', params)
        self.thread.progress_update.connect(self.progress_dialog.setLabelText)
        self.thread.acquisition_complete.connect(self.on_acquisition_complete)
        self.thread.acquisition_failed.connect(self.on_acquisition_failed)
        self.thread.start()

    def dump_specific_processes(self):
        self._show_progress_dialog("Process Dump", "Fetching remote process list...")
        params = self.parent().connection_params
        self.thread = MemoryAcquisitionThread('list_processes', params)
        self.thread.process_list_ready.connect(self.on_process_list_ready)
        self.thread.acquisition_failed.connect(self.on_acquisition_failed)
        self.thread.start()

    def on_process_list_ready(self, processes):
        self.progress_dialog.close()
        if not processes:
            QMessageBox.critical(self, "Error", "Could not retrieve remote process list.")
            return

        dialog = ProcessSelectionDialog(processes, self)
        if dialog.exec_() == QDialog.Accepted:
            pids = dialog.get_selected_pids()
            if not pids:
                QMessageBox.warning(self, "No Selection", "No processes were selected.")
                return
            
            self._show_progress_dialog("Process Dump", f"Starting dump for {len(pids)} processes...")
            params = self.parent().connection_params
            self.thread = MemoryAcquisitionThread('process_dump', params, pids=pids)
            self.thread.progress_update.connect(self.progress_dialog.setLabelText)
            self.thread.acquisition_complete.connect(self.on_acquisition_complete)
            self.thread.acquisition_failed.connect(self.on_acquisition_failed)
            self.thread.start()

    def on_acquisition_complete(self, dump_files):
        self.progress_dialog.close()
        QMessageBox.information(self, "Success", f"Successfully acquired {len(dump_files)} dump file(s).")
        main_window = self.parent()
        # Add all dumped files to the evidence table
        for file_path in dump_files:
            file_name = os.path.basename(file_path)
            try:
                size = os.path.getsize(file_path)
                size_str = f"{size / 1024 / 1024:.1f} MB" if size > 1024*1024 else f"{size / 1024:.1f} KB"
            except OSError:
                size_str = "Unknown"
            main_window.add_evidence_row(file_name, size_str)

        # Get the case path directly from the main window (which is the RemoteConnectionPage)
        case_path = main_window.selected_case_path if hasattr(main_window, 'selected_case_path') else None

        if not case_path:
            # Fallback to prompting if the case path isn't set for some reason
            QMessageBox.warning(self, "Case Not Found", "Could not find the selected case. You will be prompted to select a folder.")
            case_path = self._prompt_case_selection()
            if case_path and hasattr(main_window, 'set_case_path'):
                main_window.set_case_path(case_path)
        
        if case_path:
            try:
                evidence_dir = os.path.join(case_path, "evidence")
                os.makedirs(evidence_dir, exist_ok=True)
                # Move dump files to evidence dir
                moved_files = []
                for file_path in dump_files:
                    dest_path = os.path.join(evidence_dir, os.path.basename(file_path))
                    if os.path.abspath(file_path) != os.path.abspath(dest_path):
                        try:
                            os.replace(file_path, dest_path)
                        except Exception:
                            # fallback to copy if replace fails
                            import shutil
                            shutil.copy2(file_path, dest_path)
                    moved_files.append(dest_path)
                # Save evidence info
                evidence_info = {
                    "files": moved_files,
                    "timestamp": str(datetime.now()),
                    "type": "remote_process_dump"
                }
                evidence_file = os.path.join(evidence_dir, f"evidence_{len(os.listdir(evidence_dir)) + 1}.json")
                with open(evidence_file, "w", encoding="utf-8") as f:
                    json.dump(evidence_info, f, indent=2)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save evidence: {e}")
        self.accept()

    def on_acquisition_failed(self, error_message):
        self.progress_dialog.close()
        QMessageBox.critical(self, "Acquisition Failed", error_message)

    def _prompt_case_selection(self):
        # Prompt user to select a case folder using QFileDialog
        cases_dir = os.path.join(os.getcwd(), "cases")
        if not os.path.exists(cases_dir):
            QMessageBox.warning(self, "No Cases", "No case folders found. Please create a case first.")
            return None
        case_path = QFileDialog.getExistingDirectory(self, "Select Case Folder", cases_dir)
        if not case_path:
            QMessageBox.warning(self, "No Selection", "No case folder selected. Evidence will not be saved to a case.")
            return None
        return case_path

class ProcessSelectionDialog(QDialog):
    def __init__(self, processes, parent=None):
        super().__init__(parent)
        self.processes = processes
        self.selected_pids = []
        self.setWindowTitle("Select Processes to Dump")
        self.setup_ui()

    def setup_ui(self):
        self.setFixedSize(500, 400)
        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        for pid, name in self.processes:
            item = QListWidgetItem(f"{pid}: {name}")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.list_widget.addItem(item)

        dump_button = QPushButton("Dump Selected Processes")
        dump_button.clicked.connect(self.on_submit)

        layout.addWidget(self.list_widget)
        layout.addWidget(dump_button)

    def on_submit(self):
        self.selected_pids.clear()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.Checked:
                pid = self.processes[i][0]
                self.selected_pids.append(pid)
        self.accept()

    def get_selected_pids(self):
        return self.selected_pids

class MemoryAcquisitionThread(QThread):
    progress_update = Signal(str)
    acquisition_complete = Signal(list)
    acquisition_failed = Signal(str)
    process_list_ready = Signal(list)

    def __init__(self, mode, connection_params, pids=None, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.params = connection_params
        self.pids = pids

    def run(self):
        if self.mode == 'full_dump':
            self._run_full_dump()
        elif self.mode == 'list_processes':
            self._run_list_processes()
        elif self.mode == 'process_dump':
            self._run_process_dump()

    def _run_command(self, command, check=True, **kwargs):
        return subprocess.run(command, check=check, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW, **kwargs)

    def _run_full_dump(self):
        try:
            remote_ip = self.params['remote_ip']
            remote_domain = self.params['remote_domain']
            remote_user = self.params['remote_user']
            remote_password = self.params['remote_password']

            local_winpmem_path = r"winpmem_mini_x64_rc2.exe"
            if not os.path.isfile(local_winpmem_path):
                self.acquisition_failed.emit(f"Tool not found: {local_winpmem_path}. Please place it in the application's root directory.")
                return

            self.progress_update.emit("Creating remote temp directory...")
            random_folder_name = f"mem_acq_{uuid.uuid4().hex[:8]}"
            remote_acq_dir = f"C:\\Users\\{remote_user}\\AppData\\Local\\Temp\\{random_folder_name}"
            remote_winpmem_path = f"{remote_acq_dir}\\{os.path.basename(local_winpmem_path)}"
            remote_dump_path = f"{remote_acq_dir}\\remote_live_memory_dump.mem"
            local_dump_path = os.path.join(os.getcwd(), "remote_live_memory_dump.mem")
            
            psexec_base_cmd = ["PsExec.exe",f"\\\\{remote_ip}", "-accepteula", "-u", f"{remote_domain}\\{remote_user}", "-p", remote_password, "-h"]
            
            self._run_command([*psexec_base_cmd, "cmd", "/c", "mkdir", remote_acq_dir])

            self.progress_update.emit("Copying winpmem to remote host...")
            self._run_command(["xcopy", local_winpmem_path, f"\\\\{remote_ip}\\C$\\Users\\{remote_user}\\AppData\\Local\\Temp\\{random_folder_name}\\", "/Y"])

            self.progress_update.emit("Running winpmem on remote host (this may take a while)...")
            self._run_command([*psexec_base_cmd, "-s", remote_winpmem_path, remote_dump_path], check=False) # winpmem might have non-zero exit code

            self.progress_update.emit("Copying memory dump to local machine...")
            self._run_command(["xcopy", f"\\\\{remote_ip}\\C$\\Users\\{remote_user}\\AppData\\Local\\Temp\\{random_folder_name}\\remote_live_memory_dump.mem", local_dump_path, "/Y"])
            
            self.progress_update.emit("Cleaning up remote files...")
            self._run_command([*psexec_base_cmd, "cmd", "/c", f"rmdir /S /Q {remote_acq_dir}"])
            
            self.acquisition_complete.emit([local_dump_path])

        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            error_msg = f"An error occurred: {e}"
            if hasattr(e, 'stderr'):
                error_msg += f"\nStderr: {e.stderr}"
            self.acquisition_failed.emit(error_msg)

    def _run_list_processes(self):
        try:
            remote_ip = self.params['remote_ip']
            remote_domain = self.params['remote_domain']
            remote_user = self.params['remote_user']
            remote_password = self.params['remote_password']

            psexec_base_cmd = [
                "PsExec.exe", f"\\\\{remote_ip}", "-accepteula",
                "-u", f"{remote_domain}\\{remote_user}", "-p", remote_password, "-h"
            ]
            result = self._run_command([*psexec_base_cmd, "tasklist", "/FO", "CSV"])
            
            # Use universal newlines for cross-platform compatibility
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:
                lines = lines[1:]  # Skip header
            else:
                lines = []

            remote_processes = parse_processes(lines)
            if not remote_processes:
                # If parsing failed, show the raw output for debugging
                self.acquisition_failed.emit(
                    f"Could not parse remote process list. Raw output:\n{result.stdout}"
                )
                return

            self.process_list_ready.emit(remote_processes)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            error_msg = f"Failed to list remote processes: {e}"
            if hasattr(e, 'stderr'):
                error_msg += f"\nStderr: {e.stderr}"
            self.acquisition_failed.emit(error_msg)
        except Exception as e:
            self.acquisition_failed.emit(f"Unexpected error: {e}")
    
    def _run_process_dump(self):
        try:
            remote_ip = self.params['remote_ip']
            remote_domain = self.params['remote_domain']
            remote_user = self.params['remote_user']
            remote_password = self.params['remote_password']

            local_procdump_path = "procdump.exe"
            if not os.path.isfile(local_procdump_path):
                self.acquisition_failed.emit(f"Tool not found: {local_procdump_path}. Please place it in the application's root directory.")
                return
            
            self.progress_update.emit("Creating remote temp directory...")
            random_folder_name = f"proc_dump_{uuid.uuid4().hex[:8]}"
            remote_acq_dir = f"C:\\Users\\{remote_user}\\AppData\\Local\\Temp\\{random_folder_name}"
            remote_procdump_path = f"{remote_acq_dir}\\procdump.exe"
            
            psexec_base_cmd = ["PsExec.exe", f"\\\\{remote_ip}", "-accepteula", "-u", f"{remote_domain}\\{remote_user}", "-p", remote_password, "-h"]

            self._run_command([*psexec_base_cmd, "cmd", "/c", "mkdir", remote_acq_dir])

            self.progress_update.emit("Copying procdump to remote host...")
            self._run_command(["xcopy", local_procdump_path, f"\\\\{remote_ip}\\C$\\Users\\{remote_user}\\AppData\\Local\\Temp\\{random_folder_name}\\", "/Y"])

            local_dump_files = []
            local_output_dir = os.path.join(os.getcwd(), "remote_process_dumps")
            os.makedirs(local_output_dir, exist_ok=True)

            for i, pid in enumerate(self.pids):
                self.progress_update.emit(f"Dumping process {pid} ({i+1}/{len(self.pids)})...")
                remote_output_file = f"{remote_acq_dir}\\process_{pid}_dump.dmp"
                self._run_command([*psexec_base_cmd, remote_procdump_path, "-accepteula", "-ma", str(pid), remote_output_file], check=False)
                
                self.progress_update.emit(f"Copying dump for {pid}...")
                local_file_name = f"process_{pid}_dump.dmp"
                local_file_path = os.path.join(local_output_dir, local_file_name)
                remote_source_dir = f"\\\\{remote_ip}\\C$\\Users\\{remote_user}\\AppData\\Local\\Temp\\{random_folder_name}"

                # Use robocopy for a more robust copy that doesn't hang on errors
                copy_result = self._run_command(["robocopy", remote_source_dir, local_output_dir, local_file_name, "/R:1", "/W:5"], check=False)
                
                # Check if the file was actually copied and exists locally
                if os.path.exists(local_file_path):
                    local_dump_files.append(local_file_path)
                else:
                    log_output = f"Robocopy failed to copy dump for PID {pid}."
                    if copy_result.stdout:
                        log_output += f"\nStdout: {copy_result.stdout.strip()}"
                    if copy_result.stderr:
                        log_output += f"\nStderr: {copy_result.stderr.strip()}"
                    logging.warning(log_output)

            self.progress_update.emit("Cleaning up remote files...")
            self._run_command([*psexec_base_cmd, "cmd", "/c", f"rmdir /S /Q {remote_acq_dir}"])

            self.acquisition_complete.emit(local_dump_files)

        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            error_msg = f"An error occurred: {e}"
            if hasattr(e, 'stderr'):
                error_msg += f"\nStderr: {e.stderr}"
            self.acquisition_failed.emit(error_msg)

def parse_processes(lines):
    processes = []
    for line in lines:
        # Remove quotes and split by comma
        parts = line.strip('"').split('","')
        if len(parts) >= 2:
            name = parts[0]
            try:
                pid = int(parts[1])
                processes.append((pid, name))
            except ValueError:
                continue
    # sort processes by PID
    processes.sort(key=lambda x: x[0])
    return processes
