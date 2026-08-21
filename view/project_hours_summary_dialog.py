from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableView, QPushButton, QHeaderView, QAbstractItemView,
    QFrame, QMessageBox, QListWidget, QListWidgetItem, QProgressBar,
    QApplication,
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QFont, QCursor
from PyQt6.QtCore import Qt, pyqtSignal, QRegularExpression

from .main_window import _MultiColumnProxy


class ProjectHoursSummaryDialog(QDialog):
    query_requested = pyqtSignal(list)
    load_ramos_requested = pyqtSignal()
    detail_requested = pyqtSignal(str)
    export_requested = pyqtSignal(list, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Resumen de Horas por Proyecto (SIA)")
        self.setMinimumSize(1100, 650)
        self.resize(1180, 720)
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

        # Header de ramos
        ramos_header = QHBoxLayout()
        ramos_header.addWidget(QLabel("CodRamos del proyecto:"))
        ramos_header.addStretch()
        self.btn_select_all = QPushButton("Seleccionar todo")
        self.btn_select_all.setFixedWidth(140)
        self.btn_select_all.clicked.connect(self._select_all_ramos)
        self.btn_clear_all = QPushButton("Limpiar selección")
        self.btn_clear_all.setFixedWidth(140)
        self.btn_clear_all.clicked.connect(self._clear_all_ramos)
        self.btn_reload_ramos = QPushButton("Recargar desde BD")
        self.btn_reload_ramos.setFixedWidth(150)
        self.btn_reload_ramos.clicked.connect(self.load_ramos_requested.emit)
        ramos_header.addWidget(self.btn_select_all)
        ramos_header.addWidget(self.btn_clear_all)
        ramos_header.addSpacing(16)
        ramos_header.addWidget(self.btn_reload_ramos)
        params_layout.addLayout(ramos_header)

        # Lista de ramos
        self.ramos_list = QListWidget()
        self.ramos_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.ramos_list.setFlow(QListWidget.Flow.LeftToRight)
        self.ramos_list.setWrapping(True)
        self.ramos_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.ramos_list.setFixedHeight(110)
        self.ramos_list.setSpacing(4)
        params_layout.addWidget(self.ramos_list)

        # Botón consultar
        action_row = QHBoxLayout()
        self.btn_query = QPushButton("Consultar Resumen")
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
        self.filter_input.setPlaceholderText("Escriba para filtrar por CodProyecto, nombre o ramo...")
        self.filter_input.setClearButtonEnabled(True)
        self.filter_input.textChanged.connect(self._apply_filter)
        self.filter_input.setEnabled(False)
        filter_row.addWidget(self.filter_input)
        layout.addLayout(filter_row)

        # --- Barra de progreso (indeterminada, visible solo durante consultas) ---
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # modo indeterminado
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # --- Estado / Resumen ---
        summary_row = QHBoxLayout()
        self.lbl_summary = QLabel("Seleccione uno o más ramos y pulse Consultar. Doble click en una fila para ver el detalle.")
        self.lbl_filtered = QLabel("")
        self.lbl_filtered.setAlignment(Qt.AlignmentFlag.AlignRight)
        summary_row.addWidget(self.lbl_summary)
        summary_row.addStretch()
        summary_row.addWidget(self.lbl_filtered)
        layout.addLayout(summary_row)

        # --- Tabla ---
        self.table = QTableView()
        self.table.setModel(self._proxy)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        self.table.doubleClicked.connect(self._on_row_double_clicked)
        layout.addWidget(self.table)

        # --- Botones ---
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
    # Ramos
    # ------------------------------------------------------------------

    def set_ramos(self, ramos: list[str]):
        self.ramos_list.clear()
        for ramo in ramos:
            item = QListWidgetItem(ramo)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.ramos_list.addItem(item)

    def get_selected_ramos(self) -> list[str]:
        selected = []
        for i in range(self.ramos_list.count()):
            item = self.ramos_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item.text())
        return selected

    def _select_all_ramos(self):
        for i in range(self.ramos_list.count()):
            self.ramos_list.item(i).setCheckState(Qt.CheckState.Checked)

    def _clear_all_ramos(self):
        for i in range(self.ramos_list.count()):
            self.ramos_list.item(i).setCheckState(Qt.CheckState.Unchecked)

    # ------------------------------------------------------------------
    # Query / export / detail
    # ------------------------------------------------------------------

    def _on_query_clicked(self):
        ramos = self.get_selected_ramos()
        if not ramos:
            QMessageBox.warning(self, "Validación", "Seleccione al menos un CodRamo de proyecto.")
            return

        self.query_requested.emit(ramos)

    def _on_export_clicked(self, fmt: str):
        if self._data:
            self.export_requested.emit(self._data, fmt)

    def _on_row_double_clicked(self, index):
        source_index = self._proxy.mapToSource(index)
        row = source_index.row()
        cod_proyecto_item = self._model.item(row, 0)
        if cod_proyecto_item is None:
            return
        self.detail_requested.emit(cod_proyecto_item.text())

    def set_status(self, text: str):
        """Actualiza el mensaje de estado sobre la tabla."""
        self.lbl_summary.setText(text)

    def set_busy(self, busy: bool, status_text: str | None = None):
        self.btn_query.setEnabled(not busy)
        self.btn_reload_ramos.setEnabled(not busy)
        self.btn_select_all.setEnabled(not busy)
        self.btn_clear_all.setEnabled(not busy)
        self.ramos_list.setEnabled(not busy)
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

        # Desconectar completamente proxy y vista para evitar trabajo O(n^2) al insertar
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
            self.lbl_summary.setText("No se encontraron proyectos para los criterios seleccionados.")
            self.lbl_filtered.setText("")
            self.filter_input.setEnabled(False)
            self.btn_export_xlsx.setEnabled(False)
            self.btn_export_csv.setEnabled(False)
            return

        columns = [
            ("CodProyecto", "CodProyecto (SIA)"),
            ("NomProyecto", "Nombre Proyecto"),
            ("CodRamo", "CodRamo"),
            ("TotalHoraRegular", "Hora Regular"),
            ("TotalHoraComp", "Hora Comp"),
            ("TotalHoraExtra", "Hora Extra"),
            ("TotalHoras", "Total"),
        ]
        actual = [(k, label) for k, label in columns if k in data[0]]
        self._model.setHorizontalHeaderLabels([label for _, label in actual])

        numeric_cols = {"TotalHoraRegular", "TotalHoraComp", "TotalHoraExtra", "TotalHoras"}
        align_right = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        align_center = Qt.AlignmentFlag.AlignCenter
        totals = {k: 0.0 for k in numeric_cols}

        # Pre-dimensionar el modelo — evita realloc por cada appendRow
        self._model.setRowCount(len(data))

        for r_idx, row in enumerate(data):
            for c_idx, (key, _) in enumerate(actual):
                val = row[key]
                if key in numeric_cols:
                    try:
                        fval = float(val or 0)
                    except (TypeError, ValueError):
                        fval = 0.0
                    totals[key] += fval
                    item = QStandardItem(f"{fval:,.2f}")
                    item.setData(fval, Qt.ItemDataRole.UserRole)
                    item.setTextAlignment(align_right)
                else:
                    item = QStandardItem("" if val is None else str(val))
                    if key == "CodProyecto" or key == "CodRamo":
                        item.setTextAlignment(align_center)
                item.setEditable(False)
                self._model.setItem(r_idx, c_idx, item)

        # Reconectar proxy y vista, y re-habilitar renderizado
        self._model.blockSignals(False)
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterRegularExpression(QRegularExpression(""))
        self.table.setModel(self._proxy)
        self.table.setUpdatesEnabled(True)
        self.table.setSortingEnabled(True)

        # Anchos fijos razonables para columnas numericas + estirable para NomProyecto
        header = self.table.horizontalHeader()
        for i, (key, _) in enumerate(actual):
            if key == "NomProyecto":
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            elif key in numeric_cols:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
                self.table.setColumnWidth(i, 110)
            else:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
                self.table.setColumnWidth(i, 130)

        self.lbl_summary.setText(
            f"{len(data)} proyectos  |  "
            f"Regulares: {totals['TotalHoraRegular']:,.2f}  |  "
            f"Comp: {totals['TotalHoraComp']:,.2f}  |  "
            f"Extras: {totals['TotalHoraExtra']:,.2f}  |  "
            f"Total: {totals['TotalHoras']:,.2f}  |  "
            f"Doble click en una fila para ver detalle."
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
            "" if visible == total else f"Mostrando {visible} de {total}"
        )
