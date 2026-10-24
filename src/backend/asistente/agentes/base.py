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
from ..herramientas.semantica import ContextoSemantico
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
        semantico: ContextoSemantico | None = None,
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
        semantico: ContextoSemantico | None = None,
    ) -> RespuestaGenerada:
        if self.catalogo:
            por_producto = listar_por_producto(pregunta, fragmentos, self.documentos)
            if por_producto is not None:
                return por_producto
        if proveedor_llm is not None:
            contexto = self._contexto_llm(resultados, fragmentos, semantico)
            generada = responder_con_llm(pregunta, contexto, proveedor_llm)
            if generada is not None:
                return generada
        # Nunca una línea elegida por similitud (ADR-25); la lectura por sección la decide el orquestador (ADR-27).
        return responder_extractivo(pregunta, resultados, umbral_cobertura)

    def _contexto_llm(
        self, resultados: list[Resultado], fragmentos: Sequence[Fragmento], semantico: ContextoSemantico | None
    ) -> list[Resultado]:
        """RF-E5: lo mejor de BM25, lo parecido por significado y el resto del documento del agente, con tope."""
        if semantico is None:
            return resultados
        tope = semantico.max_fragmentos_llm
        mitad = (tope + 1) // 2
        candidatos = [
            *(r.fragmento for r in resultados[:mitad]),
            *semantico.fragmentos(tope),
            *(f for f in fragmentos if f.ruta_seccion != "Índice" and self.atiende(f.archivo)),
            *(r.fragmento for r in resultados[mitad:]),
        ]
        por_id = {r.fragmento.id: r for r in resultados}
        elegidos = list(dict.fromkeys(candidatos))[:tope]
        return [por_id.get(f.id) or Resultado(f, 0.0, frozenset(), 0.0) for f in elegidos]
