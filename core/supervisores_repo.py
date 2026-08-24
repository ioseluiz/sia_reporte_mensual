"""Repositorio JSON del mapeo CodRamo -> supervisor (nombre, email, cc)."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _PROJECT_ROOT / "config" / "supervisores.json"
_EXAMPLE_PATH = _PROJECT_ROOT / "config" / "supervisores.example.json"

_EMPTY = {"nombre": "", "email": "", "cc": []}


def _load_all() -> dict[str, dict[str, Any]]:
    path = _CONFIG_PATH if _CONFIG_PATH.exists() else _EXAMPLE_PATH
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            log.warning("supervisores.json no es un objeto JSON; se ignora.")
            return {}
        return data
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("No se pudo leer %s: %s. Continuando con mapeo vacío.", path, exc)
        return {}


def get_defaults(cod_ramo: str) -> dict[str, Any]:
    """Devuelve {'nombre','email','cc'} para el CodRamo, o vacíos si no existe."""
    data = _load_all()
    entry = data.get(cod_ramo)
    if not isinstance(entry, dict):
        return dict(_EMPTY, cc=list(_EMPTY["cc"]))
    return {
        "nombre": str(entry.get("nombre") or ""),
        "email": str(entry.get("email") or ""),
        "cc": [str(x) for x in (entry.get("cc") or []) if str(x).strip()],
    }


def save_defaults(cod_ramo: str, nombre: str, email: str, cc: list[str]) -> None:
    """Persiste el mapeo para CodRamo. Crea config/supervisores.json si no existe."""
    data = _load_all() if _CONFIG_PATH.exists() else {}
    data[cod_ramo] = {
        "nombre": nombre.strip(),
        "email": email.strip(),
        "cc": [c.strip() for c in cc if c and c.strip()],
    }
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
