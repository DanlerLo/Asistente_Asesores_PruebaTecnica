from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from ..dominio import RespuestaGenerada
from ..generacion.extractivo import responder_extractivo
from ..generacion.llm import ProveedorLLM, responder_con_llm
from ..herramientas.corpus import Fragmento
from ..herramientas.entidades import pertenece_a
from ..herramientas.recuperacion import Resultado
from .catalogo import listar_por_producto


class Agente(Protocol):
    @property
    def nombre(self) -> str: ...  # propiedad: así también la satisfacen las dataclasses frozen

    def responder(
        self,
        pregunta: str,
        resultados: list[Resultado],
        *,
        umbral_cobertura: float,
        proveedor_llm: ProveedorLLM | None = None,
        fragmentos: Sequence[Fragmento] = (),
    ) -> RespuestaGenerada: ...


@dataclass(frozen=True)
class AgenteDocumental:
    """Recibe todos los fragmentos: el enrutador elige quién responde, no filtra la evidencia."""

    nombre: str
    documentos: tuple[str, ...]  # nombres de documento sin extensión
    catalogo: bool = False  # RF-O9: lista un atributo por producto si la pregunta no nombra ninguno

    def atiende(self, archivo: str) -> bool:
        return pertenece_a(archivo, self.documentos)

    def responder(
        self,
        pregunta: str,
        resultados: list[Resultado],
        *,
        umbral_cobertura: float,
        proveedor_llm: ProveedorLLM | None = None,
        fragmentos: Sequence[Fragmento] = (),
    ) -> RespuestaGenerada:
        if self.catalogo:
            por_producto = listar_por_producto(pregunta, fragmentos, self.documentos)
            if por_producto is not None:
                return por_producto
        if proveedor_llm is not None:
            generada = responder_con_llm(pregunta, resultados, proveedor_llm)
            if generada is not None:
                return generada
        return responder_extractivo(pregunta, resultados, umbral_cobertura)
