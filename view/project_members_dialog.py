from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QTableView, QPushButton, QHeaderView, QAbstractItemView,
    QMessageBox, QApplication,
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QFont, QColor, QBrush
from PyQt6.QtCore import Qt, pyqtSignal


class ProjectMembersDialog(QDialog):
    """Muestra los integrantes de un proyecto. Columnas dinamicas.
    Resalta la fila del coordinador si detecta una columna con la palabra
    'coordinador' (o 'coord') que resulte truthy en esa fila.
    """

    export_requested = pyqtSignal(list, str)   # (data, cod_proyecto)

    _COORD_KEYWORDS = ("coordinador", "coord")

    def __init__(self, cod_proyecto: str, nom_proyecto: str,
                 data: list[dict], parent=None):
        super().__init__(parent)
        self._cod_proyecto = cod_proyecto
        self._nom_proyecto = nom_proyecto or ""
        self._data = data or []

        titulo = f"Integrantes de {cod_proyecto}"
        if self._nom_proyecto:
            titulo += f" — {self._nom_proyecto}"
        self.setWindowTitle(titulo)
        self.setMinimumSize(820, 480)
        self.resize(960, 560)

        self._model = QStandardItemModel()

        self._setup_ui()
        self._populate()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        header = QVBoxLayout()
        title = QLabel(f"Proyecto: {self._cod_proyecto}")
        bold = QFont()
        bold.setBold(True)
        bold.setPointSize(bold.pointSize() + 1)
        title.setFont(bold)
        header.addWidget(title)
        if self._nom_proyecto:
            header.addWidget(QLabel(self._nom_proyecto))
        layout.addLayout(header)

        self.lbl_summary = QLabel("")
        self.lbl_coord = QLabel("")
        self.lbl_coord.setStyleSheet("color: #a15c00;")
        layout.addWidget(self.lbl_summary)
        layout.addWidget(self.lbl_coord)

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
        self.btn_export = QPushButton("Exportar a Excel")
        self.btn_export.setEnabled(bool(self._data))
        self.btn_export.clicked.connect(self._on_export_clicked)
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_export)
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    @classmethod
    def _detect_coord_key(cls, keys: list[str]) -> str | None:
        for k in keys:
            low = k.lower()
            if any(kw in low for kw in cls._COORD_KEYWORDS):
                return k
        return None

    def _populate(self):
        if not self._data:
            self.lbl_summary.setText(
                f"El proyecto {self._cod_proyecto} no tiene integrantes registrados en tblIntegrantes."
            )
            self._model.setHorizontalHeaderLabels(["(sin datos)"])
            return

        keys = list(self._data[0].keys())
        self._model.setHorizontalHeaderLabels(keys)

        coord_key = self._detect_coord_key(keys)
        coord_names: list[str] = []
        highlight_brush = QBrush(QColor(255, 243, 205))   # amarillo claro
        bold_font = QFont()
        bold_font.setBold(True)

        self._model.setRowCount(len(self._data))
        for r_idx, row in enumerate(self._data):
            is_coord = False
            if coord_key is not None:
                is_coord = bool(row.get(coord_key))

            for c_idx, k in enumerate(keys):
                val = row.get(k)
                if val is None:
                    text = ""
                elif isinstance(val, bool):
                    text = "Sí" if val else "No"
                elif hasattr(val, "strftime"):
                    text = val.strftime("%Y-%m-%d")
                else:
                    text = str(val)
                item = QStandardItem(text)
                item.setEditable(False)
                if is_coord:
                    item.setBackground(highlight_brush)
                    item.setFont(bold_font)
                self._model.setItem(r_idx, c_idx, item)

            if is_coord:
                name = (row.get("NomUsuario") or row.get("Nombre")
                        or row.get("IP") or row.get("CodUsuario") or "—")
                coord_names.append(str(name))

        header = self.table.horizontalHeader()
        for i, k in enumerate(keys):
            if k in ("NomUsuario", "NomProyecto", "Nombre"):
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)

        self.lbl_summary.setText(f"{len(self._data)} integrante(s).")
        if coord_names:
            self.lbl_coord.setText(
                f"Coordinador: {', '.join(coord_names)} (columna: {coord_key})"
            )
        elif coord_key is None:
            self.lbl_coord.setText(
                "No se detectó columna de coordinador en tblIntegrantes."
            )
        else:
            self.lbl_coord.setText(
                f"Ningún integrante marcado como coordinador ({coord_key})."
            )

    def _on_export_clicked(self):
        if self._data:
            self.export_requested.emit(self._data, self._cod_proyecto)

    def show_error(self, title: str, message: str):
        QMessageBox.critical(self, title, message)

    def show_info(self, title: str, message: str):
        QMessageBox.information(self, title, message)
