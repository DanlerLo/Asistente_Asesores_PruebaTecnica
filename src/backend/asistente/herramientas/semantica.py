from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from .corpus import Fragmento


class Embebedor(Protocol):
    def embeber(self, textos: Sequence[str]) -> Any: ...


class EmbebedorLocal:
    """Modelo multilingüe en CPU (ONNX); se descarga una vez en ``cache`` y después funciona sin red."""

    def __init__(self, modelo: str, cache: Path) -> None:
        from fastembed import TextEmbedding  # perezoso: con EMBEDDINGS=none no se carga

        self._modelo = TextEmbedding(modelo, cache_dir=str(cache))

    def embeber(self, textos: Sequence[str]) -> Any:
        return np.array(list(self._modelo.embed(list(textos))), dtype=np.float32)


def construir_embebedor(proveedor: str, modelo: str, cache: Path) -> Embebedor | None:
    return EmbebedorLocal(modelo, cache) if proveedor == "local" else None


@dataclass(frozen=True)
class LineaSimilar:
    fragmento: Fragmento
    linea: str
    similitud: float


@dataclass(frozen=True)
class ContextoSemantico:
    """Lo parecido por significado: enruta cuando BM25 no encuentra nada y amplía el contexto del LLM."""

    similares: tuple[LineaSimilar, ...]
    umbral: float
    max_fragmentos_llm: int

    def fragmentos(self, cantidad: int) -> list[Fragmento]:
        vistos: dict[str, Fragmento] = {}
        for similar in self.similares:
            if similar.similitud >= self.umbral:
                vistos.setdefault(similar.fragmento.id, similar.fragmento)
            if len(vistos) >= cantidad:
                break
        return list(vistos.values())

    def seccion_clara(self, umbral: float, margen: float) -> Fragmento | None:
        """La sección más parecida, solo si supera el umbral y le saca margen a la segunda (ADR-27)."""
        mejores: dict[str, tuple[float, Fragmento]] = {}
        for similar in self.similares:
            actual = mejores.get(similar.fragmento.id)
            if actual is None or similar.similitud > actual[0]:
                mejores[similar.fragmento.id] = (similar.similitud, similar.fragmento)
        orden = sorted(mejores.values(), key=lambda par: -par[0])
        if not orden or orden[0][0] < umbral:
            return None
        if len(orden) > 1 and orden[0][0] - orden[1][0] < margen:
            return None
        return orden[0][1]


def _normalizar_filas(matriz: Any) -> Any:
    normas = np.linalg.norm(matriz, axis=1, keepdims=True)
    return matriz / np.where(normas == 0, 1, normas)


class IndiceSemantico:
    """Una entrada por línea, con su sección como prefijo (la respuesta extractiva es una línea)."""

    def __init__(self, fragmentos: Sequence[Fragmento], embebedor: Embebedor) -> None:
        self._embebedor = embebedor
        self._entradas = [(f, linea) for f in fragmentos if f.ruta_seccion != "Índice" for linea in f.lineas]
        textos = [f"{f.ruta_seccion or f.documento}: {linea}" for f, linea in self._entradas]
        self._matriz = _normalizar_filas(np.asarray(embebedor.embeber(textos))) if textos else None

    @property
    def lineas(self) -> list[str]:
        return [linea for _, linea in self._entradas]

    def similares(self, pregunta: str) -> list[LineaSimilar]:
        if self._matriz is None:
            return []
        vector = _normalizar_filas(np.asarray(self._embebedor.embeber([pregunta])))[0]
        similitudes = self._matriz @ vector
        orden = np.argsort(-similitudes, kind="stable")
        salida = []
        for i in orden:
            fragmento, linea = self._entradas[i]
            salida.append(LineaSimilar(fragmento, linea, float(similitudes[i])))
        return salida
