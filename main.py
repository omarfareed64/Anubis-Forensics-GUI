import sys
from PyQt5.QtWidgets import QApplication
from pages.splash_screen import SplashScreen
from pages.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    window = None


    def show_main():
        nonlocal window
        splash.close()
        window = MainWindow()
        window.showMaximized()

    splash = SplashScreen(on_begin_callback=show_main)
    splash.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
