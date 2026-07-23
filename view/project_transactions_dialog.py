from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableView, QPushButton, QHeaderView, QAbstractItemView,
    QDateEdit, QFrame, QMessageBox,
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QFont
from PyQt6.QtCore import Qt, QDate, pyqtSignal, QRegularExpression

from .main_window import _MultiColumnProxy


class ProjectTransactionsDialog(QDialog):
    search_requested = pyqtSignal(str, object, object)
    export_requested = pyqtSignal(list, str)

    def __init__(self, default_start_date: QDate, default_end_date: QDate, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Buscar Transacciones por Proyecto (SIA)")
        self.setMinimumSize(1000, 600)
        self.resize(1050, 650)
        self._data: list[dict] = []

        self._model = QStandardItemModel()
        self._proxy = _MultiColumnProxy()
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self._setup_ui(default_start_date, default_end_date)

    def _setup_ui(self, default_start_date: QDate, default_end_date: QDate):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # --- Panel de Búsqueda ---
        search_frame = QFrame()
        search_frame.setFrameShape(QFrame.Shape.StyledPanel)
        search_layout = QVBoxLayout(search_frame)
        search_layout.setSpacing(8)

        inputs_row = QHBoxLayout()

        inputs_row.addWidget(QLabel("Nº SIA (CodProyecto):"))
        self.txt_codproyecto = QLineEdit()
        self.txt_codproyecto.setPlaceholderText("Ej. LCS, INI-2024-001")
        self.txt_codproyecto.setMinimumWidth(200)
        self.txt_codproyecto.returnPressed.connect(self._on_search_clicked)
        inputs_row.addWidget(self.txt_codproyecto)

        inputs_row.addSpacing(16)
        inputs_row.addWidget(QLabel("Fecha inicial:"))
        self.date_start = QDateEdit()
        self.date_start.setCalendarPopup(True)
        self.date_start.setDate(default_start_date)
        self.date_start.setDisplayFormat("dd/MM/yyyy")
        inputs_row.addWidget(self.date_start)

        inputs_row.addSpacing(16)
        inputs_row.addWidget(QLabel("Fecha final:"))
        self.date_end = QDateEdit()
        self.date_end.setCalendarPopup(True)
        self.date_end.setDate(default_end_date)
        self.date_end.setDisplayFormat("dd/MM/yyyy")
        inputs_row.addWidget(self.date_end)

        inputs_row.addSpacing(16)
        self.btn_search = QPushButton("Buscar")
        bold_font = QFont()
        bold_font.setBold(True)
        self.btn_search.setFont(bold_font)
        self.btn_search.setFixedWidth(100)
        self.btn_search.clicked.connect(self._on_search_clicked)
        inputs_row.addWidget(self.btn_search)

        search_layout.addLayout(inputs_row)
        layout.addWidget(search_frame)

        # --- Filtro Rápido sobre resultados ---
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filtrar resultados:"))
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Escriba para filtrar en los resultados de la tabla...")
        self.filter_input.setClearButtonEnabled(True)
        self.filter_input.textChanged.connect(self._apply_filter)
        self.filter_input.setEnabled(False)
        filter_row.addWidget(self.filter_input)
        layout.addLayout(filter_row)

        # --- Resumen ---
        summary_row = QHBoxLayout()
        self.lbl_summary = QLabel("Ingrese un número de SIA (CodProyecto) y rango de fechas para buscar.")
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

        # --- Botones de acción inferior ---
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

    def _on_search_clicked(self):
        cod_proyecto = self.txt_codproyecto.text().strip()
        if not cod_proyecto:
            QMessageBox.warning(self, "Validación", "Por favor, ingrese un número de SIA (CodProyecto) para buscar.")
            return

        start_date = self.date_start.date().toPyDate()
        end_date = self.date_end.date().toPyDate()

        if start_date > end_date:
            QMessageBox.warning(self, "Validación", "La fecha inicial no puede ser mayor que la fecha final.")
            return

        self.search_requested.emit(cod_proyecto, start_date, end_date)

    def _on_export_clicked(self, fmt: str):
        if self._data:
            self.export_requested.emit(self._data, fmt)

    def set_busy(self, busy: bool):
        self.btn_search.setEnabled(not busy)
        self.txt_codproyecto.setEnabled(not busy)
        self.date_start.setEnabled(not busy)
        self.date_end.setEnabled(not busy)
        has_data = len(self._data) > 0
        self.filter_input.setEnabled(not busy and has_data)
        self.btn_export_xlsx.setEnabled(not busy and has_data)
        self.btn_export_csv.setEnabled(not busy and has_data)

    def display_results(self, data: list[dict]):
        self._data = data
        self._model.clear()
        self.filter_input.blockSignals(True)
        self.filter_input.clear()
        self.filter_input.blockSignals(False)
        self._proxy.setFilterRegularExpression(QRegularExpression(""))

        if not data:
            self.lbl_summary.setText("No se encontraron transacciones para el proyecto en el rango de fechas.")
            self.lbl_filtered.setText("")
            self.filter_input.setEnabled(False)
            self.btn_export_xlsx.setEnabled(False)
            self.btn_export_csv.setEnabled(False)
            return

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

        actual_cols = [c for c in columns_map.keys() if c in data[0]]
        header_labels = [columns_map[c] for c in actual_cols]
        self._model.setHorizontalHeaderLabels(header_labels)

        for row in data:
            items = []
            for col in actual_cols:
                val = row[col]
                if col == "Fecha" and val is not None:
                    try:
                        text = val.strftime("%d/%m/%Y")
                    except AttributeError:
                        text = str(val)
                else:
                    text = "" if val is None else str(val)
                item = QStandardItem(text)
                if col != "DescProyecto" and col != "NomUsuario":
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setEditable(False)
                items.append(item)
            self._model.appendRow(items)

        total_reg = sum(float(str(r.get("HoraRegular") or 0)) for r in data)
        total_ext = sum(float(str(r.get("HoraExtra") or 0)) for r in data)
        total_comp = sum(float(str(r.get("HoraComp") or 0)) for r in data)

        self.lbl_summary.setText(
            f"{len(data)} registros  |  "
            f"Regulares: {total_reg:,.2f}  |  "
            f"Extras: {total_ext:,.2f}  |  "
            f"Compensadas: {total_comp:,.2f}"
        )
        self.lbl_filtered.setText("")
        self.filter_input.setEnabled(True)
        self.btn_export_xlsx.setEnabled(True)
        self.btn_export_csv.setEnabled(True)

        self.table.resizeColumnsToContents()
        if "DescProyecto" in actual_cols:
            desc_idx = actual_cols.index("DescProyecto")
            self.table.horizontalHeader().setSectionResizeMode(desc_idx, QHeaderView.ResizeMode.Stretch)

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
