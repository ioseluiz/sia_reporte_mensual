from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QDateEdit, QPushButton, QListWidget, QListWidgetItem,
    QStatusBar, QFrame, QAbstractItemView, QHeaderView,
    QMessageBox, QSizePolicy, QLineEdit, QTableView, QComboBox,
)
from PyQt6.QtGui import QFont, QStandardItemModel, QStandardItem
from PyQt6.QtCore import Qt, QDate, QSortFilterProxyModel, QRegularExpression, pyqtSignal


class _MultiColumnProxy(QSortFilterProxyModel):
    """
    Filtro combinado:
    - Texto libre (cualquier columna, case-insensitive).
    - Filtros exactos por columna (para los combos Oracle).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._col_filters: dict[str, str] = {}

    def set_col_filter(self, col_name: str, value: str):
        """Aplica un filtro de igualdad exacta a la columna col_name. value='' desactiva."""
        self._col_filters[col_name] = value
        self.invalidateFilter()

    def clear_col_filters(self):
        self._col_filters.clear()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        model = self.sourceModel()

        # Filtros exactos por columna
        for col_name, value in self._col_filters.items():
            if not value:
                continue
            for col in range(model.columnCount(source_parent)):
                header = model.horizontalHeaderItem(col)
                if header and header.text() == col_name:
                    idx = model.index(source_row, col, source_parent)
                    text = model.data(idx, Qt.ItemDataRole.DisplayRole) or ""
                    if text != value:
                        return False
                    break

        # Filtro de texto libre (cualquier columna)
        rx = self.filterRegularExpression()
        if not rx.pattern():
            return True
        for col in range(model.columnCount(source_parent)):
            idx = model.index(source_row, col, source_parent)
            text = model.data(idx, Qt.ItemDataRole.DisplayRole) or ""
            if rx.match(text).hasMatch():
                return True
        return False


class MainWindow(QMainWindow):
    settings_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SIA - Reporte Mensual")
        self.setMinimumSize(980, 700)
        self._model = QStandardItemModel()
        self._proxy = _MultiColumnProxy()
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._raw_data: list[dict] = []
        self._setup_ui()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _setup_ui(self):
        self._build_menu_bar()

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 8)
        root.setSpacing(10)

        root.addWidget(self._build_form_panel())
        root.addWidget(self._build_results_panel(), stretch=1)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def _build_menu_bar(self):
        config_menu = self.menuBar().addMenu("Configuración")
        action_conn = config_menu.addAction("Conexión a base de datos…")
        action_conn.triggered.connect(self.settings_requested.emit)

    def _build_form_panel(self) -> QFrame:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(frame)
        layout.setSpacing(10)

        # --- Fechas ---
        date_row = QHBoxLayout()
        date_row.addWidget(QLabel("Fecha inicial:"))
        self.date_start = QDateEdit()
        self.date_start.setCalendarPopup(True)
        today = QDate.currentDate()
        self.date_start.setDate(QDate(today.year(), today.month(), 1))
        self.date_start.setDisplayFormat("dd/MM/yyyy")
        date_row.addWidget(self.date_start)

        date_row.addSpacing(24)
        date_row.addWidget(QLabel("Fecha final:"))
        self.date_end = QDateEdit()
        self.date_end.setCalendarPopup(True)
        self.date_end.setDate(today)
        self.date_end.setDisplayFormat("dd/MM/yyyy")
        date_row.addWidget(self.date_end)
        date_row.addStretch()
        layout.addLayout(date_row)

        # --- Ramos ---
        ramos_header = QHBoxLayout()
        ramos_header.addWidget(QLabel("CodRamos:"))
        ramos_header.addStretch()
        self.btn_select_all = QPushButton("Seleccionar todo")
        self.btn_select_all.setFixedWidth(140)
        self.btn_clear_all = QPushButton("Limpiar selección")
        self.btn_clear_all.setFixedWidth(140)
        self.btn_reload_ramos = QPushButton("Recargar desde BD")
        self.btn_reload_ramos.setFixedWidth(150)
        ramos_header.addWidget(self.btn_select_all)
        ramos_header.addWidget(self.btn_clear_all)
        ramos_header.addSpacing(16)
        ramos_header.addWidget(self.btn_reload_ramos)
        layout.addLayout(ramos_header)

        self.ramos_list = QListWidget()
        self.ramos_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.ramos_list.setFlow(QListWidget.Flow.LeftToRight)
        self.ramos_list.setWrapping(True)
        self.ramos_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.ramos_list.setFixedHeight(110)
        self.ramos_list.setSpacing(4)
        layout.addWidget(self.ramos_list)

        # --- Botones de acción ---
        action_row = QHBoxLayout()
        self.btn_query = QPushButton("Consultar")
        bold = QFont()
        bold.setBold(True)
        self.btn_query.setFont(bold)
        self.btn_query.setFixedHeight(36)
        self.btn_query.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.btn_export = QPushButton("Exportar a Excel")
        self.btn_export.setFixedHeight(36)
        self.btn_export.setEnabled(False)

        action_row.addWidget(self.btn_query)
        action_row.addStretch()
        action_row.addWidget(self.btn_export)
        layout.addLayout(action_row)

        return frame

    def _build_results_panel(self) -> QFrame:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # --- Combos Oracle (filtro en cascada) ---
        oracle_row = QHBoxLayout()
        oracle_row.addWidget(QLabel("Proyecto Oracle:"))
        self.cmb_oracle_proyecto = QComboBox()
        self.cmb_oracle_proyecto.setMinimumWidth(160)
        self.cmb_oracle_proyecto.setEnabled(False)
        oracle_row.addWidget(self.cmb_oracle_proyecto)
        oracle_row.addSpacing(20)
        oracle_row.addWidget(QLabel("Subtarea Oracle:"))
        self.cmb_oracle_subtarea = QComboBox()
        self.cmb_oracle_subtarea.setMinimumWidth(160)
        self.cmb_oracle_subtarea.setEnabled(False)
        oracle_row.addWidget(self.cmb_oracle_subtarea)
        oracle_row.addStretch()
        self.cmb_oracle_proyecto.currentTextChanged.connect(self._on_oracle_proyecto_changed)
        self.cmb_oracle_subtarea.currentTextChanged.connect(self._on_oracle_subtarea_changed)
        layout.addLayout(oracle_row)

        # --- Barra de filtro de texto ---
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filtrar:"))
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Escriba para filtrar por cualquier columna…")
        self.filter_input.setClearButtonEnabled(True)
        self.filter_input.textChanged.connect(self._apply_filter)
        filter_row.addWidget(self.filter_input)
        layout.addLayout(filter_row)

        # --- Etiqueta de resumen ---
        summary_row = QHBoxLayout()
        self.lbl_results = QLabel("Sin resultados")
        self.lbl_filtered = QLabel("")
        self.lbl_filtered.setAlignment(Qt.AlignmentFlag.AlignRight)
        summary_row.addWidget(self.lbl_results)
        summary_row.addStretch()
        summary_row.addWidget(self.lbl_filtered)
        layout.addLayout(summary_row)

        # --- Tabla ---
        self.table = QTableView()
        self.table.setModel(self._proxy)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        self.table.setToolTip("Doble clic en una fila para ver el detalle de sus transacciones")
        layout.addWidget(self.table)

        return frame

    def _on_oracle_proyecto_changed(self, text: str):
        valor = "" if text == "(Todos)" else text
        self._proxy.set_col_filter("CodProyectoOracle", valor)
        self._repopulate_subtarea(valor)
        self._proxy.set_col_filter("CodSubtareaOracle", "")
        self._update_summary_labels()

    def _on_oracle_subtarea_changed(self, text: str):
        valor = "" if text == "(Todos)" else text
        self._proxy.set_col_filter("CodSubtareaOracle", valor)
        self._update_summary_labels()

    def _repopulate_subtarea(self, oracle_proyecto: str):
        subtareas = sorted({
            str(r.get("CodSubtareaOracle") or "")
            for r in self._raw_data
            if (not oracle_proyecto or str(r.get("CodProyectoOracle") or "") == oracle_proyecto)
        } - {""})
        self.cmb_oracle_subtarea.blockSignals(True)
        self.cmb_oracle_subtarea.clear()
        self.cmb_oracle_subtarea.addItem("(Todos)")
        self.cmb_oracle_subtarea.addItems(subtareas)
        self.cmb_oracle_subtarea.blockSignals(False)

    def _populate_oracle_combos(self, data: list[dict]):
        proyectos = sorted({str(r.get("CodProyectoOracle") or "") for r in data} - {""})
        self.cmb_oracle_proyecto.blockSignals(True)
        self.cmb_oracle_proyecto.clear()
        self.cmb_oracle_proyecto.addItem("(Todos)")
        self.cmb_oracle_proyecto.addItems(proyectos)
        self.cmb_oracle_proyecto.setEnabled(True)
        self.cmb_oracle_proyecto.blockSignals(False)
        self._repopulate_subtarea("")
        self.cmb_oracle_subtarea.setEnabled(True)

    def _reset_oracle_combos(self):
        for cmb in (self.cmb_oracle_proyecto, self.cmb_oracle_subtarea):
            cmb.blockSignals(True)
            cmb.clear()
            cmb.setEnabled(False)
            cmb.blockSignals(False)

    def _apply_filter(self, text: str):
        escaped = QRegularExpression.escape(text)
        self._proxy.setFilterRegularExpression(
            QRegularExpression(escaped, QRegularExpression.PatternOption.CaseInsensitiveOption)
        )
        self._update_summary_labels()

    def _horas_col_index(self) -> int:
        for col in range(self._model.columnCount()):
            header = self._model.horizontalHeaderItem(col)
            if header and header.text() == "TotalHoras":
                return col
        return -1

    def _sum_visible_horas(self) -> float:
        col = self._horas_col_index()
        if col < 0:
            return 0.0
        total = 0.0
        for row in range(self._proxy.rowCount()):
            text = self._proxy.data(self._proxy.index(row, col), Qt.ItemDataRole.DisplayRole) or "0"
            try:
                total += float(str(text).replace(",", "."))
            except ValueError:
                pass
        return total

    def _update_summary_labels(self):
        total_rows = self._model.rowCount()
        visible_rows = self._proxy.rowCount()
        if total_rows == 0:
            self.lbl_filtered.setText("")
            return
        visible_horas = self._sum_visible_horas()
        self.lbl_results.setText(
            f"{visible_rows} registros  |  Total horas: {visible_horas:,.2f}"
        )
        self.lbl_filtered.setText(
            f"Mostrando {visible_rows} de {total_rows}" if visible_rows < total_rows else ""
        )

    # ------------------------------------------------------------------
    # Métodos públicos (usados por el Controller)
    # ------------------------------------------------------------------

    def get_row_data_at(self, proxy_index) -> dict:
        """Devuelve los datos de la fila clickeada (mapeando a través del proxy)."""
        source_index = self._proxy.mapToSource(proxy_index)
        row = source_index.row()
        if row < 0:
            return {}
        result = {}
        for col in range(self._model.columnCount()):
            header = self._model.horizontalHeaderItem(col)
            col_name = header.text() if header else str(col)
            item = self._model.item(row, col)
            result[col_name] = item.text() if item else ""
        return result

    def set_ramos(self, ramos: list[str]):
        self.ramos_list.clear()
        for ramo in ramos:
            item = QListWidgetItem(f"  {ramo}  ")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.ramos_list.addItem(item)

    def get_selected_ramos(self) -> list[str]:
        return [
            self.ramos_list.item(i).text().strip()
            for i in range(self.ramos_list.count())
            if self.ramos_list.item(i).checkState() == Qt.CheckState.Checked
        ]

    def select_all_ramos(self):
        for i in range(self.ramos_list.count()):
            self.ramos_list.item(i).setCheckState(Qt.CheckState.Checked)

    def clear_all_ramos(self):
        for i in range(self.ramos_list.count()):
            self.ramos_list.item(i).setCheckState(Qt.CheckState.Unchecked)

    def get_date_range(self) -> tuple:
        return (
            self.date_start.date().toPyDate(),
            self.date_end.date().toPyDate(),
        )

    def display_results(self, data: list[dict]):
        self._raw_data = data
        self._model.clear()
        self._proxy.clear_col_filters()
        self.filter_input.blockSignals(True)
        self.filter_input.clear()
        self.filter_input.blockSignals(False)
        self._proxy.setFilterRegularExpression(QRegularExpression(""))

        if not data:
            self.lbl_results.setText("La consulta no devolvió resultados.")
            self.lbl_filtered.setText("")
            self.btn_export.setEnabled(False)
            self._reset_oracle_combos()
            return

        columns = list(data[0].keys())
        self._model.setHorizontalHeaderLabels(columns)

        for row in data:
            items = []
            for col in columns:
                val = row[col]
                text = "" if val is None else str(val)
                item = QStandardItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setEditable(False)
                items.append(item)
            self._model.appendRow(items)

        self._populate_oracle_combos(data)
        self._update_summary_labels()
        self.btn_export.setEnabled(True)

    def set_busy(self, busy: bool):
        self.btn_query.setEnabled(not busy)
        self.btn_reload_ramos.setEnabled(not busy)
        if busy:
            self.btn_export.setEnabled(False)

    def set_status(self, message: str):
        self.status_bar.showMessage(message)

    def show_error(self, title: str, message: str):
        QMessageBox.critical(self, title, message)

    def show_info(self, title: str, message: str):
        QMessageBox.information(self, title, message)
