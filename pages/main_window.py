from PyQt5.QtWidgets import QMainWindow, QStackedWidget, QMessageBox

from .home_page import HomePage, COLOR_GRAY
from .case_creation_page import CaseCreationPage
from .resource_page import ResourcePage
from .remote_acquisition_page import RemoteAcquisitionPage
from .remote_connection_page import RemoteConnectionPage
from .analysis_page import AnalysisPage
from .report_page import ReportPage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Anubis Forensics")
        self.resize(1800, 1200)
        self.setMinimumSize(900, 640)
        self.setStyleSheet(f"background-color: {COLOR_GRAY}; font-family: 'Cascadia Mono';")

        self.current_case_path = None  # Single source of truth for the selected case

        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        self.home_page = HomePage()
        self.case_creation_page = CaseCreationPage()
        self.resource_page = ResourcePage()
        self.remote_acquisition_page = RemoteAcquisitionPage()
        self.remote_connection_page = RemoteConnectionPage()
        self.analysis_page = AnalysisPage()
        self.report_page = ReportPage()

        self.pages = [self.home_page, self.case_creation_page, self.resource_page, self.remote_acquisition_page,
                      self.remote_connection_page, self.analysis_page, self.report_page]
        for page in self.pages:
            self.stacked_widget.addWidget(page)
            page.tab_selected.connect(self._handle_tab_selected)

        # Page-specific navigation signals
        self.home_page.create_case_requested.connect(self._show_case_creation_page)
        self.home_page.add_evidence_requested.connect(self._show_resource_page_for_evidence)
        self.case_creation_page.back_requested.connect(self._show_home_page)
        self.case_creation_page.case_created.connect(self._on_case_created)
        self.case_creation_page.resource_requested.connect(self._show_resource_page)
        self.resource_page.back_requested.connect(self._show_home_page)
        self.resource_page.remote_acquisition_requested.connect(self._show_remote_acquisition_page)
        self.remote_acquisition_page.back_requested.connect(self._show_resource_page)
        self.remote_acquisition_page.connect_requested.connect(self._show_remote_connection_page)
        self.remote_connection_page.back_requested.connect(self._show_remote_acquisition_page)
        self.remote_connection_page.analysis_requested.connect(self._show_analysis_page)

    # ------------------------------------------------------------- helpers
    def set_case(self, case_path):
        """Propagate the selected case to every page that stores results."""
        self.current_case_path = case_path
        for page in (self.resource_page, self.remote_acquisition_page, self.remote_connection_page, self.analysis_page, self.report_page):
            page.set_case_path(case_path)

    def _show(self, page, tab_name):
        self.stacked_widget.setCurrentWidget(page)
        page._select_tab_programmatically(tab_name)

    # ---------------------------------------------------------- navigation
    def _show_home_page(self):
        self._show(self.home_page, "Case Info")

    def _show_case_creation_page(self):
        self._show(self.case_creation_page, "Case Info")

    def _on_case_created(self, case_path):
        self.set_case(case_path)
        self._show_resource_page()

    def _show_resource_page(self):
        self._show(self.resource_page, "Resource")

    def _show_resource_page_for_evidence(self, case_path):
        self.set_case(case_path)
        self._show_resource_page()

    def _show_remote_acquisition_page(self):
        if not self.current_case_path:
            QMessageBox.warning(self, "No Case Selected", "Select or create a case first so acquired evidence can be stored in it.")
            return
        self._show(self.remote_acquisition_page, "Resource")

    def _show_remote_connection_page(self, connection_params):
        self._show(self.remote_connection_page, "Resource")
        self.remote_connection_page.set_connection_params(connection_params)
        self.analysis_page.set_connection_params(connection_params)

    def _show_analysis_page(self):
        self._show(self.analysis_page, "Analyze Evidence")
        if self.current_case_path:
            self.analysis_page.set_case_path(self.current_case_path)
        if self.remote_connection_page.connection_params:
            self.analysis_page.set_connection_params(self.remote_connection_page.connection_params)

    def _show_report_page(self):
        self._show(self.report_page, "Report")
        self.report_page.set_case_path(self.current_case_path)

    def _handle_tab_selected(self, tab_name):
        if tab_name == "Case Info":
            self._show_home_page()
        elif tab_name == "Resource":
            if self.current_case_path:
                self._show_resource_page_for_evidence(self.current_case_path)
            else:
                self._show_resource_page()
        elif tab_name == "Analyze Evidence":
            self._show_analysis_page()
        elif tab_name == "Report":
            self._show_report_page()
