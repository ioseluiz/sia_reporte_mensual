from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableView, QPushButton, QHeaderView, QAbstractItemView,
    QFrame, QMessageBox, QListWidget, QListWidgetItem, QProgressBar,
    QApplication,
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QFont, QCursor
from PyQt6.QtCore import Qt, pyqtSignal, QRegularExpression

from .main_window import _MultiColumnProxy
from core.fiscal_year import fy_label


class FiscalYearReportDialog(QDialog):
    load_fys_requested = pyqtSignal()
    query_requested = pyqtSignal(list)                # list[int] de FY
    export_requested = pyqtSignal(list, list, str)    # data, fys_seleccionados, fmt

    # Orden y nombres exactos del Excel ejemplo
    COLUMNS = [
        ("SIA", "SIA"),
        ("Proyecto", "Proyecto"),
        ("Cliente", "Cliente"),
        ("Ingeniero", "Ingeniero"),
        ("Sum of HoraRegular", "Sum of HoraRegular"),
        ("Codramo_act2", "Codramo_act2"),
        ("Rol", "Rol"),
        ("Fiscalv2", "Fiscalv2"),
        ("Coordinador", "Coordinador"),
        ("DescCuenta", "DescCuenta"),
    ]
    NUMERIC_COLS = {"Sum of HoraRegular"}
    INTEGER_COLS = {"SIA", "Fiscalv2"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Raw Data por Año Fiscal (SIA)")
        self.setMinimumSize(1200, 650)
        self.resize(1280, 720)
        self._data: list[dict] = []
        self._busy_cursor_active = False

        self._model = QStandardItemModel()
        self._proxy = _MultiColumnProxy()
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # --- Panel de parámetros ---
        params_frame = QFrame()
        params_frame.setFrameShape(QFrame.Shape.StyledPanel)
        params_layout = QVBoxLayout(params_frame)
        params_layout.setSpacing(8)

        fys_header = QHBoxLayout()
        fys_header.addWidget(QLabel("Años fiscales (ACP: octubre → septiembre):"))
        fys_header.addStretch()
        self.btn_select_all = QPushButton("Seleccionar todo")
        self.btn_select_all.setFixedWidth(140)
        self.btn_select_all.clicked.connect(self._select_all_fys)
        self.btn_clear_all = QPushButton("Limpiar selección")
        self.btn_clear_all.setFixedWidth(140)
        self.btn_clear_all.clicked.connect(self._clear_all_fys)
        self.btn_reload_fys = QPushButton("Recargar desde BD")
        self.btn_reload_fys.setFixedWidth(150)
        self.btn_reload_fys.clicked.connect(self.load_fys_requested.emit)
        fys_header.addWidget(self.btn_select_all)
        fys_header.addWidget(self.btn_clear_all)
        fys_header.addSpacing(16)
        fys_header.addWidget(self.btn_reload_fys)
        params_layout.addLayout(fys_header)

        # Lista de años fiscales
        self.fys_list = QListWidget()
        self.fys_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.fys_list.setFlow(QListWidget.Flow.LeftToRight)
        self.fys_list.setWrapping(True)
        self.fys_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.fys_list.setFixedHeight(110)
        self.fys_list.setSpacing(4)
        params_layout.addWidget(self.fys_list)

        action_row = QHBoxLayout()
        self.btn_query = QPushButton("Consultar Reporte")
        bold = QFont()
        bold.setBold(True)
        self.btn_query.setFont(bold)
        self.btn_query.setFixedHeight(36)
        self.btn_query.clicked.connect(self._on_query_clicked)
        action_row.addWidget(self.btn_query)
        action_row.addStretch()
        params_layout.addLayout(action_row)

        layout.addWidget(params_frame)

        # --- Filtro sobre resultados ---
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filtrar resultados:"))
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Escriba para filtrar por SIA, proyecto, ingeniero, ramo, cuenta...")
        self.filter_input.setClearButtonEnabled(True)
        self.filter_input.textChanged.connect(self._apply_filter)
        self.filter_input.setEnabled(False)
        filter_row.addWidget(self.filter_input)
        layout.addLayout(filter_row)

        # Barra de progreso indeterminada
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # Estado / resumen
        summary_row = QHBoxLayout()
        self.lbl_summary = QLabel("Cargando años fiscales…")
        self.lbl_filtered = QLabel("")
        self.lbl_filtered.setAlignment(Qt.AlignmentFlag.AlignRight)
        summary_row.addWidget(self.lbl_summary)
        summary_row.addStretch()
        summary_row.addWidget(self.lbl_filtered)
        layout.addLayout(summary_row)

        # Tabla
        self.table = QTableView()
        self.table.setModel(self._proxy)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)

        # Botones
        btn_row = QHBoxLayout()
        self.btn_export_xlsx = QPushButton("Exportar a Excel")
        self.btn_export_xlsx.setEnabled(False)
        self.btn_export_xlsx.clicked.connect(lambda: self._on_export_clicked("xlsx"))

        self.btn_export_csv = QPushButton("Exportar a CSV")
        self.btn_export_csv.setEnabled(False)
        self.btn_export_csv.clicked.connect(lambda: self._on_export_clicked("csv"))

        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)

        btn_row.addWidget(self.btn_export_xlsx)
        btn_row.addWidget(self.btn_export_csv)
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Años fiscales
    # ------------------------------------------------------------------

    def set_fiscal_years(self, fys: list[int]):
        self.fys_list.clear()
        for fy in fys:
            item = QListWidgetItem(fy_label(int(fy)))
            item.setData(Qt.ItemDataRole.UserRole, int(fy))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.fys_list.addItem(item)

    def get_selected_fys(self) -> list[int]:
        selected = []
        for i in range(self.fys_list.count()):
            item = self.fys_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(int(item.data(Qt.ItemDataRole.UserRole)))
        return selected

    def _select_all_fys(self):
        for i in range(self.fys_list.count()):
            self.fys_list.item(i).setCheckState(Qt.CheckState.Checked)

    def _clear_all_fys(self):
        for i in range(self.fys_list.count()):
            self.fys_list.item(i).setCheckState(Qt.CheckState.Unchecked)

    # ------------------------------------------------------------------
    # Query / export
    # ------------------------------------------------------------------

    def _on_query_clicked(self):
        fys = self.get_selected_fys()
        if not fys:
            QMessageBox.warning(self, "Validación",
                                "Seleccione al menos un año fiscal.")
            return
        self.query_requested.emit(fys)

    def _on_export_clicked(self, fmt: str):
        if not self._data:
            return
        self.export_requested.emit(self._data, self.get_selected_fys(), fmt)

    def set_status(self, text: str):
        self.lbl_summary.setText(text)

    def set_busy(self, busy: bool, status_text: str | None = None):
        self.btn_query.setEnabled(not busy)
        self.btn_reload_fys.setEnabled(not busy)
        self.btn_select_all.setEnabled(not busy)
        self.btn_clear_all.setEnabled(not busy)
        self.fys_list.setEnabled(not busy)
        self.table.setEnabled(not busy)
        has_data = len(self._data) > 0
        self.filter_input.setEnabled(not busy and has_data)
        self.btn_export_xlsx.setEnabled(not busy and has_data)
        self.btn_export_csv.setEnabled(not busy and has_data)

        self.progress.setVisible(busy)
        if status_text is not None:
            self.set_status(status_text)

        if busy and not self._busy_cursor_active:
            QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
            self._busy_cursor_active = True
        elif not busy and self._busy_cursor_active:
            QApplication.restoreOverrideCursor()
            self._busy_cursor_active = False

    def display_results(self, data: list[dict]):
        self._data = data

        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)
        self.table.setModel(None)
        self._proxy.setSourceModel(None)
        self._model.blockSignals(True)
        self._model.clear()
        self.filter_input.blockSignals(True)
        self.filter_input.clear()
        self.filter_input.blockSignals(False)

        if not data:
            self._model.blockSignals(False)
            self._proxy.setSourceModel(self._model)
            self._proxy.setFilterRegularExpression(QRegularExpression(""))
            self.table.setModel(self._proxy)
            self.table.setUpdatesEnabled(True)
            self.table.setSortingEnabled(True)
            self.set_status("No se encontraron registros para los años fiscales seleccionados.")
            self.lbl_filtered.setText("")
            self.filter_input.setEnabled(False)
            self.btn_export_xlsx.setEnabled(False)
            self.btn_export_csv.setEnabled(False)
            return

        actual = [(k, label) for k, label in self.COLUMNS if k in data[0]]
        self._model.setHorizontalHeaderLabels([label for _, label in actual])

        align_right = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        align_center = Qt.AlignmentFlag.AlignCenter
        total_horas = 0.0

        self._model.setRowCount(len(data))

        for r_idx, row in enumerate(data):
            for c_idx, (key, _) in enumerate(actual):
                val = row.get(key)
                if key in self.NUMERIC_COLS:
                    try:
                        fval = float(val or 0)
                    except (TypeError, ValueError):
                        fval = 0.0
                    total_horas += fval
                    item = QStandardItem(f"{fval:,.2f}")
                    item.setData(fval, Qt.ItemDataRole.UserRole)
                    item.setTextAlignment(align_right)
                elif key in self.INTEGER_COLS:
                    if val is None:
                        item = QStandardItem("")
                    else:
                        try:
                            ival = int(val)
                            item = QStandardItem(str(ival))
                            item.setData(ival, Qt.ItemDataRole.UserRole)
                        except (TypeError, ValueError):
                            item = QStandardItem(str(val))
                    item.setTextAlignment(align_center)
                else:
                    item = QStandardItem("" if val is None else str(val))
                item.setEditable(False)
                self._model.setItem(r_idx, c_idx, item)

        self._model.blockSignals(False)
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterRegularExpression(QRegularExpression(""))
        self.table.setModel(self._proxy)
        self.table.setUpdatesEnabled(True)
        self.table.setSortingEnabled(True)

        header = self.table.horizontalHeader()
        wide_cols = {"Proyecto", "DescCuenta"}
        for i, (key, _) in enumerate(actual):
            if key in wide_cols:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            elif key in self.NUMERIC_COLS:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
                self.table.setColumnWidth(i, 140)
            elif key in self.INTEGER_COLS:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
                self.table.setColumnWidth(i, 90)
            else:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
                self.table.setColumnWidth(i, 160)

        self.set_status(
            f"{len(data):,} filas  |  "
            f"Total Horas Regular: {total_horas:,.2f}  |  "
            f"Use el filtro para refinar o exporte el resultado."
        )
        self.lbl_filtered.setText("")
        self.filter_input.setEnabled(True)
        self.btn_export_xlsx.setEnabled(True)
        self.btn_export_csv.setEnabled(True)

    def closeEvent(self, event):
        if self._busy_cursor_active:
            QApplication.restoreOverrideCursor()
            self._busy_cursor_active = False
        super().closeEvent(event)

    def _apply_filter(self, text: str):
        escaped = QRegularExpression.escape(text)
        self._proxy.setFilterRegularExpression(
            QRegularExpression(escaped, QRegularExpression.PatternOption.CaseInsensitiveOption)
        )
        total = self._model.rowCount()
        visible = self._proxy.rowCount()
        self.lbl_filtered.setText(
            "" if visible == total else f"Mostrando {visible:,} de {total:,}"
        )
