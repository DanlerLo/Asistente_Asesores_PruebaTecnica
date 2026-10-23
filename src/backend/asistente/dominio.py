"""Modelos y constantes del dominio compartidos por todas las capas.

Aquí viven los tres estados de una consulta, la frase canónica sin
información y la forma de una respuesta con sus fuentes. No depende de
ningún otro módulo del paquete.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

ESTADO_EXITOSA = "Exitosa"
ESTADO_SIN_INFO = "Sin información suficiente"
ESTADO_BLOQUEADA = "Bloqueada por seguridad"
ESTADOS = (ESTADO_EXITOSA, ESTADO_SIN_INFO, ESTADO_BLOQUEADA)

FRASE_SIN_INFO = "No tengo información suficiente para responder."
MENSAJE_BLOQUEO = (
    "Esta consulta no puede ser atendida: involucra información restringida "
    "(credenciales, configuraciones internas, datos de otros clientes o intentos de "
    "alterar las reglas del asistente). Si requieres esa información, escala el caso "
    "al área responsable y registra el evento."
)


@dataclass(frozen=True)
class Fuente:
    documento: str
    archivo: str
    seccion: str
    puntaje: float
    extracto: str = ""

    def a_dict(self) -> dict:
        return {
            "documento": self.documento,
            "archivo": self.archivo,
            "seccion": self.seccion,
            "puntaje": round(self.puntaje, 3),
            "extracto": self.extracto,
        }


@dataclass
class RespuestaGenerada:
    texto: str
    estado: str
    fuentes: list[Fuente] = field(default_factory=list)
    modo: str = "extractivo"


def respuesta_sin_informacion(modo: str = "extractivo") -> RespuestaGenerada:
    return RespuestaGenerada(texto=FRASE_SIN_INFO, estado=ESTADO_SIN_INFO, fuentes=[], modo=modo)


def respuesta_bloqueada(fuentes: Sequence[Fuente] = ()) -> RespuestaGenerada:
    """Mensaje de bloqueo; cita las políticas que lo respaldan solo si existen en el corpus (hallazgo F6)."""
    texto = MENSAJE_BLOQUEO
    if fuentes:
        texto += " Fuente: " + "; ".join(f"{f.archivo} › {f.seccion}" for f in fuentes)
    return RespuestaGenerada(texto=texto, estado=ESTADO_BLOQUEADA, fuentes=list(fuentes), modo="guardrail")
