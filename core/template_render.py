"""Render de la plantilla HTML del correo de horas menores a 8."""
from __future__ import annotations

import sys
from datetime import date
from html import escape
from pathlib import Path
from typing import Iterable

_MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _resolve_template_path() -> Path:
    """Busca el HTML de la plantilla tanto en dev como en el .exe empaquetado.
    PyInstaller expone los recursos en sys._MEIPASS; en dev se resuelve
    relativo a este archivo (raiz-del-repo/templates).
    """
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "templates" / "correo_menores_8.html")
    candidates.append(
        Path(__file__).resolve().parent.parent / "templates" / "correo_menores_8.html"
    )
    for p in candidates:
        if p.exists():
            return p
    # Cae al primer candidato para dar un mensaje de error claro al leerlo
    return candidates[0]


_TEMPLATE_PATH = _resolve_template_path()


def format_periodo(inicio: date, fin: date) -> str:
    """Ej.: '21 de julio al 20 de agosto de 2026'."""
    ini = f"{inicio.day} de {_MESES[inicio.month - 1]}"
    if inicio.year != fin.year:
        ini += f" de {inicio.year}"
    fin_txt = f"{fin.day} de {_MESES[fin.month - 1]} de {fin.year}"
    return f"{ini} al {fin_txt}"


def _fmt_fecha(value) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _fmt_horas(value) -> str:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return escape(str(value))
    return f"{num:g}"


def build_tabla_html(filas: Iterable[dict]) -> str:
    """Construye una tabla HTML con las columnas Usuario / CodRamo / Fecha / Horas Regulares."""
    header_style = (
        "background:#D6D6D6; padding:4px 8px; text-align:left; "
        "border:1px solid #B0B0B0; font-family:Calibri, sans-serif;"
    )
    cell_style = (
        "padding:4px 8px; border:1px solid #B0B0B0; "
        "font-family:Calibri, sans-serif;"
    )
    num_cell_style = cell_style + " text-align:right;"

    rows_html = []
    for row in filas:
        usuario = escape(str(row.get("NomUsuario") or row.get("Usuario") or ""))
        cod_ramo = escape(str(row.get("CodRamo") or ""))
        fecha = escape(_fmt_fecha(row.get("Fecha")))
        horas = _fmt_horas(row.get("HorasRegulares", row.get("Horas Regulares")))
        rows_html.append(
            f"<tr>"
            f"<td style=\"{cell_style}\">{usuario}</td>"
            f"<td style=\"{cell_style}\">{cod_ramo}</td>"
            f"<td style=\"{num_cell_style}\">{fecha}</td>"
            f"<td style=\"{num_cell_style}\">{horas}</td>"
            f"</tr>"
        )

    return (
        "<table style=\"border-collapse:collapse; font-size:11pt;\">"
        "<thead><tr>"
        f"<th style=\"{header_style}\">Usuario</th>"
        f"<th style=\"{header_style}\">CodRamo</th>"
        f"<th style=\"{header_style}\">Fecha</th>"
        f"<th style=\"{header_style}\">Horas Regulares</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows_html)}</tbody>"
        "</table>"
    )


def render_correo(supervisor_nombre: str, periodo: str, filas: Iterable[dict]) -> str:
    """Lee la plantilla y sustituye los placeholders. Devuelve el HTML final."""
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    tabla = build_tabla_html(filas)
    return (
        template
        .replace("{{supervisor_nombre}}", escape(supervisor_nombre))
        .replace("{{periodo}}", escape(periodo))
        .replace("{{tabla_html}}", tabla)
    )


def build_asunto(periodo: str) -> str:
    return f"Solicitud de apoyo: Actualización y registro de horas en el SIA – Periodo ({periodo})"
