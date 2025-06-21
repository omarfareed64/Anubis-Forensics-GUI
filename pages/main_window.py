from PyQt5.QtWidgets import QMainWindow, QStackedWidget
from .home_page import HomePage, COLOR_GRAY
from .case_creation_page import CaseCreationPage
from .resource_page import ResourcePage
from .remote_acquisition_page import RemoteAcquisitionPage
from .remote_connection_page import RemoteConnectionPage
from .analysis_page import AnalysisPage

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Anubis Forensics")
        self.resize(1800, 1200)
        self.setStyleSheet(f"background-color: {COLOR_GRAY}; font-family: 'Cascadia Mono';")

        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        self.home_page = HomePage()
        self.case_creation_page = CaseCreationPage()
        self.resource_page = ResourcePage()
        self.remote_acquisition_page = RemoteAcquisitionPage()
        self.remote_connection_page = RemoteConnectionPage()
        self.analysis_page = AnalysisPage()

        self.stacked_widget.addWidget(self.home_page)
        self.stacked_widget.addWidget(self.case_creation_page)
        self.stacked_widget.addWidget(self.resource_page)
        self.stacked_widget.addWidget(self.remote_acquisition_page)
        self.stacked_widget.addWidget(self.remote_connection_page)
        self.stacked_widget.addWidget(self.analysis_page)

        # Connect signals for page navigation
        self.home_page.create_case_requested.connect(self._show_case_creation_page)
        self.home_page.add_evidence_requested.connect(self._show_resource_page_for_evidence)
        self.case_creation_page.back_requested.connect(self._show_home_page)
        self.case_creation_page.resource_requested.connect(self._show_resource_page)
        self.resource_page.back_requested.connect(self._show_home_page)
        self.remote_acquisition_page.back_requested.connect(self._show_resource_page)
        self.remote_acquisition_page.connect_requested.connect(self._show_remote_connection_page)
        self.remote_connection_page.back_requested.connect(self._show_remote_acquisition_page)
        self.remote_connection_page.analysis_requested.connect(self._show_analysis_page)

        # Centralized tab navigation
        for page in [self.home_page, self.case_creation_page, self.resource_page, self.remote_acquisition_page, self.remote_connection_page, self.analysis_page]:
            page.tab_selected.connect(self._handle_tab_selected)

        # Connect remote acquisition navigation
        self.resource_page.remote_acquisition_requested.connect(self._show_remote_acquisition_page)

    def _show_case_creation_page(self):
        self.stacked_widget.setCurrentWidget(self.case_creation_page)
        self._select_tab(self.case_creation_page, "Case Info")

    def _show_home_page(self):
        self.stacked_widget.setCurrentWidget(self.home_page)
        self._select_tab(self.home_page, "Case Info")

    def _show_resource_page(self):
        self.stacked_widget.setCurrentWidget(self.resource_page)
        self._select_tab(self.resource_page, "Resource")

    def _show_remote_acquisition_page(self):
        self.stacked_widget.setCurrentWidget(self.remote_acquisition_page)
        self._select_tab(self.remote_acquisition_page, "Resource")
        # Pass the case path from resource page to acquisition page
        if hasattr(self.resource_page, 'selected_case_path'):
            case_path = self.resource_page.selected_case_path
            if hasattr(self.remote_acquisition_page, 'set_case_path'):
                self.remote_acquisition_page.set_case_path(case_path)

    def _show_remote_connection_page(self, connection_params):
        """Show remote connection page with connection parameters"""
        self.stacked_widget.setCurrentWidget(self.remote_connection_page)
        self._select_tab(self.remote_connection_page, "Resource")
        # Pass connection parameters to the remote connection page
        self.remote_connection_page.set_connection_params(connection_params)
        # Pass case path as well
        if hasattr(self.remote_acquisition_page, 'selected_case_path'):
            case_path = self.remote_acquisition_page.selected_case_path
            if hasattr(self.remote_connection_page, 'set_case_path'):
                self.remote_connection_page.set_case_path(case_path)

    def _show_analysis_page(self):
        self.stacked_widget.setCurrentWidget(self.analysis_page)
        self._select_tab(self.analysis_page, "Analyze Evidence")
        # Pass connection parameters to the analysis page
        if hasattr(self.remote_connection_page, 'connection_params'):
            params = self.remote_connection_page.connection_params
            if hasattr(self.analysis_page, 'set_connection_params'):
                self.analysis_page.set_connection_params(params)

    def _show_resource_page_for_evidence(self, case_path):
        """Show resource page for adding evidence to a specific case"""
        self.stacked_widget.setCurrentWidget(self.resource_page)
        self._select_tab(self.resource_page, "Resource")
        # Pass the case path to the resource page
        if hasattr(self.resource_page, 'set_case_path'):
            self.resource_page.set_case_path(case_path)

    def _handle_tab_selected(self, tab_name):
        if tab_name == "Case Info":
            self._show_home_page()
        elif tab_name == "Resource":
            # Check which page is currently active to determine navigation
            current_widget = self.stacked_widget.currentWidget()
            if current_widget == self.remote_acquisition_page:
                self._show_remote_connection_page()
            else:
                self._show_resource_page()
        elif tab_name == "Analyze Evidence":
            self._show_analysis_page()
        # Add more tab logic here as needed

    def _select_tab(self, page, tab_name):
        if hasattr(page, "tab_buttons"):
            page._select_tab_programmatically(tab_name)
