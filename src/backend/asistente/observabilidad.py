"""Logging estructurado (JSON por línea) para trazabilidad y monitoreo."""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

_CAMPOS_ESTANDAR = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {"message", "asctime"}


class FormateadorJSON(logging.Formatter):
    def format(self, registro: logging.LogRecord) -> str:
        datos = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
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
    raiz = logging.getLogger()
    if any(isinstance(h.formatter, FormateadorJSON) for h in raiz.handlers):
        return
    manejador = logging.StreamHandler(sys.stdout)
    manejador.setFormatter(FormateadorJSON())
    raiz.handlers = [manejador]
    raiz.setLevel(nivel.upper())
