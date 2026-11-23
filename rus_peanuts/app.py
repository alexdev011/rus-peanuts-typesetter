"""Запуск приложения RUS PEANUTS."""
import sys

from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QApplication

from rus_peanuts.typesetting.fonts import load_fonts
from rus_peanuts.typesetting.layout import Typography
from rus_peanuts.ui import embedded
from rus_peanuts.ui.main_window import MainWindow
from rus_peanuts.ui.qt_setup import prepare_qt


def main() -> None:
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ruspeanuts.autotypesetter.v7")
    except Exception:
        pass
    prepare_qt()
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(embedded.pixmap(embedded.EMBEDDED_APP_ICON_B64)))
    window = MainWindow(Typography(load_fonts()))
    window.show()
    sys.exit(app.exec())
