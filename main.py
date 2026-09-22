import logging
import os
import sys
import traceback
from pathlib import Path


def _boot_log_path() -> Path:
    """Log rudimentario que se escribe desde el primer instante, antes del
    logging normal, para poder capturar crashes de arranque en el .exe.
    """
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    directory = Path(base) / "INICA-SIA-ReporteMensual"
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except Exception:
        directory = Path(os.path.expanduser("~"))
    return directory / "boot.log"


def _boot_log(message: str) -> None:
    try:
        path = _boot_log_path()
        with path.open("a", encoding="utf-8") as fh:
            fh.write(message + "\n")
    except Exception:
        pass


_boot_log(f"=== boot inicio {os.getpid()} sys.executable={sys.executable} frozen={getattr(sys, 'frozen', False)} ===")


# Permite encontrar recursos (icono) tanto en desarrollo como en el exe empaquetado
def _resource_path(relative: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


def _log_path() -> Path:
    """Ruta del archivo de log persistente.
    En Windows lo pone bajo %LOCALAPPDATA%\\INICA-SIA-ReporteMensual\\app.log
    para que sea escribible aunque el .exe esté en Archivos de Programa.
    """
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    directory = Path(base) / "INICA-SIA-ReporteMensual"
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except Exception:
        directory = Path(os.path.expanduser("~"))
    return directory / "app.log"


def _configure_logging():
    log_file = _log_path()
    handlers: list[logging.Handler] = []
    # En .exe --windowed sys.stderr puede ser None; solo agrega el stream si existe
    if getattr(sys, "stderr", None) is not None:
        try:
            handlers.append(logging.StreamHandler(sys.stderr))
        except Exception:
            pass
    try:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    except Exception:
        pass
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )
    return log_file


def _install_excepthook(log_file: Path):
    log = logging.getLogger("uncaught")

    def _hook(exc_type, exc_value, exc_tb):
        log.critical(
            "Excepción no controlada:\n%s",
            "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
        )
        try:
            from PyQt6.QtWidgets import QApplication, QMessageBox
            if QApplication.instance() is not None:
                QMessageBox.critical(
                    None,
                    "Error inesperado",
                    f"Ocurrió un error inesperado.\n\nDetalle:\n{exc_value}\n\n"
                    f"Se guardó el traceback en:\n{log_file}"
                )
        except Exception:
            pass

    sys.excepthook = _hook


# Icono correcto en la barra de tareas de Windows
if sys.platform == "win32":
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
        "INICA.SIA.ReporteMensual.1"
    )

_boot_log("importando PyQt6…")
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
_boot_log("importando MainController…")
from controller.main_controller import MainController
_boot_log("imports OK")


def main():
    _boot_log("main() inicio")
    log_file = _configure_logging()
    _install_excepthook(log_file)
    logging.getLogger(__name__).info("Iniciando aplicación (log: %s)", log_file)
    _boot_log(f"logging configurado -> {log_file}")

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon(_resource_path(os.path.join("assets", "icon.ico"))))

    _boot_log("QApplication creada, instanciando MainController…")
    controller = MainController()
    _boot_log("MainController listo, show()…")
    controller.show()

    _boot_log("entrando a app.exec()")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
