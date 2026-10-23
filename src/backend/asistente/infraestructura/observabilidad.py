"""Logging estructurado (JSON por línea) para trazabilidad y monitoreo.

Cada registro emitido mientras se atiende una solicitud lleva su ``request_id`` (RF-17): el middleware
lo fija en ``id_solicitud`` y la fábrica de registros lo copia, así no hay que pasarlo a mano por las capas.
"""
from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime

_CAMPOS_ESTANDAR = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {"message", "asctime"}

id_solicitud: ContextVar[str] = ContextVar("id_solicitud", default="")


def instalar_id_de_solicitud() -> None:
    """Agrega ``request_id`` a todo registro creado dentro de una solicitud (idempotente)."""
    fabrica = logging.getLogRecordFactory()
    if getattr(fabrica, "con_id_de_solicitud", False):
        return

    def crear_registro(*args, **kwargs) -> logging.LogRecord:
        registro = fabrica(*args, **kwargs)
        actual = id_solicitud.get()
        if actual and not hasattr(registro, "request_id"):
            registro.request_id = actual
        return registro

    crear_registro.con_id_de_solicitud = True  # type: ignore[attr-defined]
    logging.setLogRecordFactory(crear_registro)


class FormateadorJSON(logging.Formatter):
    def format(self, registro: logging.LogRecord) -> str:
        datos = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "nivel": registro.levelname,
            "logger": registro.name,
            "mensaje": registro.getMessage(),
        }
        for clave, valor in registro.__dict__.items():
            if clave not in _CAMPOS_ESTANDAR and not clave.startswith("_"):
                datos[clave] = valor
        if registro.exc_info:
            datos["excepcion"] = self.formatException(registro.exc_info)
        return json.dumps(datos, ensure_ascii=False, default=str)


def configurar_logging(nivel: str = "INFO") -> None:
    instalar_id_de_solicitud()
    # uvicorn instala sus manejadores de texto antes de importar la app: se redirigen a la raíz para que
    # todo salga en un solo formato (JSON) y una sola línea por evento.
    for nombre in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        registrador = logging.getLogger(nombre)
        registrador.handlers = []
        registrador.propagate = True
    raiz = logging.getLogger()
    if any(isinstance(h.formatter, FormateadorJSON) for h in raiz.handlers):
        return
    manejador = logging.StreamHandler(sys.stdout)
    manejador.setFormatter(FormateadorJSON())
    raiz.handlers = [manejador]
    raiz.setLevel(nivel.upper())
    # httpx registra cada URL solicitada en INFO: se silencia para no llenar los logs ni filtrar datos de la URL.
    logging.getLogger("httpx").setLevel(logging.WARNING)
