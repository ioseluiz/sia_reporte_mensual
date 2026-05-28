from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableView, QPushButton, QHeaderView, QAbstractItemView,
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QFont
from PyQt6.QtCore import Qt, QRegularExpression

from .main_window import _MultiColumnProxy


class DetailDialog(QDialog):
    """
    Muestra todas las transacciones individuales de un proyecto
    para el período seleccionado.
    """

    def __init__(self, cod_proyecto: str, data: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Detalle de transacciones — {cod_proyecto.strip()}")
        self.setMinimumSize(820, 520)
        self.resize(900, 580)
        self._data = data
        self._cod_proyecto = cod_proyecto.strip()

        self._model = QStandardItemModel()
        self._proxy = _MultiColumnProxy()
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self._setup_ui()
        self._populate()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        title = QLabel(f"Proyecto: <b>{self._cod_proyecto}</b>")
        font = QFont()
        font.setPointSize(10)
        title.setFont(font)
        layout.addWidget(title)

        # Filtro
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filtrar:"))
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filtrar por cualquier columna…")
        self.filter_input.setClearButtonEnabled(True)
        self.filter_input.textChanged.connect(self._apply_filter)
        filter_row.addWidget(self.filter_input)
        layout.addLayout(filter_row)

        # Resumen
        summary_row = QHBoxLayout()
        self.lbl_summary = QLabel("")
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
        self.btn_export = QPushButton("Exportar a Excel")
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_export)
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------

    def _populate(self):
        self._model.clear()

        if not self._data:
            self.lbl_summary.setText("Sin transacciones para este proyecto en el período.")
            return

        columns = list(self._data[0].keys())
        self._model.setHorizontalHeaderLabels(columns)

        for row in self._data:
            items = []
            for col in columns:
                val = row[col]
                text = "" if val is None else str(val)
                item = QStandardItem(text)
                item.setEditable(False)
                items.append(item)
            self._model.appendRow(items)

        total = sum(
            float(str(r.get("HoraRegular", 0) or 0))
            for r in self._data
        )
        self.lbl_summary.setText(
            f"{len(self._data)} transacciones  |  Total HoraRegular: {total:,.2f}"
        )

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
