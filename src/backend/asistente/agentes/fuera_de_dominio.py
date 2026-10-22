"""Agente de fuera de dominio: preguntas sin relación con la base documental.

Responde siempre la frase canónica, sin fuentes y sin invocar un LLM (no hay
evidencia que redactar y así no se gasta una llamada). La prueba técnica fija
tres estados, por lo que el resultado es *Sin información suficiente*; el
motivo queda en el log como ``motivo_ruta``.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ..dominio import RespuestaGenerada, respuesta_sin_informacion
from ..generacion.llm import ProveedorLLM
from ..herramientas.corpus import Fragmento
from ..herramientas.recuperacion import Resultado


@dataclass(frozen=True)
class AgenteFueraDeDominio:
    nombre: str = "fuera_de_dominio"

    def responder(
        self,
        pregunta: str,
        resultados: list[Resultado],
        *,
        umbral_cobertura: float,
        proveedor_llm: ProveedorLLM | None = None,
        fragmentos: Sequence[Fragmento] = (),
    ) -> RespuestaGenerada:
        return respuesta_sin_informacion()


AGENTE_FUERA_DE_DOMINIO = AgenteFueraDeDominio()
