from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableView, QPushButton, QHeaderView, QAbstractItemView,
    QMessageBox, QProgressBar, QApplication, QCheckBox,
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QFont, QCursor
from PyQt6.QtCore import Qt, pyqtSignal, QRegularExpression

from .main_window import _MultiColumnProxy


class ProjectsDialog(QDialog):
    """Listado general de proyectos con doble-click a integrantes."""

    load_requested = pyqtSignal(bool)                # (only_active,)
    export_requested = pyqtSignal(list)
    members_requested = pyqtSignal(str, str)         # (cod_proyecto, nom_proyecto)

    _COLUMNS = [
        ("CodProyecto", "Cod. Proyecto"),
        ("NomProyecto", "Nombre"),
        ("CodRamo", "Ramo"),
        ("CodProyectoOracle", "Oracle"),
        ("FechaRec", "Fecha Recepción"),
        ("NumIntegrantes", "# Integr."),
        ("Abierto", "Abierto"),
        ("ProyectoActivo", "Activo"),
    ]
    _BOOL_KEYS = {"Abierto", "ProyectoActivo"}
    _DATE_KEYS = {"FechaRec"}
    _INT_KEYS = {"NumIntegrantes"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Listado de Proyectos")
        self.setMinimumSize(1050, 620)
        self.resize(1160, 700)
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

        header = QHBoxLayout()
        title = QLabel("Proyectos (doble-click en una fila para ver integrantes)")
        bold = QFont()
        bold.setBold(True)
        title.setFont(bold)
        header.addWidget(title)
        header.addStretch()
        self.chk_solo_activos = QCheckBox("Solo proyectos activos")
        self.chk_solo_activos.setChecked(True)
        self.chk_solo_activos.stateChanged.connect(self._on_filter_toggled)
        header.addWidget(self.chk_solo_activos)
        self.btn_reload = QPushButton("Recargar")
        self.btn_reload.setFixedWidth(120)
        self.btn_reload.clicked.connect(
            lambda: self.load_requested.emit(self.chk_solo_activos.isChecked())
        )
        header.addWidget(self.btn_reload)
        layout.addLayout(header)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filtrar:"))
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText(
            "Escriba para filtrar por proyecto, nombre, ramo u Oracle..."
        )
        self.filter_input.setClearButtonEnabled(True)
        self.filter_input.textChanged.connect(self._apply_filter)
        self.filter_input.setEnabled(False)
        filter_row.addWidget(self.filter_input)
        layout.addLayout(filter_row)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        summary_row = QHBoxLayout()
        self.lbl_summary = QLabel("Cargando proyectos…")
        self.lbl_filtered = QLabel("")
        self.lbl_filtered.setAlignment(Qt.AlignmentFlag.AlignRight)
        summary_row.addWidget(self.lbl_summary)
        summary_row.addStretch()
        summary_row.addWidget(self.lbl_filtered)
        layout.addLayout(summary_row)

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

        btn_row = QHBoxLayout()
        self.btn_export = QPushButton("Exportar a Excel")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._on_export_clicked)
        self.btn_members = QPushButton("Ver Integrantes")
        self.btn_members.setEnabled(False)
        self.btn_members.clicked.connect(self._emit_members_of_selected)
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_export)
        btn_row.addWidget(self.btn_members)
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    def _on_filter_toggled(self, *_):
        self.load_requested.emit(self.chk_solo_activos.isChecked())

    def _on_export_clicked(self):
        if self._data:
            self.export_requested.emit(self._data)

    def _emit_members_of_selected(self):
        idx = self.table.currentIndex()
        if idx.isValid():
            self._emit_members_at(idx)

    def _on_row_double_clicked(self, index):
        self._emit_members_at(index)

    def _emit_members_at(self, proxy_index):
        source_row = self._proxy.mapToSource(proxy_index).row()
        cod_item = self._model.item(source_row, 0)
        nom_item = self._model.item(source_row, 1)
        if cod_item is None:
            return
        cod = cod_item.text().strip()
        nom = nom_item.text() if nom_item is not None else ""
        if cod:
            self.members_requested.emit(cod, nom)

    def set_status(self, text: str):
        self.lbl_summary.setText(text)

    def set_busy(self, busy: bool, status_text: str | None = None):
        self.btn_reload.setEnabled(not busy)
        self.chk_solo_activos.setEnabled(not busy)
        self.table.setEnabled(not busy)
        has_data = len(self._data) > 0
        self.filter_input.setEnabled(not busy and has_data)
        self.btn_export.setEnabled(not busy and has_data)
        self.btn_members.setEnabled(not busy and has_data)
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
            self.lbl_summary.setText("No se encontraron proyectos con el filtro seleccionado.")
            self.lbl_filtered.setText("")
            self.filter_input.setEnabled(False)
            self.btn_export.setEnabled(False)
            self.btn_members.setEnabled(False)
            return

        actual = [(k, label) for k, label in self._COLUMNS if k in data[0]]
        self._model.setHorizontalHeaderLabels([label for _, label in actual])

        align_center = Qt.AlignmentFlag.AlignCenter
        align_right = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        center_keys = (
            {"CodProyecto", "CodRamo", "CodProyectoOracle"}
            | self._BOOL_KEYS | self._DATE_KEYS
        )

        self._model.setRowCount(len(data))
        for r_idx, row in enumerate(data):
            for c_idx, (key, _) in enumerate(actual):
                val = row.get(key)
                if key in self._BOOL_KEYS:
                    text = "" if val is None else ("Sí" if val else "No")
                    item = QStandardItem(text)
                    item.setData(1 if val else 0, Qt.ItemDataRole.UserRole)
                elif key in self._DATE_KEYS:
                    if val is None:
                        item = QStandardItem("")
                    else:
                        text = val.strftime("%Y-%m-%d") if hasattr(val, "strftime") else str(val)
                        item = QStandardItem(text)
                elif key in self._INT_KEYS:
                    try:
                        ival = int(val or 0)
                    except (TypeError, ValueError):
                        ival = 0
                    item = QStandardItem(str(ival))
                    item.setData(ival, Qt.ItemDataRole.UserRole)
                    item.setTextAlignment(align_right)
                elif val is None:
                    item = QStandardItem("")
                else:
                    item = QStandardItem(str(val))
                if key in center_keys:
                    item.setTextAlignment(align_center)
                item.setEditable(False)
                self._model.setItem(r_idx, c_idx, item)

        self._model.blockSignals(False)
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterRegularExpression(QRegularExpression(""))
        self.table.setModel(self._proxy)
        self.table.setUpdatesEnabled(True)
        self.table.setSortingEnabled(True)

        header = self.table.horizontalHeader()
        for i, (key, _) in enumerate(actual):
            if key == "NomProyecto":
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)

        modo = "activos" if self.chk_solo_activos.isChecked() else "todos"
        self.lbl_summary.setText(
            f"{len(data)} proyecto(s) ({modo}). Doble-click en una fila para ver integrantes."
        )
        self.lbl_filtered.setText("")
        self.filter_input.setEnabled(True)
        self.btn_export.setEnabled(True)
        self.btn_members.setEnabled(True)

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

    def show_error(self, title: str, message: str):
        QMessageBox.critical(self, title, message)

    def show_info(self, title: str, message: str):
        QMessageBox.information(self, title, message)

    def closeEvent(self, event):
        if self._busy_cursor_active:
            QApplication.restoreOverrideCursor()
            self._busy_cursor_active = False
        super().closeEvent(event)
