from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QTableView, QPushButton, QHeaderView, QAbstractItemView,
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtCore import Qt, pyqtSignal


class ProjectDetailDialog(QDialog):
    export_requested = pyqtSignal(list, str, str)

    def __init__(self, cod_proyecto: str, data: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Detalle de transacciones — {cod_proyecto}")
        self.setMinimumSize(900, 550)
        self.resize(950, 600)

        self._cod_proyecto = cod_proyecto
        self._data = data or []

        self._model = QStandardItemModel()
        self._setup_ui()
        self._populate_table()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        header = QLabel(f"Proyecto: <b>{self._cod_proyecto}</b>  |  Todas las transacciones históricas")
        layout.addWidget(header)

        self.lbl_summary = QLabel("")
        layout.addWidget(self.lbl_summary)

        self.table = QTableView()
        self.table.setModel(self._model)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        self.btn_export_xlsx = QPushButton("Exportar a Excel")
        self.btn_export_xlsx.clicked.connect(lambda: self._on_export_clicked("xlsx"))
        self.btn_export_csv = QPushButton("Exportar a CSV")
        self.btn_export_csv.clicked.connect(lambda: self._on_export_clicked("csv"))

        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)

        btn_row.addWidget(self.btn_export_xlsx)
        btn_row.addWidget(self.btn_export_csv)
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    def _populate_table(self):
        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)
        self.table.setModel(None)
        self._model.blockSignals(True)
        self._model.clear()

        if not self._data:
            self._model.blockSignals(False)
            self.table.setModel(self._model)
            self.table.setUpdatesEnabled(True)
            self.table.setSortingEnabled(True)
            self.lbl_summary.setText("No hay transacciones registradas para este proyecto.")
            self.btn_export_xlsx.setEnabled(False)
            self.btn_export_csv.setEnabled(False)
            return

        columns = [
            ("Fecha", "Fecha"),
            ("NomUsuario", "Usuario"),
            ("CodRamo", "CodRamo Emp."),
            ("HoraRegular", "Hora Regular"),
            ("HoraComp", "Hora Comp"),
            ("HoraExtra", "Hora Extra"),
            ("IP", "IP"),
            ("ID", "ID"),
        ]
        actual = [(k, label) for k, label in columns if k in self._data[0]]
        self._model.setHorizontalHeaderLabels([label for _, label in actual])

        numeric_cols = {"HoraRegular", "HoraComp", "HoraExtra"}
        align_right = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        align_center = Qt.AlignmentFlag.AlignCenter
        totals = {"HoraRegular": 0.0, "HoraComp": 0.0, "HoraExtra": 0.0}

        self._model.setRowCount(len(self._data))
        for r_idx, row in enumerate(self._data):
            for c_idx, (key, _) in enumerate(actual):
                val = row[key]
                if key == "Fecha" and val is not None:
                    try:
                        text = val.strftime("%d/%m/%Y")
                    except AttributeError:
                        text = str(val)
                    item = QStandardItem(text)
                    item.setTextAlignment(align_center)
                elif key in numeric_cols:
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
                    if key != "NomUsuario":
                        item.setTextAlignment(align_center)
                item.setEditable(False)
                self._model.setItem(r_idx, c_idx, item)

        self._model.blockSignals(False)
        self.table.setModel(self._model)
        self.table.setUpdatesEnabled(True)
        self.table.setSortingEnabled(True)

        grand = totals["HoraRegular"] + totals["HoraComp"] + totals["HoraExtra"]
        self.lbl_summary.setText(
            f"{len(self._data)} registros  |  "
            f"Regulares: {totals['HoraRegular']:,.2f}  |  "
            f"Comp: {totals['HoraComp']:,.2f}  |  "
            f"Extras: {totals['HoraExtra']:,.2f}  |  "
            f"Total: {grand:,.2f}"
        )

        header = self.table.horizontalHeader()
        for i, (key, _) in enumerate(actual):
            if key == "NomUsuario":
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
                self.table.setColumnWidth(i, 110)

    def _on_export_clicked(self, fmt: str):
        if self._data:
            self.export_requested.emit(self._data, fmt, self._cod_proyecto)
