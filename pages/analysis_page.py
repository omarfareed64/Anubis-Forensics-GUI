import csv
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QComboBox, QGroupBox, QGridLayout,
    QStatusBar, QProgressBar, QFileDialog, QAction, QMenu, QApplication
)
from PyQt5.QtGui import QFont, QColor, QKeySequence
from PyQt5.QtCore import Qt, pyqtSignal, QThread, pyqtSignal as Signal, QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView
from .base_page import BasePage, COLOR_ORANGE, COLOR_DARK, COLOR_GRAY, TAB_NAMES
from services.web_artifact_extractor import extract_all_web_artifacts
from services.usb_analyzer import get_usb_devices
from datetime import datetime, timedelta

class WebArtifactThread(QThread):
    """Worker thread for extracting web artifacts."""
    finished = Signal(dict)

    def __init__(self, params, parent=None):
        super().__init__(parent)
        self.params = params

    def run(self):
        """Execute the extraction script."""
        result = extract_all_web_artifacts(
            remote_ip=self.params.get('remote_ip'),
            domain=self.params.get('remote_domain'),
            username=self.params.get('remote_user'),
            password=self.params.get('remote_password')
        )
        self.finished.emit(result)

class UsbDeviceThread(QThread):
    """Worker thread for scanning local USB device history."""
    finished = Signal(list)

    def run(self):
        """Execute the USB device scan."""
        devices = get_usb_devices()
        self.finished.emit(devices)

class AnalysisPage(BasePage):
    back_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.connection_params = None
        self.web_artifact_thread = None
        self.usb_device_thread = None
        self.usb_devices = [] # To store full list of devices
        self.displayed_usb_devices = [] # To store the currently visible list
        self.setup_page_content()
        self._select_tab_programmatically("Analyze Evidence")
        
        # Set default font for message boxes

    def set_connection_params(self, params):
        """Receive and store connection parameters."""
        self.connection_params = params

    def _switch_right_panel_view(self, view_to_show):
        """Manages visibility of widgets in the right panel."""
        self.web_view.setVisible(self.web_view == view_to_show)
        self.usb_view_container.setVisible(self.usb_view_container == view_to_show)
        self.placeholder_label.setVisible(self.placeholder_label == view_to_show)

    def setup_page_content(self):
        """Setup the page-specific content for the analysis page"""
        # Add tab bar
        self.main_layout.addLayout(self._setup_tab_bar(TAB_NAMES))
        self.main_layout.addSpacing(40)

        # Main content layout
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)
        content_layout.setContentsMargins(40, 0, 40, 20)

        # Left side (buttons)
        left_panel = QFrame()
        left_panel.setFixedWidth(250)
        left_panel.setStyleSheet("background-color: white; border-radius: 18px;")
        
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(20, 20, 20, 20)
        left_layout.setSpacing(15)
        left_layout.setAlignment(Qt.AlignTop)

        artifact_buttons = ["MEMORY", "WEB", "SRUM", "REGISTRY", "USB"]
        for artifact_name in artifact_buttons:
            button = QPushButton(artifact_name)
            button.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
            button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLOR_DARK};
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 12px;
                    text-align: center;
                }}
                QPushButton:hover {{
                    background-color: {COLOR_ORANGE};
                }}
            """)
            button.clicked.connect(lambda ch, name=artifact_name: self.on_artifact_button_click(name))
            left_layout.addWidget(button)
        
        content_layout.addWidget(left_panel)

        # Right side (display area)
        self.right_panel = QFrame()
        self.right_panel.setStyleSheet(f"background-color: white; border: 2px solid {COLOR_DARK}; border-radius: 18px;")
        
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(2, 2, 2, 2)

        # Web view for web artifacts
        self.web_view = QWebEngineView()
        right_layout.addWidget(self.web_view)

        # --- USB View Container ---
        self.usb_view_container = QWidget()
        self.usb_view_container.setStyleSheet("""
            QGroupBox {
                border: 1px solid #ccc;
                border-radius: 6px;
                margin-top: 10px;
                font-weight: bold;
                background-color: #f7f7f7;
                font-family: 'Segoe UI';
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 5px;
                font-family: 'Segoe UI';
            }
            QPushButton#exportButton { 
                background-color: #17a2b8; 
                font-family: 'Segoe UI';
            }
            QPushButton#exportButton:hover { background-color: #138496; }
            QPushButton#forensicButton { 
                background-color: #dc3545; 
                font-family: 'Segoe UI';
            }
            QPushButton#forensicButton:hover { background-color: #c82333; }
            QProgressBar {
                font-family: 'Segoe UI';
            }
        """)
        usb_layout = QVBoxLayout(self.usb_view_container)
        usb_layout.setContentsMargins(0, 0, 0, 0)
        usb_layout.setSpacing(10)

        # Controls Panel
        control_panel = QGroupBox("Controls")
        control_panel.setFont(QFont("Segoe UI", 9))
        control_layout = QGridLayout(control_panel)
        control_layout.setContentsMargins(15, 25, 15, 15)
        control_layout.setSpacing(10)
        
        self.usb_search_box = QLineEdit()
        self.usb_search_box.setPlaceholderText("Type to filter devices...")
        self.usb_search_box.setClearButtonEnabled(True)
        self.usb_search_box.setFont(QFont("Segoe UI", 9))
        self.usb_search_box.textChanged.connect(self.apply_usb_filters)

        self.usb_time_filter = QComboBox()
        self.usb_time_filter.addItems(["All Time", "Last 7 Days", "Last 30 Days", "Last 90 Days", "Last Year"])
        self.usb_time_filter.setFont(QFont("Segoe UI", 9))
        self.usb_time_filter.currentIndexChanged.connect(self.apply_usb_filters)
        
        self.export_button = QPushButton("Export to CSV")
        self.export_button.setObjectName("exportButton")
        self.export_button.setFont(QFont("Segoe UI", 9))
        self.export_button.clicked.connect(self.export_usb_csv)
        
        self.forensic_button = QPushButton("Forensic Analysis")
        self.forensic_button.setObjectName("forensicButton")
        self.forensic_button.setFont(QFont("Segoe UI", 9))
        self.forensic_button.clicked.connect(self.perform_forensic_analysis)

        search_label = QLabel("Search:")
        search_label.setFont(QFont("Segoe UI", 9))
        time_label = QLabel("Time Range:")
        time_label.setFont(QFont("Segoe UI", 9))
        
        control_layout.addWidget(search_label, 0, 0)
        control_layout.addWidget(self.usb_search_box, 0, 1)
        control_layout.addWidget(time_label, 0, 2)
        control_layout.addWidget(self.usb_time_filter, 0, 3)
        control_layout.addWidget(self.export_button, 1, 0, 1, 2)
        control_layout.addWidget(self.forensic_button, 1, 2, 1, 2)
        control_layout.setColumnStretch(1, 1)

        usb_layout.addWidget(control_panel)

        # USB Table
        self.usb_table_view = QTableWidget()
        self.usb_table_view.setSortingEnabled(True)
        self.usb_table_view.setAlternatingRowColors(True)
        self.usb_table_view.setSelectionBehavior(QTableWidget.SelectRows)
        self.usb_table_view.setEditTriggers(QTableWidget.NoEditTriggers)
        self.usb_table_view.verticalHeader().setVisible(False)
        self.usb_table_view.horizontalHeader().setStretchLastSection(True)
        self.usb_table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.usb_table_view.customContextMenuRequested.connect(self.show_usb_context_menu)
        self.usb_table_view.doubleClicked.connect(self.show_usb_device_details)
        self.usb_table_view.setFont(QFont("Segoe UI", 9))
        self.usb_table_view.horizontalHeader().setStyleSheet(f"""
            QHeaderView::section {{
                background-color: {COLOR_DARK};
                color: white;
                padding: 6px;
                font-weight: bold;
                font-family: 'Segoe UI';
            }}
        """)
        usb_layout.addWidget(self.usb_table_view, 1)

        # Status Bar
        self.usb_status_bar = QStatusBar()
        self.usb_status_bar.setSizeGripEnabled(False)
        self.usb_status_bar.setFont(QFont("Segoe UI", 9))
        self.usb_device_count_label = QLabel()
        self.usb_device_count_label.setFont(QFont("Segoe UI", 9))
        self.usb_status_bar.addPermanentWidget(self.usb_device_count_label)
        self.usb_progress_bar = QProgressBar()
        self.usb_progress_bar.setMaximumWidth(250)
        self.usb_progress_bar.setVisible(False)
        self.usb_progress_bar.setFont(QFont("Segoe UI", 9))
        self.usb_status_bar.addPermanentWidget(self.usb_progress_bar)
        usb_layout.addWidget(self.usb_status_bar)

        right_layout.addWidget(self.usb_view_container)

        # Placeholder label for messages
        self.placeholder_label = QLabel("Select an artifact to view details")
        self.placeholder_label.setFont(QFont("Segoe UI", 16))
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.placeholder_label.setStyleSheet("color: #aaa;")
        right_layout.addWidget(self.placeholder_label)

        content_layout.addWidget(self.right_panel, 1) # Stretch factor of 1

        self.main_layout.addLayout(content_layout, 1)

        self._switch_right_panel_view(self.placeholder_label) # Show placeholder initially

    def on_artifact_button_click(self, artifact_name):
        """Handle clicks on the artifact buttons."""
        self._switch_right_panel_view(self.placeholder_label)
        self.placeholder_label.setText(f"Gathering data for {artifact_name}...")

        if artifact_name == "WEB":
            if not self.connection_params:
                QMessageBox.warning(self, "Error", "Connection parameters not set for remote artifact extraction.")
                self.placeholder_label.setText("Select an artifact to view details")
                return

            self.web_artifact_thread = WebArtifactThread(self.connection_params)
            self.web_artifact_thread.finished.connect(self.on_web_extraction_finished)
            self.web_artifact_thread.start()
        
        elif artifact_name == "USB":
            self.usb_device_thread = UsbDeviceThread()
            self.usb_device_thread.finished.connect(self.on_usb_scan_finished)
            self.usb_device_thread.start()
        
        else:
             self.placeholder_label.setText(f"Analysis for {artifact_name} is not yet implemented.")

    def on_web_extraction_finished(self, result):
        """Handle finished signal from the web artifact extraction thread."""
        if result["status"] == "success":
            self._switch_right_panel_view(self.web_view)
            self.web_view.setUrl(QUrl.fromLocalFile(result["report_path"]))
        else:
            self._switch_right_panel_view(self.placeholder_label)
            self.placeholder_label.setText(f"Error: {result['message']}")
            QMessageBox.critical(self, "Extraction Failed", result['message'])

    def on_usb_scan_finished(self, devices):
        """Handles the finished signal from the USB device scan thread."""
        self.usb_progress_bar.setVisible(False)
        self.usb_status_bar.clearMessage()
        self.usb_devices = devices
        if not devices:
            self.placeholder_label.setText("No USB devices found or failed to read registry.")
            self._switch_right_panel_view(self.placeholder_label)
            return
        
        self.apply_usb_filters()
        self._switch_right_panel_view(self.usb_view_container)

    def apply_usb_filters(self):
        """Filters and displays USB devices based on search and time criteria."""
        if not self.usb_devices:
            return

        search_term = self.usb_search_box.text().lower()
        time_filter = self.usb_time_filter.currentText()
        
        now = datetime.utcnow()
        time_delta = None
        if time_filter == "Last 7 Days": time_delta = timedelta(days=7)
        elif time_filter == "Last 30 Days": time_delta = timedelta(days=30)
        elif time_filter == "Last 90 Days": time_delta = timedelta(days=90)
        elif time_filter == "Last Year": time_delta = timedelta(days=365)
        
        cutoff_time = now - time_delta if time_delta else None

        filtered_devices = []
        for device in self.usb_devices:
            # Time filter
            if cutoff_time and (not device.get("datetime_obj") or device["datetime_obj"] < cutoff_time):
                continue

            # Search filter
            if search_term:
                matches = False
                for value in device.values():
                    if search_term in str(value).lower():
                        matches = True
                        break
                if not matches:
                    continue
            
            filtered_devices.append(device)

        self.display_usb_data(filtered_devices)

    def display_usb_data(self, devices):
        """Populates the table with a list of USB devices."""
        self.displayed_usb_devices = devices # Store for the details view
        self.usb_status_bar.showMessage("Populating view...")
        self.usb_table_view.setSortingEnabled(False)
        self.usb_table_view.clear()
        
        headers = ["Forensic ID", "Description", "Hardware ID", "Plug-in Time", "Duration", "Manufacturer"]
        self.usb_table_view.setColumnCount(len(headers))
        self.usb_table_view.setHorizontalHeaderLabels(headers)

        self.usb_table_view.setRowCount(len(devices))
        for row, device in enumerate(devices):
            # Populate with new, richer data
            col_data = [
                device.get("Forensic ID", ""), device.get("Description", ""), device.get("Hardware ID", ""),
                device.get("Plug-in Time", ""), device.get("Duration", ""), device.get("Manufacturer", "")
            ]
            for col, value in enumerate(col_data):
                item = QTableWidgetItem(str(value))
                item.setFont(QFont("Segoe UI", 9))
                self.usb_table_view.setItem(row, col, item)
                
        self.usb_table_view.resizeColumnsToContents()
        self.usb_table_view.setSortingEnabled(True)
        connected_count = sum(1 for d in devices if d.get("Connected") == "Yes")
        self.usb_device_count_label.setText(f"{len(devices)} devices found ({connected_count} connected)")
        self.usb_status_bar.clearMessage()
    
    def show_usb_device_details(self, index):
        """Displays a dialog with detailed forensic info for the selected USB device."""
        if index.row() >= len(self.displayed_usb_devices):
            return

        device = self.displayed_usb_devices[index.row()]
        
        details_html = "<h3>Forensic Details</h3><ul>"
        for key, value in sorted(device.items()):
            if key != "datetime_obj": # Don't show the internal datetime object
                details_html += f"<li><b>{key.replace('_', ' ').title()}:</b> {value}</li>"
        details_html += "</ul>"

        QMessageBox.information(self, f"Details for {device.get('Description', 'Device')}", details_html)

    def export_usb_csv(self):
        """Exports the current USB device list to a CSV file."""
        if not self.displayed_usb_devices:
            QMessageBox.warning(self, "Export Failed", "No USB devices to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Export USB Devices", "", "CSV Files (*.csv);;All Files (*)")
        if file_path:
            try:
                with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(["Forensic ID", "Description", "Hardware ID", "Plug-in Time", "Duration", "Manufacturer"])
                    for device in self.displayed_usb_devices:
                        writer.writerow([
                            device.get("Forensic ID", ""),
                            device.get("Description", ""),
                            device.get("Hardware ID", ""),
                            device.get("Plug-in Time", ""),
                            device.get("Duration", ""),
                            device.get("Manufacturer", "")
                        ])
                QMessageBox.information(self, "Export Successful", f"USB devices exported to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", f"Failed to export to CSV: {e}")

    def identify_suspicious_patterns(self, devices):
        """Placeholder for identifying suspicious patterns in USB device data."""
        # This method is called by the new forensic button.
        # It should contain the logic to analyze the devices and identify patterns.
        # For now, it just returns a placeholder message.
        QMessageBox.information(self, "Suspicious Patterns", "Suspicious patterns analysis not yet implemented.")

    def perform_forensic_analysis(self):
        """Placeholder for generating and showing/exporting forensic report."""
        # This method is called by the new forensic button.
        # It should contain the logic to generate a comprehensive forensic report.
        # For now, it just returns a placeholder message.
        QMessageBox.information(self, "Forensic Analysis", "Forensic analysis not yet implemented.")

    def show_usb_context_menu(self, position):
        """Shows a context menu for the selected USB device."""
        index = self.usb_table_view.indexAt(position)
        if not index.isValid():
            return

        device = self.displayed_usb_devices[index.row()]
        menu = QMenu()
        menu.setFont(QFont("Segoe UI", 9))

        copy_cell_action = QAction("Copy Cell", self)
        copy_cell_action.setFont(QFont("Segoe UI", 9))
        copy_cell_action.triggered.connect(lambda: self.copy_cell_to_clipboard(index.row(), index.column()))
        menu.addAction(copy_cell_action)

        copy_row_action = QAction("Copy Row", self)
        copy_row_action.setFont(QFont("Segoe UI", 9))
        copy_row_action.triggered.connect(lambda: self.copy_row_to_clipboard(index.row()))
        menu.addAction(copy_row_action)

        menu.exec_(self.usb_table_view.viewport().mapToGlobal(position))

    def copy_cell_to_clipboard(self, row, column):
        """Copies the content of a specific cell to the clipboard."""
        item = self.usb_table_view.item(row, column)
        if item:
            QApplication.clipboard().setText(item.text())

    def copy_row_to_clipboard(self, row):
        """Copies the content of a specific row to the clipboard."""
        # This method is called by the context menu.
        # It should copy the entire row's data.
        # For now, it just copies the first column (Forensic ID) as a placeholder.
        # A more robust solution would involve copying all columns.
        row_data = []
        for col in range(self.usb_table_view.columnCount()):
            item = self.usb_table_view.item(row, col)
            if item:
                row_data.append(item.text())
        QApplication.clipboard().setText("\n".join(row_data))

    def _handle_tab_click(self, clicked_button):
        """Handle tab button clicks"""
        tab_text = clicked_button.text()
        # Potentially navigate to other pages. For now, just print.
        print(f"Tab clicked: {tab_text}")
        super()._handle_tab_click(clicked_button) 

if __name__ == '__main__':
    import sys
    print("This module is part of the Anubis Forensics GUI application.")
    print("Please run the main application using: python main.py")
    sys.exit(1) 
