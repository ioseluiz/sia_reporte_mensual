"""Helpers de año fiscal ACP.

El año fiscal de la Autoridad del Canal de Panamá va de octubre a septiembre.
Ejemplo: FY2025 = 1 de octubre de 2024 → 30 de septiembre de 2025.
"""
from datetime import date
from typing import Iterable

FY_START_MONTH = 10  # octubre


def fy_from_date(d: date) -> int:
    """Devuelve el año fiscal al que pertenece una fecha."""
    return d.year + 1 if d.month >= FY_START_MONTH else d.year


def fy_bounds(fy: int) -> tuple[date, date]:
    """Devuelve (inicio, fin) inclusivos del año fiscal dado."""
    return date(fy - 1, FY_START_MONTH, 1), date(fy, 9, 30)


def fy_label(fy: int) -> str:
    """Etiqueta legible para la UI, ej. 'FY2025 (oct-2024 → sep-2025)'."""
    return f"FY{fy} (oct-{fy - 1} → sep-{fy})"


def fys_to_date_range(fys: Iterable[int]) -> tuple[date, date]:
    """Rango mínimo→máximo que cubre todos los FY dados.

    Útil para pasar un único (start, end) al WHERE del SQL; el filtrado
    exacto por FY lo hace el CASE WHEN sobre el mes.
    """
    fys_list = sorted(int(fy) for fy in fys)
    if not fys_list:
        raise ValueError("fys no puede estar vacío")
    start, _ = fy_bounds(fys_list[0])
    _, end = fy_bounds(fys_list[-1])
    return start, end
