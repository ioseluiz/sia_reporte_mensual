"""Creación de borradores en Outlook vía COM (win32com).

Debe llamarse desde el hilo principal (COM no es thread-safe con MTA).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

log = logging.getLogger(__name__)


class OutlookNoDisponibleError(RuntimeError):
    """Outlook no está instalado o no se pudo iniciar via COM."""


def crear_borrador(
    to: str,
    cc: Iterable[str] | str | None,
    subject: str,
    html_body: str,
    attachments: Iterable[str | Path] | None = None,
):
    """Crea un borrador de Outlook y lo abre (no lo envía).

    Retorna el MailItem para que el usuario decida enviarlo o descartarlo.
    """
    try:
        import win32com.client as com
        import pywintypes
    except ImportError as exc:
        raise OutlookNoDisponibleError(
            "pywin32 no está instalado. Ejecútese: pip install pywin32"
        ) from exc

    try:
        outlook = com.Dispatch("Outlook.Application")
    except pywintypes.com_error as exc:
        raise OutlookNoDisponibleError(
            "No se pudo iniciar Outlook. Asegúrese de que esté instalado y con un perfil configurado."
        ) from exc

    try:
        mail = outlook.CreateItem(0)  # olMailItem
        mail.To = to or ""
        if cc:
            cc_str = "; ".join(cc) if isinstance(cc, (list, tuple)) else str(cc)
            mail.CC = cc_str
        mail.Subject = subject
        mail.HTMLBody = html_body
        for path in (attachments or []):
            mail.Attachments.Add(str(path))
        mail.Display(False)
        return mail
    except pywintypes.com_error as exc:
        raise OutlookNoDisponibleError(
            f"Outlook rechazó la creación del borrador: {exc}"
        ) from exc
