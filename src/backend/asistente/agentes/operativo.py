"""Agente operativo: procedimientos, políticas internas, manual del asesor y preguntas frecuentes.

También atiende los documentos que no tienen un agente asignado (ver ``Enrutador``).
"""
from __future__ import annotations

from .base import AgenteDocumental

AGENTE_OPERATIVO = AgenteDocumental(
    nombre="operativo",
    documentos=(
        "Procedimientos Operativos",
        "Políticas de Atención",
        "Manual del Asesor Comercial",
        "Preguntas Frecuentes",
    ),
)
