"""Recuperación léxica (BM25) sobre los fragmentos del corpus.

Sin dependencias externas: el corpus es pequeño y una implementación propia
de BM25 es suficiente, determinista y fácil de probar. Cuando la pregunta
nombra una entidad (p. ej. un producto: "Crédito Productivo Impulso") la
búsqueda se restringe a los fragmentos de esa entidad para evitar responder
con datos de otro producto ("bloqueo por entidad").
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from .corpus import Fragmento
from .texto import raices_unicas, tokenizar


@dataclass(frozen=True)
class Resultado:
    fragmento: Fragmento
    puntaje: float
    terminos: frozenset[str]  # raíces de la pregunta presentes en el fragmento
    cobertura: float  # proporción de raíces útiles de la pregunta cubiertas por el fragmento
    consulta_util: frozenset[str] = frozenset()  # raíces de la pregunta que existen en el corpus


class IndiceBM25:
    def __init__(self, fragmentos: list[Fragmento], k1: float = 1.5, b: float = 0.75) -> None:
        self.fragmentos = list(fragmentos)
        self.k1, self.b = k1, b
        self._tf: list[Counter[str]] = [Counter(tokenizar(f.texto_indexable)) for f in self.fragmentos]
        self._dl: list[int] = [sum(c.values()) for c in self._tf]
        self._avgdl: float = (sum(self._dl) / len(self._dl)) if self._dl else 0.0
        df: Counter[str] = Counter()
        for conteo in self._tf:
            df.update(conteo.keys())
        total = len(self.fragmentos)
        self._idf: dict[str, float] = {
            t: math.log(1.0 + (total - n + 0.5) / (n + 0.5)) for t, n in df.items()
        }
        # Fragmentos "Índice" por documento, para preguntas sobre el documento completo.
        self._indices_documento: list[tuple[int, frozenset[str]]] = [
            (i, frozenset(raices_unicas(f.documento)))
            for i, f in enumerate(self.fragmentos)
            if f.ruta_seccion == "Índice"
        ]

    @property
    def vacio(self) -> bool:
        return not self.fragmentos

    def _candidatos(self, consulta: set[str]) -> list[int]:
        """Índices de fragmentos a considerar (bloqueo por entidad si aplica).

        Los fragmentos "Índice" no compiten aquí: solo se usan cuando la pregunta
        trata sobre el documento completo (ver ``_priorizar_indice``).
        """
        bloqueados: list[int] = []
        normales: list[int] = []
        for i, fragmento in enumerate(self.fragmentos):
            if fragmento.ruta_seccion == "Índice":
                continue
            normales.append(i)
            raices = fragmento.entidad_raices
            if not raices or len(raices) > 5:
                continue
            coincidencias = len(raices & consulta)
            if coincidencias >= 2 and coincidencias >= len(raices) - 1:
                bloqueados.append(i)
        return bloqueados or normales

    def buscar(self, pregunta: str, top_k: int = 3) -> list[Resultado]:
        consulta = raices_unicas(pregunta)
        if not consulta or self.vacio:
            return []
        # Las palabras que no existen en ningún documento no pueden emparejarse con nada:
        # no penalizan la cobertura (p. ej. saludos o ruido en preguntas largas).
        consulta_util = frozenset(t for t in consulta if t in self._idf) or frozenset(consulta)
        resultados: list[Resultado] = []
        for i in self._candidatos(consulta):
            tf, dl = self._tf[i], self._dl[i]
            puntaje = 0.0
            terminos: set[str] = set()
            for termino in consulta:
                frecuencia = tf.get(termino, 0)
                if not frecuencia:
                    continue
                terminos.add(termino)
                norma = frecuencia + self.k1 * (1 - self.b + self.b * dl / self._avgdl)
                puntaje += self._idf[termino] * frecuencia * (self.k1 + 1) / norma
            if puntaje > 0:
                resultados.append(
                    Resultado(
                        fragmento=self.fragmentos[i],
                        puntaje=puntaje,
                        terminos=frozenset(terminos),
                        cobertura=len(terminos) / len(consulta_util),
                        consulta_util=consulta_util,
                    )
                )
        resultados.sort(key=lambda r: (-r.puntaje, r.fragmento.id))
        resultados = self._priorizar_indice(consulta, resultados)
        return resultados[:top_k]

    def _priorizar_indice(self, consulta: set[str], resultados: list[Resultado]) -> list[Resultado]:
        """Si la pregunta solo nombra un documento ("¿qué productos de crédito existen?"),
        su fragmento Índice pasa al primer lugar."""
        mejor = resultados[0].puntaje if resultados else 1.0
        for i, raices_titulo in self._indices_documento:
            if consulta <= raices_titulo:
                fragmento = self.fragmentos[i]
                resto = [r for r in resultados if r.fragmento.id != fragmento.id]
                return [Resultado(fragmento, mejor, frozenset(consulta), 1.0, frozenset(consulta)), *resto]
        return resultados
