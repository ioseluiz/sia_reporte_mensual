from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableView, QPushButton, QHeaderView, QAbstractItemView,
    QDateEdit, QFrame, QMessageBox, QComboBox,
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QFont
from PyQt6.QtCore import Qt, QDate, pyqtSignal, QRegularExpression

from .main_window import _MultiColumnProxy


class UserTransactionsDialog(QDialog):
    """
    Diálogo para consultar todas las transacciones de un empleado.
    Selección en cascada: CodRamo (empleado) → Usuario → Consultar.
    """

    ramo_changed = pyqtSignal(str)
    search_requested = pyqtSignal(str, str, object, object)  # ip, nom_usuario, start, end
    export_requested = pyqtSignal(list, str)  # data, nom_usuario

    def __init__(self, ramos: list[str], default_start_date: QDate, default_end_date: QDate, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Transacciones por Empleado")
        self.setMinimumSize(1000, 620)
        self.resize(1100, 680)
        self._data: list[dict] = []
        self._current_nom_usuario: str = ""

        self._model = QStandardItemModel()
        self._proxy = _MultiColumnProxy()
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self._setup_ui(default_start_date, default_end_date)
        self._populate_ramos(ramos)

    def _setup_ui(self, default_start_date: QDate, default_end_date: QDate):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # --- Panel de selección ---
        selection_frame = QFrame()
        selection_frame.setFrameShape(QFrame.Shape.StyledPanel)
        selection_layout = QVBoxLayout(selection_frame)
        selection_layout.setSpacing(8)

        # Fila 1: CodRamo + Usuario
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("CodRamo (empleado):"))
        self.cmb_ramo = QComboBox()
        self.cmb_ramo.setMinimumWidth(140)
        self.cmb_ramo.currentIndexChanged.connect(self._on_ramo_changed)
        row1.addWidget(self.cmb_ramo)

        row1.addSpacing(16)
        row1.addWidget(QLabel("Usuario:"))
        self.cmb_usuario = QComboBox()
        self.cmb_usuario.setMinimumWidth(280)
        self.cmb_usuario.setEnabled(False)
        row1.addWidget(self.cmb_usuario, stretch=1)
        selection_layout.addLayout(row1)

        # Fila 2: Fechas + Buscar
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Fecha inicial:"))
        self.date_start = QDateEdit()
        self.date_start.setCalendarPopup(True)
        self.date_start.setDate(default_start_date)
        self.date_start.setDisplayFormat("dd/MM/yyyy")
        row2.addWidget(self.date_start)

        row2.addSpacing(16)
        row2.addWidget(QLabel("Fecha final:"))
        self.date_end = QDateEdit()
        self.date_end.setCalendarPopup(True)
        self.date_end.setDate(default_end_date)
        self.date_end.setDisplayFormat("dd/MM/yyyy")
        row2.addWidget(self.date_end)

        row2.addStretch()
        self.btn_search = QPushButton("Consultar")
        bold_font = QFont()
        bold_font.setBold(True)
        self.btn_search.setFont(bold_font)
        self.btn_search.setFixedWidth(110)
        self.btn_search.setEnabled(False)
        self.btn_search.clicked.connect(self._on_search_clicked)
        row2.addWidget(self.btn_search)
        selection_layout.addLayout(row2)

        layout.addWidget(selection_frame)

        # --- Filtro rápido ---
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filtrar resultados:"))
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filtrar en cualquier columna…")
        self.filter_input.setClearButtonEnabled(True)
        self.filter_input.textChanged.connect(self._apply_filter)
        self.filter_input.setEnabled(False)
        filter_row.addWidget(self.filter_input)
        layout.addLayout(filter_row)

        # --- Resumen ---
        summary_row = QHBoxLayout()
        self.lbl_summary = QLabel("Seleccione un CodRamo y un usuario para consultar.")
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
        layout.addWidget(self.table)

        # --- Botones inferiores ---
        btn_row = QHBoxLayout()
        self.btn_export = QPushButton("Exportar a Excel")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._on_export_clicked)
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_export)
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Población de combos
    # ------------------------------------------------------------------

    def _populate_ramos(self, ramos: list[str]):
        self.cmb_ramo.blockSignals(True)
        self.cmb_ramo.clear()
        self.cmb_ramo.addItem("(Seleccione un CodRamo)", None)
        for ramo in ramos:
            self.cmb_ramo.addItem(ramo, ramo)
        self.cmb_ramo.blockSignals(False)

    def set_users(self, users: list[dict]):
        """Recibe [{IP, NomUsuario}, ...] desde el controlador y llena el combo de usuarios."""
        self.cmb_usuario.blockSignals(True)
        self.cmb_usuario.clear()
        self.cmb_usuario.addItem("(Seleccione un usuario)", None)
        for u in users:
            ip = u.get("IP", "")
            nom = u.get("NomUsuario", "")
            self.cmb_usuario.addItem(nom, (ip, nom))
        self.cmb_usuario.blockSignals(False)
        self.cmb_usuario.setEnabled(len(users) > 0)
        self.btn_search.setEnabled(False)
        # Conectar solo la primera vez
        try:
            self.cmb_usuario.currentIndexChanged.disconnect(self._on_usuario_changed)
        except TypeError:
            pass
        self.cmb_usuario.currentIndexChanged.connect(self._on_usuario_changed)

    # ------------------------------------------------------------------
    # Eventos
    # ------------------------------------------------------------------

    def _on_ramo_changed(self, index: int):
        ramo = self.cmb_ramo.currentData()
        self.cmb_usuario.clear()
        self.cmb_usuario.setEnabled(False)
        self.btn_search.setEnabled(False)
        if not ramo:
            return
        self.ramo_changed.emit(ramo)

    def _on_usuario_changed(self, index: int):
        data = self.cmb_usuario.currentData()
        self.btn_search.setEnabled(bool(data))

    def _on_search_clicked(self):
        data = self.cmb_usuario.currentData()
        if not data:
            QMessageBox.warning(self, "Validación", "Seleccione un usuario para consultar.")
            return
        ip, nom_usuario = data
        start_date = self.date_start.date().toPyDate()
        end_date = self.date_end.date().toPyDate()
        if start_date > end_date:
            QMessageBox.warning(self, "Validación", "La fecha inicial no puede ser mayor que la fecha final.")
            return
        self._current_nom_usuario = nom_usuario
        self.search_requested.emit(ip, nom_usuario, start_date, end_date)

    def _on_export_clicked(self):
        if self._data:
            self.export_requested.emit(self._data, self._current_nom_usuario)

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

    # ------------------------------------------------------------------
    # API expuesta al controlador
    # ------------------------------------------------------------------

    def set_busy(self, busy: bool):
        self.cmb_ramo.setEnabled(not busy)
        self.cmb_usuario.setEnabled(not busy and self.cmb_usuario.count() > 1)
        self.date_start.setEnabled(not busy)
        self.date_end.setEnabled(not busy)
        self.btn_search.setEnabled(not busy and bool(self.cmb_usuario.currentData()))
        self.filter_input.setEnabled(not busy and len(self._data) > 0)
        self.btn_export.setEnabled(not busy and len(self._data) > 0)

    def display_results(self, data: list[dict]):
        self._data = data
        self._model.clear()
        self.filter_input.blockSignals(True)
        self.filter_input.clear()
        self.filter_input.blockSignals(False)
        self._proxy.setFilterRegularExpression(QRegularExpression(""))

        if not data:
            self.lbl_summary.setText(
                f"No se encontraron transacciones para {self._current_nom_usuario} "
                "en el rango de fechas."
            )
            self.lbl_filtered.setText("")
            self.filter_input.setEnabled(False)
            self.btn_export.setEnabled(False)
            return

        columns = list(data[0].keys())
        self._model.setHorizontalHeaderLabels(columns)

        for row in data:
            items = []
            for col in columns:
                val = row[col]
                if val is None:
                    text = ""
                elif col == "Fecha":
                    try:
                        text = val.strftime("%d/%m/%Y")
                    except AttributeError:
                        text = str(val)
                elif col == "FechaCreacion":
                    try:
                        text = val.strftime("%d/%m/%Y %H:%M")
                    except AttributeError:
                        text = str(val)
                else:
                    text = str(val)
                item = QStandardItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setEditable(False)
                items.append(item)
            self._model.appendRow(items)

        total_reg = sum(float(r.get("HoraRegular") or 0) for r in data)
        total_ext = sum(float(r.get("HoraExtra") or 0) for r in data)
        total_comp = sum(float(r.get("HoraComp") or 0) for r in data)

        self.lbl_summary.setText(
            f"{self._current_nom_usuario} — {len(data)} transacciones  |  "
            f"Regulares: {total_reg:,.2f}  |  "
            f"Extras: {total_ext:,.2f}  |  "
            f"Compensadas: {total_comp:,.2f}"
        )
        self.lbl_filtered.setText("")
        self.filter_input.setEnabled(True)
        self.btn_export.setEnabled(True)
        self.table.resizeColumnsToContents()
