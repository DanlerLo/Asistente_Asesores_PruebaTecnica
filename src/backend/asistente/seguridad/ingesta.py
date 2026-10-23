"""Política de seguridad de la ingesta de documentos (hallazgo F5).

Las reglas que deciden qué entra al índice viven aquí, junto a los demás guardrails, y no en el
cargador de documentos:

* **Los documentos son datos, nunca instrucciones.** Una línea o un encabezado con apariencia de
  instrucción para un asistente se descarta (RF-S5, RF-S11). Es una heurística de mejor esfuerzo: la
  garantía real es no indexar lo restringido y el filtro de salida.
* **Lo restringido no se indexa.** Un archivo restringido por nombre o por su marca
  ``CLASIFICACIÓN: CONFIDENCIAL`` solo aporta valores sensibles al filtro de salida.

``herramientas.corpus`` no puede importar ``seguridad`` (regla de capas): recibe esta política por
inyección (``FiltroIngesta``). ``cargar_corpus_seguro`` es la forma de cargar el corpus con ella.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ..herramientas.corpus import Corpus, cargar_corpus
from ..herramientas.texto import normalizar

PATRONES_INYECCION: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"ignora(r)?\s+(todas?\s+)?(las?|tus?|sus?|estas?)?\s*(instrucciones|reglas|politicas|restricciones)",
        r"olvida(r)?\s+(todas?\s+)?(las?|tus?)\s+(instrucciones|reglas)",
        r"entregue?\s+toda\s+la\s+informacion",
        r"prompt\s+(administrativo|del\s+sistema|de\s+sistema)",
        r"system\s+prompt",
        r"si\s+un\s+usuario\s+pregunta.*\b(entregue?|revele?|muestre?)\b",
        r"\bactua\s+como\b",
        # RF-S11: paráfrasis dirigidas al asistente («Nota para el asistente: …», «Haz caso omiso de …»).
        r"\b(nota|instruccion|instrucciones|mensaje)\s+(para|al)\s+(el\s+|la\s+)?(asistente|modelo|ia|bot|chatbot|agente)\b",
        r"\b(haz|has|hacer|hagan?)\s+caso\s+omiso\b",
        r"^(asistente|modelo|ia|bot|chatbot|agente)\s*:",
        r"\b(ignore|disregard)\s+(all\s+)?(previous|prior|above|earlier)\b",
    )
)
PATRON_CONFIDENCIAL = re.compile(
    r"clasificacion\s*:\s*confidencial|informacion\s+restringida", re.IGNORECASE
)
_RE_SECRETO = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-]{4,}")


def es_instruccion_sospechosa(linea: str) -> bool:
    """True si la línea parece una instrucción dirigida a un asistente."""
    texto = normalizar(linea)
    return any(p.search(texto) for p in PATRONES_INYECCION)


def es_restringido(nombre: str, texto: str, archivos_restringidos: tuple[str, ...]) -> bool:
    nombre_norm = normalizar(nombre)
    if any(nombre_norm == normalizar(r) for r in archivos_restringidos):
        return True
    cabecera = normalizar("\n".join(texto.splitlines()[:10]))
    return bool(PATRON_CONFIDENCIAL.search(cabecera))


def extraer_secretos(texto: str) -> set[str]:
    """Valores con aspecto de credencial/identificador técnico (``INT-1234-...``)."""
    secretos: set[str] = set()
    for token in _RE_SECRETO.findall(texto):
        tiene_digito = any(c.isdigit() for c in token)
        if (tiene_digito or "_" in token or "-" in token) and len(token) >= 6:
            secretos.add(token)
    return secretos


@dataclass(frozen=True)
class PoliticaIngesta:
    """Implementa ``herramientas.corpus.FiltroIngesta`` con las reglas de este módulo."""

    archivos_restringidos: tuple[str, ...] = ()

    def es_restringido(self, nombre: str, texto: str) -> bool:
        return es_restringido(nombre, texto, self.archivos_restringidos)

    def extraer_secretos(self, texto: str) -> set[str]:
        return extraer_secretos(texto)

    def es_instruccion(self, linea: str) -> bool:
        return es_instruccion_sospechosa(linea)


def cargar_corpus_seguro(data_dir: Path, archivos_restringidos: tuple[str, ...] = ()) -> Corpus:
    """Carga ``data_dir`` aplicando la política de ingesta (única forma de cargar el corpus en la app)."""
    return cargar_corpus(data_dir, PoliticaIngesta(archivos_restringidos))
