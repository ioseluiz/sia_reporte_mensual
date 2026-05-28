import os
import sys

# Permite encontrar recursos (icono) tanto en desarrollo como en el exe empaquetado
def _resource_path(relative: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)

# Icono correcto en la barra de tareas de Windows
if sys.platform == "win32":
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
        "INICA.SIA.ReporteMensual.1"
    )

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from controller.main_controller import MainController


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon(_resource_path(os.path.join("assets", "icon.ico"))))

    controller = MainController()
    controller.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
