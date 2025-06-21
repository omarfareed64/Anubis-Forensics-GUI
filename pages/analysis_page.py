import csv
import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QComboBox, QGroupBox, QGridLayout,
    QStatusBar, QProgressBar, QFileDialog, QAction, QMenu, QApplication, QTextEdit,
    QListWidget, QListWidgetItem, QScrollArea
)
from PyQt5.QtGui import QFont, QColor, QKeySequence
from PyQt5.QtCore import Qt, pyqtSignal, QThread, pyqtSignal as Signal, QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView
from .base_page import BasePage, COLOR_ORANGE, COLOR_DARK, COLOR_GRAY, TAB_NAMES
from services.web_artifact_extractor import extract_all_web_artifacts
from services.usb_analyzer import get_usb_devices
from services.registry_analyzer import RegistryAnalyzer
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

class RegistryWorker(QThread):
    """Worker thread for registry operations"""
    progress_updated = pyqtSignal(str)
    operation_completed = pyqtSignal(str, bool, str)
    header_output = pyqtSignal(str)  # For header parsing output
    
    def __init__(self, analyzer, operation, **kwargs):
        super().__init__()
        self.analyzer = analyzer
        self.operation = operation
        self.kwargs = kwargs
        
        # Connect the analyzer's signals to our signals
        self.analyzer.progress_updated.connect(self.progress_updated.emit)
        self.analyzer.operation_completed.connect(self.operation_completed.emit)
        self.analyzer.header_output.connect(self.header_output.emit)
        
    def run(self):
        # This will call the appropriate method on the RegistryAnalyzer instance
        operation_func = getattr(self.analyzer, self.operation, None)
        if operation_func:
            # We need to unpack the kwargs dict to pass them as arguments
            success, message = operation_func(**self.kwargs)
            self.operation_completed.emit(self.operation, success, message)

class AnalysisPage(BasePage):
    back_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.connection_params = None
        self.web_artifact_thread = None
        self.usb_device_thread = None
        self.registry_worker_thread = None
        self.registry_analyzer = RegistryAnalyzer() # Add analyzer instance
        self.usb_devices = [] # To store full list of devices
        self.displayed_usb_devices = [] # To store the currently visible list
        self.selected_case_path = None
        self.setup_page_content()
        self._select_tab_programmatically("Analyze Evidence")

    def set_connection_params(self, params):
        """Receive and store connection parameters."""
        self.connection_params = params

    def set_case_path(self, case_path):
        self.selected_case_path = case_path
        if case_path:
            base_output = os.path.join(self.selected_case_path, "registry_analysis")
            self.acquire_output_dir_input.setText(os.path.join(base_output, "acquired_hives"))
            self.analyze_input_dir.setText(os.path.join(base_output, "acquired_hives"))
            self.compare_output_dir.setText(os.path.join(base_output, "comparison_results"))
            self.logs_output_dir.setText(os.path.join(base_output, "recovered_hives"))

    def _switch_right_panel_view(self, view_to_show):
        """Manages visibility of widgets in the right panel."""
        self.web_view.setVisible(self.web_view == view_to_show)
        self.usb_view_container.setVisible(self.usb_view_container == view_to_show)
        self.registry_view_container.setVisible(self.registry_view_container == view_to_show)
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

        search_label = QLabel("Search")
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

        # --- Registry View Container ---
        self.registry_view_container = self.create_registry_view()
        right_layout.addWidget(self.registry_view_container)

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
        """Handle clicks on the left-side artifact buttons."""
        if artifact_name == "WEB":
            if not self.connection_params:
                QMessageBox.warning(self, "No Connection", "Please establish a remote connection first.")
                return
            self.web_view.load(QUrl()) # Clear previous content
            self._switch_right_panel_view(self.web_view)
            self.web_artifact_thread = WebArtifactThread(self.connection_params)
            self.web_artifact_thread.finished.connect(self.on_web_extraction_finished)
            self.web_artifact_thread.start()
        elif artifact_name == "USB":
            self._switch_right_panel_view(self.usb_view_container)
            self.usb_device_thread = UsbDeviceThread()
            self.usb_device_thread.finished.connect(self.on_usb_scan_finished)
            self.usb_device_thread.start()
        elif artifact_name == "REGISTRY":
            if not self.selected_case_path:
                QMessageBox.warning(self, "No Case Selected", "A case must be selected to perform registry analysis.")
                return
            # Update output paths before showing
            self.set_case_path(self.selected_case_path)
            self._switch_right_panel_view(self.registry_view_container)
        else:
            self.placeholder_label.setText(f"{artifact_name} analysis not implemented yet.")
            self._switch_right_panel_view(self.placeholder_label)

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

    # --- REGISTRY ANALYSIS METHODS ---
    def create_registry_view(self):
        """Creates the entire view for Registry Analysis options."""
        container = QFrame()
        container.setStyleSheet("background-color: transparent;")
        
        # Main content area
        content_layout = QHBoxLayout(container)
        
        # Left panel - Options
        left_panel = self.create_registry_options_panel()
        content_layout.addWidget(left_panel, 1)
        
        # Right panel - Progress and Results
        right_panel = self.create_registry_progress_panel()
        content_layout.addWidget(right_panel, 1)
        
        return container

    def create_registry_options_panel(self):
        """Create the left panel with registry analysis options"""
        panel = QScrollArea()
        panel.setWidgetResizable(True)
        panel.setStyleSheet("background: white; border-radius: 12px; padding: 10px; border: none;")
        
        content_widget = QWidget()
        panel.setWidget(content_widget)
        
        layout = QVBoxLayout(content_widget)
        
        # Title
        title = QLabel("Registry Analysis Options")
        title.setFont(QFont("Cascadia Mono", 16, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLOR_DARK}; margin-bottom: 15px;")
        layout.addWidget(title)
        
        # Option 1: Acquire Registry Hives
        acquire_group = self.create_acquire_hives_group()
        layout.addWidget(acquire_group)
        
        # Option 2: Analyze Registry Hives
        analyze_group = self.create_analyze_hives_group()
        layout.addWidget(analyze_group)
        
        # Option 3: Compare Registry Hives
        compare_group = self.create_compare_hives_group()
        layout.addWidget(compare_group)
        
        # Option 4: Apply Transaction Logs
        logs_group = self.create_apply_logs_group()
        layout.addWidget(logs_group)
        
        # Option 5: Parse Hive Header
        header_group = self.create_parse_header_group()
        layout.addWidget(header_group)
        
        layout.addStretch()
        return panel

    def _get_group_box_style(self):
        return f"""
            QGroupBox {{
                border: 2px solid {COLOR_DARK};
                border-radius: 8px;
                margin-top: 15px;
                padding: 15px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 5px 0 5px;
                color: {COLOR_DARK};
                font-size: 14px;
                font-weight: bold;
            }}
        """

    def _create_small_browse_button(self, callback):
        browse_btn = QPushButton("Browse...")
        browse_btn.setFixedSize(100, 44)
        # Create a smaller version of the standard button style
        small_button_style = self.get_button_style(bg_color=COLOR_DARK, text_color="white", hover_color=COLOR_ORANGE)
        small_button_style = small_button_style.replace("padding: 18px 64px;", "padding: 8px 12px;")
        small_button_style = small_button_style.replace("font-size: 22px;", "font-size: 14px;")
        browse_btn.setStyleSheet(small_button_style)
        browse_btn.clicked.connect(callback)
        return browse_btn
        
    def create_registry_progress_panel(self):
        panel = QWidget()
        panel.setStyleSheet("background: white; border-radius: 12px; padding: 20px;")
        layout = QVBoxLayout(panel)
        title = QLabel("Progress & Results")
        title.setFont(QFont("Cascadia Mono", 18, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLOR_DARK}; margin-bottom: 20px;")
        layout.addWidget(title)
        
        self.registry_progress_text = QTextEdit()
        self.registry_progress_text.setReadOnly(True)
        self.registry_progress_text.setStyleSheet(f"""
            QTextEdit {{
                border: 2px solid {COLOR_DARK};
                border-radius: 8px;
                padding: 10px;
                font-family: 'Cascadia Mono';
                font-size: 12px;
                background-color: #f8f8f8;
            }}
        """)
        layout.addWidget(self.registry_progress_text)
        return panel

    def create_acquire_hives_group(self):
        group = QGroupBox("1. Acquire Registry Hives")
        group.setFont(QFont("Cascadia Mono", 12, QFont.Weight.Bold))
        group.setStyleSheet(self._get_group_box_style())
        
        layout = QVBoxLayout(group)
        layout.setSpacing(10)
        
        layout.addWidget(QLabel("Username (optional):"))
        self.username_input = self.create_styled_input("For NTUSER.DAT and UsrClass.dat")
        layout.addWidget(self.username_input)
        
        layout.addSpacing(10)
        layout.addWidget(QLabel("Select Hives to Acquire:"))
        self.hive_list = QListWidget()
        self.hive_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.hive_list.setMaximumHeight(150)
        self.hive_list.setStyleSheet(f"border: 1px solid {COLOR_DARK}; border-radius: 5px; padding: 5px;")
        
        available_hives = self.registry_analyzer.get_available_hives()
        for hive in available_hives:
            self.hive_list.addItem(QListWidgetItem(hive))
        layout.addWidget(self.hive_list)
        
        layout.addSpacing(10)
        layout.addWidget(QLabel("Output Directory:"))
        output_layout = QHBoxLayout()
        self.acquire_output_dir_input = self.create_styled_input()
        browse_btn = self._create_small_browse_button(lambda: self.browse_directory(self.acquire_output_dir_input))
        output_layout.addWidget(self.acquire_output_dir_input)
        output_layout.addWidget(browse_btn)
        layout.addLayout(output_layout)
        
        layout.addSpacing(15)
        acquire_btn = self.create_styled_button("Acquire Hives", self.acquire_hives)
        layout.addWidget(acquire_btn, alignment=Qt.AlignCenter)
        
        return group

    def create_analyze_hives_group(self):
        group = QGroupBox("2. Analyze Registry Hives")
        group.setFont(QFont("Cascadia Mono", 12, QFont.Weight.Bold))
        group.setStyleSheet(self._get_group_box_style())
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Directory of Acquired Hives:"))
        input_layout = QHBoxLayout()
        self.analyze_input_dir = self.create_styled_input()
        browse_input_btn = self._create_small_browse_button(lambda: self.browse_directory(self.analyze_input_dir))
        input_layout.addWidget(self.analyze_input_dir)
        input_layout.addWidget(browse_input_btn)
        layout.addLayout(input_layout)

        populate_btn = QPushButton("List Hives from Directory")
        small_button_style = self.get_button_style(bg_color=COLOR_DARK, text_color="white", hover_color=COLOR_ORANGE)
        small_button_style = small_button_style.replace("padding: 18px 64px;", "padding: 8px 12px;").replace("font-size: 22px;", "font-size: 14px;")
        populate_btn.setStyleSheet(small_button_style)
        populate_btn.setFixedHeight(44)
        populate_btn.clicked.connect(self.populate_hives_for_analysis)
        layout.addWidget(populate_btn, alignment=Qt.AlignLeft)
        
        layout.addSpacing(10)
        layout.addWidget(QLabel("Select Hives to Analyze:"))
        self.analyze_hive_list = QListWidget()
        self.analyze_hive_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.analyze_hive_list.setMaximumHeight(150)
        self.analyze_hive_list.setStyleSheet(f"border: 1px solid {COLOR_DARK}; border-radius: 5px; padding: 5px;")
        layout.addWidget(self.analyze_hive_list)

        layout.addSpacing(15)
        analyze_btn = self.create_styled_button("Analyze Selected Hives", self.analyze_hives)
        layout.addWidget(analyze_btn, alignment=Qt.AlignCenter)
        return group

    def create_compare_hives_group(self):
        group = QGroupBox("3. Compare Registry Hives")
        group.setFont(QFont("Cascadia Mono", 12, QFont.Weight.Bold))
        group.setStyleSheet(self._get_group_box_style())
        layout = QVBoxLayout(group)
        layout.setSpacing(10)
        
        layout.addWidget(QLabel("First Hive:"))
        hive1_layout = QHBoxLayout()
        self.hive1_input = self.create_styled_input("Path to first hive file")
        browse1_btn = self._create_small_browse_button(lambda: self.browse_file(self.hive1_input))
        hive1_layout.addWidget(self.hive1_input)
        hive1_layout.addWidget(browse1_btn)
        layout.addLayout(hive1_layout)

        layout.addSpacing(10)
        layout.addWidget(QLabel("Second Hive:"))
        hive2_layout = QHBoxLayout()
        self.hive2_input = self.create_styled_input("Path to second hive file")
        browse2_btn = self._create_small_browse_button(lambda: self.browse_file(self.hive2_input))
        hive2_layout.addWidget(self.hive2_input)
        hive2_layout.addWidget(browse2_btn)
        layout.addLayout(hive2_layout)
        
        layout.addSpacing(10)
        layout.addWidget(QLabel("Output Directory for Report:"))
        output_layout = QHBoxLayout()
        self.compare_output_dir = self.create_styled_input()
        browse3_btn = self._create_small_browse_button(lambda: self.browse_directory(self.compare_output_dir))
        output_layout.addWidget(self.compare_output_dir)
        output_layout.addWidget(browse3_btn)
        layout.addLayout(output_layout)

        layout.addSpacing(15)
        compare_btn = self.create_styled_button("Compare Hives", self.compare_hives)
        layout.addWidget(compare_btn, alignment=Qt.AlignCenter)
        
        return group

    def create_apply_logs_group(self):
        group = QGroupBox("4. Apply Transaction Logs")
        group.setFont(QFont("Cascadia Mono", 12, QFont.Weight.Bold))
        group.setStyleSheet(self._get_group_box_style())
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Hive File:"))
        hive_layout = QHBoxLayout()
        self.logs_hive_input = self.create_styled_input("Path to hive file (e.g., SYSTEM, NTUSER.DAT)")
        browse1_btn = self._create_small_browse_button(lambda: self.browse_file(self.logs_hive_input))
        hive_layout.addWidget(self.logs_hive_input)
        hive_layout.addWidget(browse1_btn)
        layout.addLayout(hive_layout)
        
        layout.addSpacing(10)
        layout.addWidget(QLabel("Output Directory for Recovered Hive:"))
        output_layout = QHBoxLayout()
        self.logs_output_dir = self.create_styled_input()
        browse2_btn = self._create_small_browse_button(lambda: self.browse_directory(self.logs_output_dir))
        output_layout.addWidget(self.logs_output_dir)
        output_layout.addWidget(browse2_btn)
        layout.addLayout(output_layout)

        layout.addSpacing(15)
        apply_btn = self.create_styled_button("Apply Transaction Logs", self.apply_transaction_logs)
        layout.addWidget(apply_btn, alignment=Qt.AlignCenter)
        
        return group

    def create_parse_header_group(self):
        group = QGroupBox("5. Parse Hive Header")
        group.setFont(QFont("Cascadia Mono", 12, QFont.Weight.Bold))
        group.setStyleSheet(self._get_group_box_style())
        layout = QVBoxLayout(group)
        layout.setSpacing(10)
        
        layout.addWidget(QLabel("Hive File:"))
        hive_layout = QHBoxLayout()
        self.header_hive_input = self.create_styled_input("Path to hive file to parse")
        browse_btn = self._create_small_browse_button(lambda: self.browse_file(self.header_hive_input))
        hive_layout.addWidget(self.header_hive_input)
        hive_layout.addWidget(browse_btn)
        layout.addLayout(hive_layout)

        layout.addSpacing(15)
        parse_btn = self.create_styled_button("Parse Hive Header", self.parse_hive_header)
        layout.addWidget(parse_btn, alignment=Qt.AlignCenter)
        
        return group
    
    def populate_hives_for_analysis(self):
        """Lists hive files from the selected input directory."""
        input_dir = self.analyze_input_dir.text()
        if not os.path.isdir(input_dir):
            QMessageBox.warning(self, "Invalid Directory", "Please select a valid directory first.")
            return
        self.analyze_hive_list.clear()
        try:
            for item in os.listdir(input_dir):
                if os.path.isfile(os.path.join(input_dir, item)):
                    self.analyze_hive_list.addItem(QListWidgetItem(item))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not read directory: {e}")

    def acquire_hives(self):
        """Handles the logic for acquiring selected hives."""
        selected_items = self.hive_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Missing Information", "Please select at least one hive to acquire.")
            return
        output_dir = self.acquire_output_dir_input.text()
        if not output_dir:
            QMessageBox.warning(self, "Missing Information", "Please specify an output directory.")
            return
        selected_hives = [item.text() for item in selected_items]
        username = self.username_input.text()
        self.start_registry_operation("acquire_registry_hives", {
            'output_dir': output_dir,
            'selected_hives': selected_hives,
            'username': username
        })

    def analyze_hives(self):
        """Handles the logic for analyzing selected hives."""
        selected_items = self.analyze_hive_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Missing Information", "Please select at least one hive to analyze.")
            return
        selected_hives = [item.text() for item in selected_items]
        analysis_dir = os.path.join(self.selected_case_path, "registry_analysis", "analysis_results")
        self.start_registry_operation("analyze_registry_hive", {
            'input_dir': self.analyze_input_dir.text(),
            'analysis_dir': analysis_dir,
            'selected_hives': selected_hives
        })

    def compare_hives(self):
        """Handles the logic for comparing two hives."""
        hive1 = self.hive1_input.text()
        hive2 = self.hive2_input.text()
        output_dir = self.compare_output_dir.text()
        if not all([hive1, hive2, output_dir]):
            QMessageBox.warning(self, "Missing Information", "Please provide paths for both hives and an output directory.")
            return
        self.start_registry_operation("compare_registry_hives", {
            'hive1_path': hive1,
            'hive2_path': hive2,
            'output_dir': output_dir
        })

    def apply_transaction_logs(self):
        """Handles the logic for applying transaction logs."""
        hive_path = self.logs_hive_input.text()
        output_dir = self.logs_output_dir.text()
        if not all([hive_path, output_dir]):
            QMessageBox.warning(self, "Missing Information", "Please provide the hive path and an output directory.")
            return
        self.start_registry_operation("apply_transaction_logs", {
            'hive_path': hive_path,
            'output_dir': output_dir
        })

    def parse_hive_header(self):
        """Handles the logic for parsing a hive header."""
        hive_path = self.header_hive_input.text()
        if not hive_path:
            QMessageBox.warning(self, "Missing Information", "Please provide the hive path.")
            return
        self.start_registry_operation("parse_hive_header", {'hive_path': hive_path})

    def browse_directory(self, input_field):
        """Opens a dialog to select a directory and sets the path to the input field."""
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if directory:
            input_field.setText(directory)

    def browse_file(self, input_field):
        """Opens a dialog to select a file and sets the path to the input field."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Hive File", "", "All Files (*)")
        if file_path:
            input_field.setText(file_path)

    def start_registry_operation(self, operation, kwargs):
        if self.registry_worker_thread and self.registry_worker_thread.isRunning():
            QMessageBox.warning(self, "In Progress", "Another registry operation is in progress.")
            return
        
        self.registry_progress_text.clear()
        self.registry_worker_thread = RegistryWorker(self.registry_analyzer, operation, **kwargs)
        self.registry_worker_thread.progress_updated.connect(self.update_registry_progress)
        self.registry_worker_thread.operation_completed.connect(self.handle_registry_operation_completed)
        self.registry_worker_thread.header_output.connect(self.display_header_output)
        self.registry_worker_thread.start()

    def update_registry_progress(self, message):
        self.registry_progress_text.append(message)

    def handle_registry_operation_completed(self, operation, success, message):
        status = "SUCCESS" if success else "FAILED"
        self.registry_progress_text.append(f"--- [{datetime.now().strftime('%H:%M:%S')}] {operation.replace('_', ' ').title()} {status} ---")
        if not success:
             self.registry_progress_text.append(f"Error: {message}\n")
        else:
             self.registry_progress_text.append(f"Details: {message}\n")
        
        # No popup for every operation, progress text is enough
        # QMessageBox.information(self, f"Operation {status}", message)

    def display_header_output(self, output):
        """Display header parsing output in a formatted way"""
        self.registry_progress_text.append("=" * 60)
        self.registry_progress_text.append("REGISTRY HIVE HEADER ANALYSIS")
        self.registry_progress_text.append("=" * 60)
        self.registry_progress_text.append(output)
        self.registry_progress_text.append("=" * 60)
        self.registry_progress_text.append("")  # Add empty line for spacing

if __name__ == '__main__':
    import sys
    print("This module is part of the Anubis Forensics GUI application.")
    print("Please run the main application using: python main.py")
    sys.exit(1) 
