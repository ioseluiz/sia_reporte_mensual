from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal, pyqtSlot, QTimer
from PyQt6.QtWidgets import QFileDialog, QDialog
from datetime import datetime

import pandas as pd

from model import sia_model
from view.main_window import MainWindow
from view.detail_dialog import DetailDialog


class _Signals(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)


class _Worker(QRunnable):
    """Ejecuta una función en el pool de hilos y emite el resultado vía signals."""

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.signals = _Signals()

    @pyqtSlot()
    def run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
            self.signals.finished.emit(result)
        except Exception as exc:
            self.signals.error.emit(str(exc))


class MainController:
    def __init__(self):
        self.view = MainWindow()
        self._pool = QThreadPool.globalInstance()
        self._data: list[dict] = []
        self._busy = False
        self._connect_signals()
        # Diferir el arranque al event loop para que la ventana ya esté visible
        QTimer.singleShot(0, self._startup)

    # ------------------------------------------------------------------
    # Señales
    # ------------------------------------------------------------------

    def _connect_signals(self):
        self.view.btn_query.clicked.connect(self._run_query)
        self.view.btn_reload_ramos.clicked.connect(self._load_ramos)
        self.view.btn_export.clicked.connect(self._export_excel)
        self.view.btn_select_all.clicked.connect(self.view.select_all_ramos)
        self.view.btn_clear_all.clicked.connect(self.view.clear_all_ramos)
        self.view.table.doubleClicked.connect(self._on_row_double_clicked)
        self.view.settings_requested.connect(self._open_settings)

    # ------------------------------------------------------------------
    # Arranque y configuración
    # ------------------------------------------------------------------

    def _startup(self):
        if self._check_env_configured():
            self._load_ramos()
        else:
            self.view.set_status(
                "Credenciales no configuradas. Completa la conexión para continuar."
            )
            self._open_settings(first_run=True)

    def _check_env_configured(self) -> bool:
        from dotenv import dotenv_values
        from model.database import get_env_path
        import os
        path = get_env_path()
        if not os.path.exists(path):
            return False
        vals = dotenv_values(path)
        required = [
            "DB_SERVER_SQLSERVER", "DB_NAME_SQLSERVER",
            "DB_USERNAME_SQLSERVER", "DB_PASSWORD_SQLSERVER",
        ]
        return all(vals.get(k, "").strip() for k in required)

    def _open_settings(self, first_run: bool = False):
        from view.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self.view)
        result = dialog.exec()
        if result == QDialog.DialogCode.Accepted:
            self._load_ramos()
        elif first_run:
            self.view.set_status(
                "Sin credenciales configuradas. Usa Configuración → Conexión a base de datos."
            )

    # ------------------------------------------------------------------
    # Cargar ramos
    # ------------------------------------------------------------------

    def _load_ramos(self):
        if self._busy:
            return
        self._set_busy(True)
        self.view.set_status("Conectando a la base de datos y cargando CodRamo de transacciones…")
        worker = _Worker(sia_model.get_ramos)
        worker.signals.finished.connect(self._on_ramos_loaded)
        worker.signals.error.connect(self._on_ramos_error)
        self._pool.start(worker)

    def _on_ramos_loaded(self, ramos: list):
        self.view.set_ramos(ramos)
        self.view.set_status(
            f"{len(ramos)} CodRamo de transacciones cargados." if ramos
            else "No se encontraron CodRamo en tblTransacciones para proyectos INI%."
        )
        self._set_busy(False)

    def _on_ramos_error(self, error: str):
        self._set_busy(False)
        if "Faltan las siguientes variables" in error:
            self.view.set_status("Credenciales incompletas en .env.")
            self._open_settings(first_run=True)
        else:
            self.view.set_status("Error al cargar ramos.")
            self.view.show_error(
                "Error de conexión",
                f"No se pudieron cargar los ramos:\n\n{error}"
                "\n\nVerifica las credenciales en Configuración → Conexión a base de datos.",
            )

    # ------------------------------------------------------------------
    # Consulta
    # ------------------------------------------------------------------

    def _run_query(self):
        if self._busy:
            return

        ramos = self.view.get_selected_ramos()
        if not ramos:
            self.view.show_error("Validación", "Selecciona al menos un CodRamo antes de consultar.")
            return

        start_date, end_date = self.view.get_date_range()
        if start_date > end_date:
            self.view.show_error("Validación", "La fecha inicial no puede ser mayor que la fecha final.")
            return

        self._set_busy(True)
        self.view.set_status("Ejecutando consulta…")
        worker = _Worker(sia_model.query_transactions, start_date, end_date, ramos)
        worker.signals.finished.connect(self._on_query_finished)
        worker.signals.error.connect(self._on_query_error)
        self._pool.start(worker)

    def _on_query_finished(self, data: list):
        self._data = data
        self.view.display_results(data)
        if data:
            self.view.set_status(f"Consulta completada: {len(data)} registros encontrados.")
        else:
            self.view.set_status("La consulta no devolvió resultados para los filtros seleccionados.")
        self._set_busy(False)

    def _on_query_error(self, error: str):
        self.view.set_status("Error al ejecutar la consulta.")
        self.view.show_error("Error de consulta", f"Ocurrió un error al consultar la base de datos:\n\n{error}")
        self._set_busy(False)

    # ------------------------------------------------------------------
    # Detalle de proyecto (doble clic)
    # ------------------------------------------------------------------

    def _on_row_double_clicked(self, index):
        if self._busy or not self._data:
            return
        row_data = self.view.get_row_data_at(index)
        cod_proyecto = row_data.get("CodProyecto", "").strip()
        if not cod_proyecto:
            return

        cod_ramo = row_data.get("CodRamo", "").strip()
        ramos = [cod_ramo] if cod_ramo else self.view.get_selected_ramos()

        start_date, end_date = self.view.get_date_range()
        self.view.set_status(f"Cargando transacciones de {cod_proyecto} / {cod_ramo}…")

        worker = _Worker(
            sia_model.get_project_transactions,
            cod_proyecto, start_date, end_date, ramos,
        )
        worker.signals.finished.connect(
            lambda data, p=cod_proyecto, r=ramos: self._show_detail(p, data, r)
        )
        worker.signals.error.connect(
            lambda e: self.view.show_error("Error al cargar detalle", e)
        )
        self._pool.start(worker)

    def _show_detail(self, cod_proyecto: str, data: list, ramos: list):
        self.view.set_status(f"{len(data)} transacciones cargadas para {cod_proyecto}.")
        dialog = DetailDialog(cod_proyecto, data, self.view)
        dialog.btn_export.clicked.connect(
            lambda: self._export_detail(cod_proyecto, data, ramos)
        )
        dialog.exec()

    def _export_detail(self, cod_proyecto: str, data: list, ramos: list):
        if not data:
            return
        safe_name = cod_proyecto.strip().replace(" ", "_").replace("/", "-")
        default_name = f"Transacciones_{safe_name}_{datetime.now().strftime('%Y-%m-%d_%H%M')}.xlsx"
        path, _ = QFileDialog.getSaveFileName(
            self.view, "Guardar detalle", default_name, "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            pd.DataFrame(data).to_excel(path, index=False)
            self.view.show_info("Exportar", f"Archivo guardado en:\n{path}")
        except Exception as exc:
            self.view.show_error("Error al exportar", str(exc))

    # ------------------------------------------------------------------
    # Exportar
    # ------------------------------------------------------------------

    def _export_excel(self):
        if not self._data:
            return

        default_name = f"Reporte_SIA_{datetime.now().strftime('%Y-%m-%d_%H%M')}.xlsx"
        path, _ = QFileDialog.getSaveFileName(
            self.view, "Guardar reporte", default_name, "Excel (*.xlsx)"
        )
        if not path:
            return

        try:
            df = pd.DataFrame(self._data)
            df.to_excel(path, index=False)
            self.view.set_status(f"Reporte exportado: {path}")
            self.view.show_info("Exportar", f"Archivo guardado exitosamente en:\n{path}")
        except Exception as exc:
            self.view.show_error("Error al exportar", str(exc))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_busy(self, busy: bool):
        self._busy = busy
        self.view.set_busy(busy)

    def show(self):
        self.view.show()
