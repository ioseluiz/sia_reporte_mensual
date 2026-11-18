"""Repositorio JSON de días feriados (Panamá).

Fuente de verdad: `config/feriados_pa.json` — una lista ordenada por fecha
con entradas `{"fecha": "YYYY-MM-DD", "descripcion": "..."}`.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

log = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _PROJECT_ROOT / "config" / "feriados_pa.json"


def _parse_fecha(s: str) -> date | None:
    try:
        return date.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def _load_all() -> list[dict]:
    if not _CONFIG_PATH.exists():
        return []
    try:
        with _CONFIG_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("No se pudo leer %s: %s. Continuando con lista vacía.",
                    _CONFIG_PATH, exc)
        return []
    if not isinstance(data, list):
        log.warning("feriados_pa.json no es una lista; se ignora.")
        return []
    salida: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        f = _parse_fecha(item.get("fecha", ""))
        if f is None:
            continue
        salida.append({
            "fecha": f.isoformat(),
            "descripcion": str(item.get("descripcion") or "").strip(),
        })
    salida.sort(key=lambda x: x["fecha"])
    return salida


def _save_all(entradas: list[dict]) -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    ordenadas = sorted(entradas, key=lambda x: x["fecha"])
    with _CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(ordenadas, f, ensure_ascii=False, indent=2)


def list_feriados() -> list[dict]:
    """Lista todos los feriados almacenados, ordenados por fecha ascendente."""
    return _load_all()


def get_fechas(start: date, end: date) -> list[date]:
    """Devuelve las fechas feriadas dentro del rango inclusivo [start, end].

    Pensado para pasar directamente como parámetros a una query SQL (IN (…)).
    """
    return [
        date.fromisoformat(e["fecha"])
        for e in _load_all()
        if start <= date.fromisoformat(e["fecha"]) <= end
    ]


def add_feriado(fecha: date, descripcion: str) -> bool:
    """Agrega (upsert) el feriado. Devuelve True si se insertó, False si ya existía
    y solo se actualizó la descripción."""
    desc = (descripcion or "").strip()
    entradas = _load_all()
    iso = fecha.isoformat()
    for e in entradas:
        if e["fecha"] == iso:
            e["descripcion"] = desc
            _save_all(entradas)
            return False
    entradas.append({"fecha": iso, "descripcion": desc})
    _save_all(entradas)
    return True


def delete_feriado(fecha: date) -> bool:
    """Elimina el feriado si existe. Devuelve True si se eliminó."""
    entradas = _load_all()
    iso = fecha.isoformat()
    nueva = [e for e in entradas if e["fecha"] != iso]
    if len(nueva) == len(entradas):
        return False
    _save_all(nueva)
    return True
