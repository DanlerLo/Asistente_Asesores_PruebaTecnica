"""Agentes especializados por dominio y agente de fuera de dominio."""
from .base import Agente, AgenteDocumental
from .credito import AGENTE_CREDITO
from .fuera_de_dominio import AGENTE_FUERA_DE_DOMINIO, AgenteFueraDeDominio
from .microseguros import AGENTE_MICROSEGUROS
from .operativo import AGENTE_OPERATIVO

__all__ = [
    "Agente",
    "AgenteDocumental",
    "AgenteFueraDeDominio",
    "AGENTE_CREDITO",
    "AGENTE_MICROSEGUROS",
    "AGENTE_OPERATIVO",
    "AGENTE_FUERA_DE_DOMINIO",
]
