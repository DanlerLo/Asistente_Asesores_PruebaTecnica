"""Contrato común de los agentes y agente documental reutilizable.

Un agente responde una consulta dentro de su dominio a partir de los
fragmentos que recuperó el orquestador. No aplica guardrails (los aplica el
orquestador antes y después de cualquier agente) ni persiste nada.

Los agentes son deterministas: no deciden con un LLM a quién delegar ni qué
herramienta usar. El LLM, si está configurado, solo redacta la respuesta a
partir de los fragmentos y siempre tiene *fallback* al motor extractivo.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ..dominio import RespuestaGenerada
from ..generacion.extractivo import responder_extractivo
from ..generacion.llm import ProveedorLLM, responder_con_llm
from ..herramientas.recuperacion import Resultado
from ..herramientas.texto import normalizar


class Agente(Protocol):
    nombre: str

    def responder(
        self,
        pregunta: str,
        resultados: list[Resultado],
        *,
        umbral_cobertura: float,
        proveedor_llm: ProveedorLLM | None = None,
    ) -> RespuestaGenerada: ...


@dataclass(frozen=True)
class AgenteDocumental:
    """Agente de dominio: atiende las preguntas cuyo mejor fragmento pertenece a sus documentos.

    Recibe todos los fragmentos recuperados (el enrutamiento decide quién
    responde, no filtra evidencia), de modo que una comparación o una pregunta
    que cruza documentos conserva su respuesta.
    """

    nombre: str
    documentos: tuple[str, ...]  # nombres de documento sin extensión

    def atiende(self, archivo: str) -> bool:
        """``archivo`` pertenece a este agente (comparación sin tildes ni mayúsculas)."""
        return normalizar(Path(archivo).stem) in {normalizar(d) for d in self.documentos}

    def responder(
        self,
        pregunta: str,
        resultados: list[Resultado],
        *,
        umbral_cobertura: float,
        proveedor_llm: ProveedorLLM | None = None,
    ) -> RespuestaGenerada:
        if proveedor_llm is not None:
            generada = responder_con_llm(pregunta, resultados, proveedor_llm)
            if generada is not None:
                return generada
        return responder_extractivo(pregunta, resultados, umbral_cobertura)
