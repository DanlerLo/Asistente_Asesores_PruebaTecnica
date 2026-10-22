"""Agente de productos de crédito (montos, plazos, requisitos, actividades financiables)."""
from __future__ import annotations

from .base import AgenteDocumental

AGENTE_CREDITO = AgenteDocumental(nombre="credito", documentos=("Productos de Crédito",))
