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
        self.view.export_collaborators_requested.connect(self._export_collaborators)
        self.view.report_under_8_requested.connect(self._generate_report_under_8)
        self.view.search_transactions_requested.connect(self._open_search_transactions)
        self.view.user_transactions_requested.connect(self._open_user_transactions)
        self.view.project_transactions_requested.connect(self._open_project_transactions)

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

    def _export_collaborators(self):
        if self._busy:
            return

        default_name = "colaboradores_sia.csv"
        path, _ = QFileDialog.getSaveFileName(
            self.view,
            "Exportar Colaboradores",
            default_name,
            "Archivos CSV (*.csv)"
        )
        if not path:
            return

        self._set_busy(True)
        self.view.set_status("Consultando colaboradores en la base de datos...")

        worker = _Worker(sia_model.get_collaborators)
        worker.signals.finished.connect(
            lambda data, p=path: self._on_export_collaborators_finished(data, p)
        )
        worker.signals.error.connect(self._on_export_collaborators_error)
        self._pool.start(worker)

    def _on_export_collaborators_finished(self, data: list, path: str):
        self._set_busy(False)
        if not data:
            self.view.show_info("Exportar Colaboradores", "No se encontraron colaboradores para exportar.")
            self.view.set_status("Exportación cancelada: sin datos.")
            return

        try:
            df = pd.DataFrame(data)
            df.to_csv(path, index=False, encoding="utf-8-sig")
            self.view.set_status(f"Colaboradores exportados: {path}")
            self.view.show_info("Exportar Colaboradores", f"Archivo guardado exitosamente en:\n{path}")
        except Exception as exc:
            self.view.show_error("Error al exportar", f"No se pudo escribir el archivo CSV:\n{exc}")
            self.view.set_status("Error en la exportación de colaboradores.")

    def _on_export_collaborators_error(self, error: str):
        self._set_busy(False)
        self.view.set_status("Error al consultar colaboradores.")
        self.view.show_error(
            "Error al exportar colaboradores",
            f"Ocurrió un error al obtener la información de la base de datos:\n\n{error}"
        )

    def _generate_report_under_8(self):
        if self._busy:
            return

        start_date, end_date = self.view.get_date_range()
        if start_date > end_date:
            self.view.show_error("Validación", "La fecha inicial no puede ser mayor que la fecha final.")
            return

        default_name = f"Reporte_Horas_Menores_8_{datetime.now().strftime('%Y-%m-%d_%H%M')}.xlsx"
        path, _ = QFileDialog.getSaveFileName(
            self.view,
            "Guardar Reporte Horas (< 8h)",
            default_name,
            "Archivos de Excel (*.xlsx)"
        )
        if not path:
            return

        self._set_busy(True)
        self.view.set_status("Consultando transacciones diarias menores a 8 horas...")

        worker = _Worker(sia_model.get_users_under_8_hours, start_date, end_date)
        worker.signals.finished.connect(
            lambda data, p=path: self._on_report_under_8_finished(data, p)
        )
        worker.signals.error.connect(self._on_report_under_8_error)
        self._pool.start(worker)

    def _on_report_under_8_finished(self, data: list, path: str):
        self._set_busy(False)
        if not data:
            self.view.show_info(
                "Reporte Horas L-V",
                "No se encontraron colaboradores con menos de 8 horas regulares de Lunes a Viernes en las fechas seleccionadas."
            )
            self.view.set_status("Generación de reporte cancelada: sin datos.")
            return

        try:
            df = pd.DataFrame(data)

            # Formatear la fecha
            if "Fecha" in df.columns:
                df["Fecha"] = pd.to_datetime(df["Fecha"]).dt.date

            # Renombrar columnas
            df_rename = df.rename(columns={
                "NomUsuario": "Usuario",
                "CodRamo": "CodRamo",
                "Fecha": "Fecha",
                "HorasRegulares": "Horas Regulares"
            })

            # Guardar en hojas separadas por CodRamo
            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                for ramo, group in df_rename.groupby("CodRamo"):
                    sheet_name = str(ramo).strip()[:30]
                    for char in [":", "\\", "/", "?", "*", "[", "]"]:
                        sheet_name = sheet_name.replace(char, "")
                    if not sheet_name:
                        sheet_name = "Sin_Ramo"
                    group.to_excel(writer, sheet_name=sheet_name, index=False)

            self.view.set_status(f"Reporte de Horas L-V generado: {path}")
            self.view.show_info("Reporte Horas L-V", f"Reporte guardado exitosamente en:\n{path}")
        except Exception as exc:
            self.view.show_error("Error al generar reporte", f"No se pudo escribir el archivo Excel:\n{exc}")
            self.view.set_status("Error en la generación del reporte.")

    def _on_report_under_8_error(self, error: str):
        self._set_busy(False)
        self.view.set_status("Error al consultar reporte de horas.")
        self.view.show_error(
            "Error al generar reporte",
            f"Ocurrió un error al obtener la información de la base de datos:\n\n{error}"
        )

    def _open_search_transactions(self):
        from view.search_transactions_dialog import SearchTransactionsDialog
        start_date, end_date = self.view.date_start.date(), self.view.date_end.date()
        
        dialog = SearchTransactionsDialog(start_date, end_date, self.view)
        dialog.search_requested.connect(self._run_transactions_search)
        dialog.export_requested.connect(self._export_search_results)
        self._search_dialog = dialog
        dialog.exec()

    def _run_transactions_search(self, username: str, start_date, end_date):
        self._search_dialog.set_busy(True)
        worker = _Worker(sia_model.search_user_transactions, username, start_date, end_date)
        worker.signals.finished.connect(self._on_search_finished)
        worker.signals.error.connect(self._on_search_error)
        self._pool.start(worker)

    def _on_search_finished(self, data: list):
        if hasattr(self, "_search_dialog") and self._search_dialog.isVisible():
            self._search_dialog.display_results(data)
            self._search_dialog.set_busy(False)

    def _on_search_error(self, error: str):
        if hasattr(self, "_search_dialog") and self._search_dialog.isVisible():
            self._search_dialog.set_busy(False)
            self.view.show_error("Error de búsqueda", f"Ocurrió un error al consultar:\n\n{error}")

    def _export_search_results(self, data: list):
        default_name = f"Busqueda_Transacciones_{datetime.now().strftime('%Y-%m-%d_%H%M')}.xlsx"
        path, _ = QFileDialog.getSaveFileName(
            self.view, "Guardar Resultados de Búsqueda", default_name, "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            df = pd.DataFrame(data)
            if "Fecha" in df.columns:
                df["Fecha"] = pd.to_datetime(df["Fecha"]).dt.date
            
            # Reordenar y renombrar columnas para que se exporte idéntico a la tabla
            columns_map = {
                "NomUsuario": "Usuario",
                "CodProyecto": "Proyecto",
                "DescProyecto": "Descripción Proyecto",
                "HoraRegular": "Hora Regular",
                "HoraExtra": "Hora Extra",
                "HoraComp": "Hora Comp",
                "Fecha": "Fecha"
            }
            actual_cols = [c for c in columns_map.keys() if c in df.columns]
            df = df[actual_cols].rename(columns=columns_map)
            
            df.to_excel(path, index=False)
            self.view.show_info("Exportar", f"Archivo guardado exitosamente en:\n{path}")
        except Exception as exc:
            self.view.show_error("Error al exportar", str(exc))

    # ------------------------------------------------------------------
    # Transacciones por Empleado (CodRamo → Usuario)
    # ------------------------------------------------------------------

    def _open_user_transactions(self):
        if self._busy:
            return
        self._set_busy(True)
        self.view.set_status("Cargando ramos de empleados…")
        worker = _Worker(sia_model.get_user_ramos)
        worker.signals.finished.connect(self._on_user_ramos_loaded)
        worker.signals.error.connect(self._on_user_transactions_error)
        self._pool.start(worker)

    def _on_user_ramos_loaded(self, ramos: list):
        self._set_busy(False)
        if not ramos:
            self.view.set_status("No se encontraron ramos en tblUsuarios.")
            self.view.show_info(
                "Transacciones por Empleado",
                "No se encontraron ramos activos en tblUsuarios."
            )
            return
        self.view.set_status(f"{len(ramos)} ramos cargados.")

        from view.user_transactions_dialog import UserTransactionsDialog
        start_date = self.view.date_start.date()
        end_date = self.view.date_end.date()

        dialog = UserTransactionsDialog(ramos, start_date, end_date, self.view)
        dialog.ramo_changed.connect(self._load_users_by_ramo)
        dialog.search_requested.connect(self._run_user_transactions_query)
        dialog.export_requested.connect(self._export_user_transactions)
        self._user_trans_dialog = dialog
        dialog.exec()

    def _load_users_by_ramo(self, cod_ramo: str):
        worker = _Worker(sia_model.get_users_by_ramo, cod_ramo)
        worker.signals.finished.connect(self._on_users_by_ramo_loaded)
        worker.signals.error.connect(self._on_user_transactions_error)
        self._pool.start(worker)

    def _on_users_by_ramo_loaded(self, users: list):
        if hasattr(self, "_user_trans_dialog") and self._user_trans_dialog.isVisible():
            self._user_trans_dialog.set_users(users)

    def _run_user_transactions_query(self, ip: str, nom_usuario: str, start_date, end_date):
        self._user_trans_dialog.set_busy(True)
        worker = _Worker(sia_model.get_all_transactions_by_ip, ip, start_date, end_date)
        worker.signals.finished.connect(self._on_user_transactions_finished)
        worker.signals.error.connect(self._on_user_transactions_query_error)
        self._pool.start(worker)

    def _on_user_transactions_finished(self, data: list):
        if hasattr(self, "_user_trans_dialog") and self._user_trans_dialog.isVisible():
            self._user_trans_dialog.display_results(data)
            self._user_trans_dialog.set_busy(False)

    def _on_user_transactions_query_error(self, error: str):
        if hasattr(self, "_user_trans_dialog") and self._user_trans_dialog.isVisible():
            self._user_trans_dialog.set_busy(False)
        self.view.show_error(
            "Error de consulta",
            f"Ocurrió un error al consultar las transacciones del empleado:\n\n{error}"
        )

    def _on_user_transactions_error(self, error: str):
        self._set_busy(False)
        self.view.set_status("Error al cargar datos de empleados.")
        self.view.show_error(
            "Error",
            f"No se pudo cargar la información de empleados:\n\n{error}"
        )

    def _export_user_transactions(self, data: list, nom_usuario: str):
        if not data:
            return
        safe_name = nom_usuario.strip().replace(" ", "_").replace(",", "").replace("/", "-")
        if not safe_name:
            safe_name = "empleado"
        default_name = f"Transacciones_{safe_name}_{datetime.now().strftime('%Y-%m-%d_%H%M')}.xlsx"
        path, _ = QFileDialog.getSaveFileName(
            self.view, "Guardar transacciones del empleado", default_name, "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            df = pd.DataFrame(data)
            if "Fecha" in df.columns:
                df["Fecha"] = pd.to_datetime(df["Fecha"]).dt.date
            if "FechaCreacion" in df.columns:
                df["FechaCreacion"] = pd.to_datetime(df["FechaCreacion"])
            df.to_excel(path, index=False)
            self.view.show_info("Exportar", f"Archivo guardado exitosamente en:\n{path}")
        except Exception as exc:
            self.view.show_error("Error al exportar", str(exc))

    # ------------------------------------------------------------------
    # Transacciones por Proyecto (CodProyecto / SIA)
    # ------------------------------------------------------------------

    def _open_project_transactions(self):
        from view.project_transactions_dialog import ProjectTransactionsDialog
        start_date, end_date = self.view.date_start.date(), self.view.date_end.date()

        dialog = ProjectTransactionsDialog(start_date, end_date, self.view)
        dialog.search_requested.connect(self._run_project_transactions_search)
        dialog.export_requested.connect(self._export_project_search_results)
        self._project_dialog = dialog
        dialog.exec()

    def _run_project_transactions_search(self, cod_proyecto: str, start_date, end_date):
        self._project_dialog.set_busy(True)
        worker = _Worker(sia_model.search_project_transactions, cod_proyecto, start_date, end_date)
        worker.signals.finished.connect(self._on_project_search_finished)
        worker.signals.error.connect(self._on_project_search_error)
        self._pool.start(worker)

    def _on_project_search_finished(self, data: list):
        if hasattr(self, "_project_dialog") and self._project_dialog.isVisible():
            self._project_dialog.display_results(data)
            self._project_dialog.set_busy(False)

    def _on_project_search_error(self, error: str):
        if hasattr(self, "_project_dialog") and self._project_dialog.isVisible():
            self._project_dialog.set_busy(False)
        self.view.show_error("Error de búsqueda", f"Ocurrió un error al consultar:\n\n{error}")

    def _export_project_search_results(self, data: list, fmt: str):
        if not data:
            return
        is_csv = fmt.lower() == "csv"
        ext = "csv" if is_csv else "xlsx"
        file_filter = "CSV (*.csv)" if is_csv else "Excel (*.xlsx)"
        default_name = f"Transacciones_Proyecto_{datetime.now().strftime('%Y-%m-%d_%H%M')}.{ext}"
        path, _ = QFileDialog.getSaveFileName(
            self.view, "Guardar Transacciones por Proyecto", default_name, file_filter
        )
        if not path:
            return
        try:
            df = pd.DataFrame(data)
            if "Fecha" in df.columns:
                df["Fecha"] = pd.to_datetime(df["Fecha"]).dt.date

            columns_map = {
                "Fecha": "Fecha",
                "NomUsuario": "Usuario",
                "CodProyecto": "Proyecto (SIA)",
                "DescProyecto": "Descripción Proyecto",
                "CodRamo": "CodRamo Emp.",
                "HoraRegular": "Hora Regular",
                "HoraExtra": "Hora Extra",
                "HoraComp": "Hora Comp",
            }
            actual_cols = [c for c in columns_map.keys() if c in df.columns]
            df = df[actual_cols].rename(columns=columns_map)

            if is_csv:
                df.to_csv(path, index=False, encoding="utf-8-sig")
            else:
                df.to_excel(path, index=False)
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
