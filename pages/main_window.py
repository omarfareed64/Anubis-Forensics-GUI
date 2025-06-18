from PyQt5.QtWidgets import QMainWindow, QStackedWidget
from .home_page import HomePage, COLOR_GRAY
from .case_creation_page import CaseCreationPage
from .resource_page import ResourcePage
from .remote_acquisition_page import RemoteAcquisitionPage
from .remote_connection_page import RemoteConnectionPage

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

        self.stacked_widget.addWidget(self.home_page)
        self.stacked_widget.addWidget(self.case_creation_page)
        self.stacked_widget.addWidget(self.resource_page)
        self.stacked_widget.addWidget(self.remote_acquisition_page)
        self.stacked_widget.addWidget(self.remote_connection_page)

        # Connect signals for page navigation
        self.home_page.create_case_requested.connect(self._show_case_creation_page)
        self.case_creation_page.back_requested.connect(self._show_home_page)
        self.case_creation_page.resource_requested.connect(self._show_resource_page)
        self.remote_acquisition_page.back_requested.connect(self._show_resource_page)
        self.remote_acquisition_page.connect_requested.connect(self._show_remote_connection_page)
        self.remote_connection_page.back_requested.connect(self._show_remote_acquisition_page)

        # Centralized tab navigation
        for page in [self.home_page, self.case_creation_page, self.resource_page, self.remote_acquisition_page, self.remote_connection_page]:
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

    def _show_remote_connection_page(self):
        self.stacked_widget.setCurrentWidget(self.remote_connection_page)
        self._select_tab(self.remote_connection_page, "Resource")

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
        # Add more tab logic here as needed

    def _select_tab(self, page, tab_name):
        if hasattr(page, "tab_buttons"):
            page._select_tab_programmatically(tab_name)
