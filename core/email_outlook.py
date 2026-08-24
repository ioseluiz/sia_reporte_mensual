"""Creación de borradores en Outlook vía COM (win32com).

Debe llamarse desde el hilo principal (COM no es thread-safe con MTA).
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Iterable

log = logging.getLogger(__name__)


class OutlookNoDisponibleError(RuntimeError):
    """Outlook no está instalado o no se pudo iniciar via COM."""


_BODY_OPEN_RE = re.compile(r"<body\b[^>]*>", re.IGNORECASE)
_BODY_INNER_RE = re.compile(r"<body\b[^>]*>(.*)</body\s*>", re.IGNORECASE | re.DOTALL)


def _mezclar_con_firma(html_body: str, html_con_firma: str) -> str:
    """Inserta el contenido de html_body al inicio del <body> del HTMLBody
    que Outlook rellenó con la firma default. La firma queda al final.
    """
    inner = _BODY_INNER_RE.search(html_body)
    inner_content = inner.group(1) if inner else html_body

    match = _BODY_OPEN_RE.search(html_con_firma)
    if not match:
        # Sin <body> reconocible: fallback conservador, respeta la firma abajo
        return inner_content + html_con_firma
    idx = match.end()
    return html_con_firma[:idx] + inner_content + html_con_firma[idx:]


def crear_borrador(
    to: str,
    cc: Iterable[str] | str | None,
    subject: str,
    html_body: str,
    attachments: Iterable[str | Path] | None = None,
):
    """Crea un borrador de Outlook y lo abre (no lo envía).

    Preserva la firma default de Outlook (incluyendo imágenes embebidas vía CID)
    accediendo a GetInspector antes de mezclar el cuerpo. Retorna el MailItem
    para que el usuario decida enviarlo o descartarlo.
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

        # Dispara la inserción de la firma default de Outlook en HTMLBody.
        # Sin esto, el HTMLBody que asignamos sobrescribe todo y la firma
        # (con su imagen embebida vía CID) nunca aparece.
        _ = mail.GetInspector
        firma_html = mail.HTMLBody or ""

        mail.HTMLBody = _mezclar_con_firma(html_body, firma_html)

        for path in (attachments or []):
            mail.Attachments.Add(str(path))
        mail.Display(False)
        return mail
    except pywintypes.com_error as exc:
        raise OutlookNoDisponibleError(
            f"Outlook rechazó la creación del borrador: {exc}"
        ) from exc
