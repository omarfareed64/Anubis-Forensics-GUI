import sys
from PyQt5.QtWidgets import QApplication
from pages.splash_screen import SplashScreen
from pages.main_window import MainWindow


def safe_window_geometry(requested_width, requested_height, screen_width, screen_height, padding=80):
    """Return a window size that fits the current display without triggering Qt geometry warnings."""
    max_width = max(1, screen_width - padding)
    max_height = max(1, screen_height - padding)

    width = min(requested_width, max_width)
    height = min(requested_height, max_height)
    return width, height


def main():
    app = QApplication(sys.argv)
    window = None

    def show_main():
        nonlocal window
        splash.close()
        window = MainWindow()
        screen = app.primaryScreen().availableGeometry()
        width, height = safe_window_geometry(1800, 1200, screen.width(), screen.height())
        window.resize(width, height)
        window.show()

    splash = SplashScreen(on_begin_callback=show_main)
    splash.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
