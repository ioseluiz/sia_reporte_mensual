"""Diálogo de preview del Reporte de Horas Menores a 8 y Faltantes.

Permite:
- Ver una pestaña por CodRamo con las filas del periodo.
- Marcar/desmarcar filas individuales (Sí/No).
- Distinguir visualmente Faltante (0 h) e Incompleto (0 < h < 8).
- Editar el supervisor (nombre, correo, CC) por sección, con defaults desde
  config/supervisores.json.
- Disparar dos acciones independientes: Descargar Excel y Crear borradores en Outlook.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QFormLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMenu, QMessageBox,
    QPushButton, QSizePolicy, QTabWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from core import supervisores_repo


_STATE_FALTANTE = "Faltante"
_STATE_INCOMPLETO = "Incompleto"

_COLOR_FALTANTE = QColor("#F8D7DA")
_COLOR_INCOMPLETO = QColor("#FFF3CD")

_HEADERS = ["", "Estado", "Usuario", "Fecha", "Horas Regulares"]
_COL_CHECK = 0
_COL_STATE = 1
_COL_USER = 2
_COL_DATE = 3
_COL_HOURS = 4


def _fmt_fecha(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y-%m-%d")
    return str(value or "")


def _fmt_horas(value: Any) -> str:
    try:
        return f"{float(value):g}"
    except (TypeError, ValueError):
        return str(value or "")


class _SectionTab(QWidget):
    """Widget interno para cada pestaña (una sección / CodRamo)."""

    seleccion_changed = pyqtSignal()       # actualiza contadores globales y "Descargar Excel"
    crear_borrador_pedido = pyqtSignal(str)  # emite cod_ramo al pulsar el botón de la sección

    def __init__(self, cod_ramo: str, filas: list[dict], parent=None):
        super().__init__(parent)
        self.cod_ramo = cod_ramo
        self._filas = filas
        self._build_ui()
        self._prefill_supervisor()
        self._populate_table()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # --- Supervisor ---
        gb = QGroupBox(f"Supervisor de {self.cod_ramo}")
        form = QFormLayout(gb)
        form.setContentsMargins(10, 8, 10, 8)
        self.ed_nombre = QLineEdit()
        self.ed_nombre.setPlaceholderText("Ej.: Ing. Vielka Quijada")
        self.ed_email = QLineEdit()
        self.ed_email.setPlaceholderText("correo@pancanal.com")
        self.ed_cc = QLineEdit()
        self.ed_cc.setPlaceholderText("cc1@pancanal.com, cc2@pancanal.com")
        self.btn_save_default = QPushButton("Guardar como default")
        self.btn_save_default.setFixedWidth(180)
        self.btn_save_default.clicked.connect(self._save_default)
        self.btn_crear_borrador = QPushButton(f"Crear borrador de correo para {self.cod_ramo}")
        self.btn_crear_borrador.setFixedHeight(32)
        bold = QFont()
        bold.setBold(True)
        self.btn_crear_borrador.setFont(bold)
        self.btn_crear_borrador.clicked.connect(
            lambda: self.crear_borrador_pedido.emit(self.cod_ramo)
        )

        form.addRow("Nombre:", self.ed_nombre)
        form.addRow("Correo (Para):", self.ed_email)
        form.addRow("CC (separados por coma):", self.ed_cc)
        actions_row = QHBoxLayout()
        actions_row.addWidget(self.btn_save_default)
        actions_row.addStretch()
        actions_row.addWidget(self.btn_crear_borrador)
        form.addRow("", actions_row)
        layout.addWidget(gb)

        # Signals para refrescar estado del botón de esta sección
        for widget in (self.ed_nombre, self.ed_email):
            widget.textChanged.connect(self._refresh_own_button)

        # --- Tabla ---
        self.table = QTableWidget(0, len(_HEADERS))
        self.table.setHorizontalHeaderLabels(_HEADERS)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setToolTip(
            "Doble clic sobre el usuario o clic derecho sobre una fila para "
            "marcar/desmarcar todos los registros de ese usuario."
        )
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(_COL_CHECK, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(_COL_STATE, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(_COL_USER, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(_COL_DATE, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(_COL_HOURS, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_user_menu)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        layout.addWidget(self.table, stretch=1)

        # --- Contador ---
        self.lbl_counter = QLabel("")
        self.lbl_counter.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.lbl_counter)

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------

    def _prefill_supervisor(self):
        defaults = supervisores_repo.get_defaults(self.cod_ramo)
        self.ed_nombre.setText(defaults["nombre"])
        self.ed_email.setText(defaults["email"])
        self.ed_cc.setText(", ".join(defaults["cc"]))

    def _populate_table(self):
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._filas))
        bold = QFont()
        bold.setBold(True)
        for row_idx, fila in enumerate(self._filas):
            horas = fila.get("HorasRegulares")
            try:
                horas_num = float(horas)
            except (TypeError, ValueError):
                horas_num = 0.0
            estado = _STATE_FALTANTE if horas_num <= 0 else _STATE_INCOMPLETO
            bg = _COLOR_FALTANTE if estado == _STATE_FALTANTE else _COLOR_INCOMPLETO

            # Col 0: checkbox
            chk_item = QTableWidgetItem()
            chk_item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
            )
            chk_item.setCheckState(Qt.CheckState.Checked)
            chk_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row_idx, _COL_CHECK, chk_item)

            # Col 1: estado con badge
            estado_item = QTableWidgetItem(estado)
            estado_item.setBackground(bg)
            estado_item.setFont(bold)
            estado_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row_idx, _COL_STATE, estado_item)

            # Col 2: usuario
            user_item = QTableWidgetItem(str(fila.get("NomUsuario") or ""))
            self.table.setItem(row_idx, _COL_USER, user_item)

            # Col 3: fecha
            date_item = QTableWidgetItem(_fmt_fecha(fila.get("Fecha")))
            date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row_idx, _COL_DATE, date_item)

            # Col 4: horas
            hours_item = QTableWidgetItem(_fmt_horas(horas))
            hours_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row_idx, _COL_HOURS, hours_item)

        self.table.blockSignals(False)
        self._update_counter()

    def _on_item_changed(self, item: QTableWidgetItem):
        if item.column() == _COL_CHECK:
            self._update_counter()
            self._refresh_own_button()
            self.seleccion_changed.emit()

    def _refresh_own_button(self):
        self.btn_crear_borrador.setEnabled(
            self.supervisor_valido() and self.has_filas_marcadas()
        )

    def _update_counter(self):
        checked = sum(1 for r in range(self.table.rowCount())
                      if not self.table.isRowHidden(r)
                      and self.table.item(r, _COL_CHECK).checkState() == Qt.CheckState.Checked)
        visibles = sum(1 for r in range(self.table.rowCount()) if not self.table.isRowHidden(r))
        total = self.table.rowCount()
        if visibles == total:
            self.lbl_counter.setText(f"{checked} de {total} filas incluidas")
        else:
            self.lbl_counter.setText(
                f"{checked} de {total} filas incluidas — {visibles} visibles con filtro actual"
            )

    # ------------------------------------------------------------------
    # Acciones desde toolbar del diálogo padre
    # ------------------------------------------------------------------

    def marcar_todo(self, marcado: bool):
        self.table.blockSignals(True)
        for r in range(self.table.rowCount()):
            if self.table.isRowHidden(r):
                continue
            self.table.item(r, _COL_CHECK).setCheckState(
                Qt.CheckState.Checked if marcado else Qt.CheckState.Unchecked
            )
        self.table.blockSignals(False)
        self._update_counter()
        self.seleccion_changed.emit()

    def filtrar_por_estado(self, estado: str | None):
        """estado: 'Faltante' | 'Incompleto' | None (mostrar todo)."""
        for r in range(self.table.rowCount()):
            if estado is None:
                self.table.setRowHidden(r, False)
            else:
                item = self.table.item(r, _COL_STATE)
                self.table.setRowHidden(r, item.text() != estado)
        self._update_counter()

    # ------------------------------------------------------------------
    # Marcado por usuario
    # ------------------------------------------------------------------

    def _usuario_at_row(self, row: int) -> str:
        item = self.table.item(row, _COL_USER)
        return item.text() if item else ""

    def _rows_for_user(self, usuario: str) -> list[int]:
        return [
            r for r in range(self.table.rowCount())
            if self._usuario_at_row(r) == usuario
        ]

    def _set_user_check_state(self, usuario: str, marcado: bool):
        if not usuario:
            return
        state = Qt.CheckState.Checked if marcado else Qt.CheckState.Unchecked
        self.table.blockSignals(True)
        for r in self._rows_for_user(usuario):
            self.table.item(r, _COL_CHECK).setCheckState(state)
        self.table.blockSignals(False)
        self._update_counter()
        self.seleccion_changed.emit()

    def _show_user_menu(self, pos: QPoint):
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        usuario = self._usuario_at_row(row)
        if not usuario:
            return
        total = len(self._rows_for_user(usuario))
        menu = QMenu(self.table)
        act_marcar = menu.addAction(f"Marcar todos los registros de «{usuario}» ({total})")
        act_desmarcar = menu.addAction(f"Desmarcar todos los registros de «{usuario}» ({total})")
        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen == act_marcar:
            self._set_user_check_state(usuario, True)
        elif chosen == act_desmarcar:
            self._set_user_check_state(usuario, False)

    def _on_cell_double_clicked(self, row: int, col: int):
        if col != _COL_USER:
            return
        usuario = self._usuario_at_row(row)
        if not usuario:
            return
        # Toggle: si TODOS los del usuario están marcados, desmarca; si no, marca.
        filas = self._rows_for_user(usuario)
        todos_marcados = all(
            self.table.item(r, _COL_CHECK).checkState() == Qt.CheckState.Checked
            for r in filas
        )
        self._set_user_check_state(usuario, not todos_marcados)

    def filtrar_texto(self, texto: str):
        texto = (texto or "").strip().lower()
        for r in range(self.table.rowCount()):
            if not texto:
                self.table.setRowHidden(r, False)
                continue
            matches = False
            for c in (_COL_USER, _COL_DATE, _COL_HOURS, _COL_STATE):
                item = self.table.item(r, c)
                if item and texto in item.text().lower():
                    matches = True
                    break
            self.table.setRowHidden(r, not matches)
        self._update_counter()

    # ------------------------------------------------------------------
    # Salida
    # ------------------------------------------------------------------

    def get_filas_marcadas(self) -> list[dict]:
        result = []
        for r in range(self.table.rowCount()):
            if self.table.item(r, _COL_CHECK).checkState() == Qt.CheckState.Checked:
                result.append(self._filas[r])
        return result

    def has_filas_marcadas(self) -> bool:
        for r in range(self.table.rowCount()):
            if self.table.item(r, _COL_CHECK).checkState() == Qt.CheckState.Checked:
                return True
        return False

    def get_supervisor(self) -> dict[str, Any]:
        cc_raw = self.ed_cc.text().strip()
        cc_list = [c.strip() for c in cc_raw.replace(";", ",").split(",") if c.strip()] if cc_raw else []
        return {
            "nombre": self.ed_nombre.text().strip(),
            "email": self.ed_email.text().strip(),
            "cc": cc_list,
        }

    def supervisor_valido(self) -> bool:
        email = self.ed_email.text().strip()
        return bool(email and "@" in email and self.ed_nombre.text().strip())

    def _save_default(self):
        sup = self.get_supervisor()
        if not sup["email"] or not sup["nombre"]:
            QMessageBox.warning(
                self, "Datos incompletos",
                "Complete al menos Nombre y Correo antes de guardar como default."
            )
            return
        try:
            supervisores_repo.save_defaults(self.cod_ramo, sup["nombre"], sup["email"], sup["cc"])
            QMessageBox.information(
                self, "Guardado",
                f"Valores guardados como default para {self.cod_ramo}."
            )
        except OSError as exc:
            QMessageBox.critical(
                self, "Error al guardar",
                f"No se pudo escribir el archivo:\n{exc}"
            )


class ReportPreviewDialog(QDialog):
    """Diálogo modal de preview y exportación del reporte de horas <8 y faltantes."""

    descargar_excel = pyqtSignal(dict)      # payload por CodRamo
    crear_borradores = pyqtSignal(dict)     # payload por CodRamo

    def __init__(self, data: list[dict], periodo: tuple[date, date], parent=None):
        super().__init__(parent)
        self._raw_data = data
        self._periodo = periodo
        self.setWindowTitle("Reporte de Horas L-V (< 8h) — Preview")
        self.setMinimumSize(1024, 720)
        self._tabs_por_ramo: dict[str, _SectionTab] = {}
        self._build_ui()
        self._populate_tabs()
        self._refresh_button_state()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 10)
        root.setSpacing(10)

        # Header
        header = QHBoxLayout()
        ini, fin = self._periodo
        self.lbl_header = QLabel(
            f"<b>Periodo:</b> {_fmt_fecha(ini)} al {_fmt_fecha(fin)}"
        )
        self.lbl_totales = QLabel("")
        self.lbl_totales.setAlignment(Qt.AlignmentFlag.AlignRight)
        header.addWidget(self.lbl_header)
        header.addStretch()
        header.addWidget(self.lbl_totales)
        root.addLayout(header)

        # Toolbar
        toolbar = QHBoxLayout()
        self.btn_check_all = QPushButton("Marcar todo")
        self.btn_uncheck_all = QPushButton("Desmarcar todo")
        self.btn_solo_faltantes = QPushButton("Sólo faltantes")
        self.btn_solo_incompletos = QPushButton("Sólo incompletos")
        self.btn_ver_todos = QPushButton("Ver todos")
        for b in (self.btn_check_all, self.btn_uncheck_all, self.btn_solo_faltantes,
                  self.btn_solo_incompletos, self.btn_ver_todos):
            b.setFixedHeight(28)
            toolbar.addWidget(b)
        toolbar.addSpacing(20)
        toolbar.addWidget(QLabel("Filtrar:"))
        self.ed_filter = QLineEdit()
        self.ed_filter.setPlaceholderText("Filtrar filas de la pestaña activa…")
        self.ed_filter.setClearButtonEnabled(True)
        self.ed_filter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        toolbar.addWidget(self.ed_filter)
        root.addLayout(toolbar)

        self.btn_check_all.clicked.connect(lambda: self._current_tab_do(lambda t: t.marcar_todo(True)))
        self.btn_uncheck_all.clicked.connect(lambda: self._current_tab_do(lambda t: t.marcar_todo(False)))
        self.btn_solo_faltantes.clicked.connect(
            lambda: self._current_tab_do(lambda t: t.filtrar_por_estado(_STATE_FALTANTE))
        )
        self.btn_solo_incompletos.clicked.connect(
            lambda: self._current_tab_do(lambda t: t.filtrar_por_estado(_STATE_INCOMPLETO))
        )
        self.btn_ver_todos.clicked.connect(
            lambda: self._current_tab_do(lambda t: t.filtrar_por_estado(None))
        )
        self.ed_filter.textChanged.connect(
            lambda text: self._current_tab_do(lambda t: t.filtrar_texto(text))
        )

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self._on_tab_changed)
        root.addWidget(self.tabs, stretch=1)

        # Nota informativa
        self.lbl_hint = QLabel(
            "Los borradores de correo se crean uno por sección desde el botón "
            "«Crear borrador de correo» dentro de cada pestaña."
        )
        self.lbl_hint.setStyleSheet("color: #555; font-style: italic;")
        root.addWidget(self.lbl_hint)

        # Botones finales
        buttons = QDialogButtonBox()
        self.btn_descargar = QPushButton("Descargar Excel")
        self.btn_cerrar = QPushButton("Cerrar")
        buttons.addButton(self.btn_descargar, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(self.btn_cerrar, QDialogButtonBox.ButtonRole.RejectRole)
        self.btn_descargar.clicked.connect(self._emit_descargar)
        self.btn_cerrar.clicked.connect(self.reject)
        root.addWidget(buttons)

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------

    def _populate_tabs(self):
        grupos: dict[str, list[dict]] = defaultdict(list)
        for fila in self._raw_data:
            ramo = str(fila.get("CodRamo") or "Sin_Ramo").strip() or "Sin_Ramo"
            grupos[ramo].append(fila)

        totales = {"total": 0, "faltantes": 0, "incompletos": 0}
        for ramo in sorted(grupos.keys()):
            filas = grupos[ramo]
            filas.sort(key=lambda f: (str(f.get("NomUsuario") or ""), _fmt_fecha(f.get("Fecha"))))
            tab = _SectionTab(ramo, filas, parent=self.tabs)
            tab.seleccion_changed.connect(self._refresh_button_state)
            tab.crear_borrador_pedido.connect(self._on_borrador_seccion)
            self._tabs_por_ramo[ramo] = tab
            self.tabs.addTab(tab, f"{ramo} ({len(filas)})")
            # Estado inicial del botón interno de la pestaña
            tab._refresh_own_button()

            totales["total"] += len(filas)
            for f in filas:
                try:
                    h = float(f.get("HorasRegulares") or 0)
                except (TypeError, ValueError):
                    h = 0.0
                if h <= 0:
                    totales["faltantes"] += 1
                else:
                    totales["incompletos"] += 1

        self.lbl_totales.setText(
            f"<b>{totales['total']}</b> registros — "
            f"<span style='color:#B02A37'>{totales['faltantes']} faltantes</span>, "
            f"<span style='color:#B8860B'>{totales['incompletos']} incompletos</span> "
            f"en <b>{len(grupos)}</b> secciones"
        )

    def _current_tab_do(self, action):
        idx = self.tabs.currentIndex()
        if idx < 0:
            return
        tab = self.tabs.widget(idx)
        if isinstance(tab, _SectionTab):
            action(tab)

    def _on_tab_changed(self, _idx: int):
        # Reaplicar el filtro de texto al cambiar de pestaña
        self._current_tab_do(lambda t: t.filtrar_texto(self.ed_filter.text()))

    def _refresh_button_state(self):
        hay_marcadas = any(t.has_filas_marcadas() for t in self._tabs_por_ramo.values())
        self.btn_descargar.setEnabled(hay_marcadas)
        # Refresca el botón interno de cada pestaña (por si cambió la selección desde toolbar global)
        for t in self._tabs_por_ramo.values():
            t._refresh_own_button()

    # ------------------------------------------------------------------
    # Salida
    # ------------------------------------------------------------------

    def _build_payload_completo(self) -> dict[str, dict]:
        payload = {}
        for ramo, tab in self._tabs_por_ramo.items():
            filas = tab.get_filas_marcadas()
            if not filas:
                continue
            payload[ramo] = {
                "supervisor": tab.get_supervisor(),
                "enviar_correo": True,
                "filas": filas,
            }
        return payload

    def _emit_descargar(self):
        payload = self._build_payload_completo()
        if not payload:
            QMessageBox.information(
                self, "Sin selección",
                "Marque al menos una fila antes de descargar."
            )
            return
        self.descargar_excel.emit(payload)

    def _on_borrador_seccion(self, cod_ramo: str):
        tab = self._tabs_por_ramo.get(cod_ramo)
        if not tab:
            return
        filas = tab.get_filas_marcadas()
        if not filas:
            QMessageBox.information(
                self, "Sin selección",
                f"No hay filas marcadas en {cod_ramo}."
            )
            return
        sup = tab.get_supervisor()
        if not tab.supervisor_valido():
            QMessageBox.warning(
                self, "Datos incompletos",
                f"Complete Nombre y Correo válido del supervisor de {cod_ramo} antes de crear el borrador."
            )
            return
        payload = {cod_ramo: {
            "supervisor": sup,
            "enviar_correo": True,
            "filas": filas,
        }}
        self.crear_borradores.emit(payload)

    def periodo(self) -> tuple[date, date]:
        return self._periodo
