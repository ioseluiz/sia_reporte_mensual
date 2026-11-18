from datetime import date

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableView, QPushButton, QHeaderView, QAbstractItemView,
    QMessageBox, QProgressBar, QApplication, QDateEdit, QFrame,
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QFont, QCursor
from PyQt6.QtCore import Qt, pyqtSignal, QRegularExpression, QDate

from .main_window import _MultiColumnProxy


_DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves",
                "Viernes", "Sábado", "Domingo"]


class DiasLibresDialog(QDialog):
    load_requested = pyqtSignal()
    add_requested = pyqtSignal(object, str)      # (date, descripcion)
    delete_requested = pyqtSignal(object)         # (date)
    export_requested = pyqtSignal(list)

    _COLUMNS = [
        ("fecha", "Fecha"),
        ("dia_semana", "Día"),
        ("descripcion", "Descripción"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Días Libres (Feriados)")
        self.setMinimumSize(760, 620)
        self.resize(820, 700)
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

        # --- Encabezado ---
        header = QHBoxLayout()
        title = QLabel("Feriados nacionales (Panamá) utilizados para excluir del reporte <8h")
        bold = QFont()
        bold.setBold(True)
        title.setFont(bold)
        header.addWidget(title)
        header.addStretch()
        self.btn_reload = QPushButton("Recargar")
        self.btn_reload.setFixedWidth(120)
        self.btn_reload.clicked.connect(self.load_requested.emit)
        header.addWidget(self.btn_reload)
        layout.addLayout(header)

        # --- Panel de agregar ---
        add_frame = QFrame()
        add_frame.setFrameShape(QFrame.Shape.StyledPanel)
        add_layout = QHBoxLayout(add_frame)
        add_layout.setContentsMargins(10, 8, 10, 8)
        add_layout.addWidget(QLabel("Fecha:"))
        self.date_add = QDateEdit()
        self.date_add.setCalendarPopup(True)
        self.date_add.setDate(QDate.currentDate())
        self.date_add.setDisplayFormat("dd/MM/yyyy")
        add_layout.addWidget(self.date_add)
        add_layout.addSpacing(12)
        add_layout.addWidget(QLabel("Descripción:"))
        self.desc_add = QLineEdit()
        self.desc_add.setPlaceholderText("ej. Día de los Mártires")
        add_layout.addWidget(self.desc_add, stretch=1)
        self.btn_add = QPushButton("Agregar")
        self.btn_add.setFixedWidth(100)
        self.btn_add.clicked.connect(self._on_add_clicked)
        add_layout.addWidget(self.btn_add)
        layout.addWidget(add_frame)

        # --- Filtro ---
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filtrar:"))
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Escriba para filtrar por fecha o descripción...")
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

        # --- Estado ---
        summary_row = QHBoxLayout()
        self.lbl_summary = QLabel("Cargando feriados…")
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
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        self.table.selectionModel().selectionChanged.connect(self._update_delete_state)
        layout.addWidget(self.table)

        # --- Botones ---
        btn_row = QHBoxLayout()
        self.btn_delete = QPushButton("Eliminar seleccionado")
        self.btn_delete.setEnabled(False)
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        self.btn_export = QPushButton("Exportar a Excel")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._on_export_clicked)
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_delete)
        btn_row.addWidget(self.btn_export)
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Slots internos
    # ------------------------------------------------------------------

    def _on_add_clicked(self):
        qd = self.date_add.date()
        fecha = date(qd.year(), qd.month(), qd.day())
        desc = self.desc_add.text().strip()
        if not desc:
            QMessageBox.warning(self, "Validación", "Ingrese una descripción.")
            return
        self.add_requested.emit(fecha, desc)

    def _on_delete_clicked(self):
        idx = self.table.currentIndex()
        if not idx.isValid():
            return
        src_idx = self._proxy.mapToSource(idx)
        row = src_idx.row()
        fecha_item = self._model.item(row, 0)
        desc_item = self._model.item(row, 2)
        if fecha_item is None:
            return
        try:
            fecha = date.fromisoformat(fecha_item.text())
        except ValueError:
            return
        desc_txt = desc_item.text() if desc_item else ""
        res = QMessageBox.question(
            self, "Confirmar eliminación",
            f"¿Eliminar el feriado?\n\n{fecha.isoformat()} — {desc_txt}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if res == QMessageBox.StandardButton.Yes:
            self.delete_requested.emit(fecha)

    def _on_export_clicked(self):
        if self._data:
            self.export_requested.emit(self._data)

    def _update_delete_state(self, *_):
        has_sel = self.table.currentIndex().isValid()
        self.btn_delete.setEnabled(has_sel and not self.progress.isVisible())

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def clear_add_form(self):
        self.desc_add.clear()

    def set_status(self, text: str):
        self.lbl_summary.setText(text)

    def set_busy(self, busy: bool, status_text: str | None = None):
        self.btn_reload.setEnabled(not busy)
        self.btn_add.setEnabled(not busy)
        self.date_add.setEnabled(not busy)
        self.desc_add.setEnabled(not busy)
        self.table.setEnabled(not busy)
        has_data = len(self._data) > 0
        self.filter_input.setEnabled(not busy and has_data)
        self.btn_export.setEnabled(not busy and has_data)
        self.btn_delete.setEnabled(
            not busy and has_data and self.table.currentIndex().isValid()
        )
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
        # Enriquecer con día de la semana en español
        enriched = []
        for e in data:
            iso = e.get("fecha") or ""
            try:
                f = date.fromisoformat(iso)
                dia = _DIAS_SEMANA[f.weekday()]
            except (TypeError, ValueError):
                dia = ""
            enriched.append({
                "fecha": iso,
                "dia_semana": dia,
                "descripcion": e.get("descripcion") or "",
            })
        self._data = enriched

        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)
        self.table.setModel(None)
        self._proxy.setSourceModel(None)
        self._model.blockSignals(True)
        self._model.clear()
        self.filter_input.blockSignals(True)
        self.filter_input.clear()
        self.filter_input.blockSignals(False)

        if not enriched:
            self._model.blockSignals(False)
            self._proxy.setSourceModel(self._model)
            self._proxy.setFilterRegularExpression(QRegularExpression(""))
            self.table.setModel(self._proxy)
            self.table.setUpdatesEnabled(True)
            self.table.setSortingEnabled(True)
            self.set_status("No hay feriados registrados.")
            self.lbl_filtered.setText("")
            self.filter_input.setEnabled(False)
            self.btn_export.setEnabled(False)
            self.btn_delete.setEnabled(False)
            return

        self._model.setHorizontalHeaderLabels([lbl for _, lbl in self._COLUMNS])
        align_center = Qt.AlignmentFlag.AlignCenter
        self._model.setRowCount(len(enriched))
        for r_idx, row in enumerate(enriched):
            fecha_item = QStandardItem(row["fecha"])
            fecha_item.setTextAlignment(align_center)
            fecha_item.setEditable(False)
            dia_item = QStandardItem(row["dia_semana"])
            dia_item.setTextAlignment(align_center)
            dia_item.setEditable(False)
            desc_item = QStandardItem(row["descripcion"])
            desc_item.setEditable(False)
            self._model.setItem(r_idx, 0, fecha_item)
            self._model.setItem(r_idx, 1, dia_item)
            self._model.setItem(r_idx, 2, desc_item)

        self._model.blockSignals(False)
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterRegularExpression(QRegularExpression(""))
        self.table.setModel(self._proxy)
        self.table.setUpdatesEnabled(True)
        self.table.setSortingEnabled(True)
        self.table.selectionModel().selectionChanged.connect(self._update_delete_state)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 110)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(1, 100)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        self.set_status(f"{len(enriched)} feriado(s) registrados.")
        self.lbl_filtered.setText("")
        self.filter_input.setEnabled(True)
        self.btn_export.setEnabled(True)

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
