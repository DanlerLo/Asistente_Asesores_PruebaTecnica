"""Carga de la base documental (``Data/*.md``): lectura, exclusión de restringidos y duplicados.

* La fragmentación vive en ``herramientas.markdown``.
* Qué es restringido y qué es una instrucción embebida lo decide la política de ingesta
  (``seguridad.ingesta``), que llega por inyección como ``FiltroIngesta``: esta capa no importa
  ``seguridad`` y no se puede cargar un corpus sin una política.
* **Documentos duplicados** (mismo contenido con otro nombre) se indexan una sola vez para no
  duplicar fuentes.
"""
from __future__ import annotations

import hashlib
import logging
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from .markdown import Fragmento, fragmentar

__all__ = ["Corpus", "FiltroIngesta", "Fragmento", "cargar_corpus", "fragmentar"]

log = logging.getLogger("asistente.corpus")

EXTENSIONES_SOPORTADAS = (".md", ".txt")


class FiltroIngesta(Protocol):
    """Reglas de seguridad de la ingesta (implementación: ``seguridad.ingesta.PoliticaIngesta``)."""

    def es_restringido(self, nombre: str, texto: str) -> bool: ...

    def extraer_secretos(self, texto: str) -> set[str]: ...

    def es_instruccion(self, linea: str) -> bool: ...


@dataclass
class Corpus:
    fragmentos: list[Fragmento] = field(default_factory=list)
    documentos: list[str] = field(default_factory=list)
    excluidos: list[str] = field(default_factory=list)
    duplicados: list[tuple[str, str]] = field(default_factory=list)
    secretos: frozenset[str] = frozenset()
    advertencias: list[str] = field(default_factory=list)

    @property
    def vacio(self) -> bool:
        return not self.fragmentos


def cargar_corpus(data_dir: Path, filtro: FiltroIngesta) -> Corpus:
    """Lee todos los documentos soportados de ``data_dir`` y construye el corpus."""
    corpus = Corpus()
    secretos: set[str] = set()
    if not data_dir.exists() or not data_dir.is_dir():
        corpus.advertencias.append("El directorio de datos (DATA_DIR) no existe.")  # sin ruta absoluta (RF-S10)
        log.warning("directorio de datos inexistente", extra={"data_dir": str(data_dir)})
        return corpus

    hashes: dict[str, str] = {}
    archivos = sorted(
        (p for p in data_dir.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONES_SOPORTADAS),
        key=lambda p: p.name,
    )
    for archivo in archivos:
        # macOS puede entregar nombres en NFD ("e" + tilde combinante); se citan siempre en NFC.
        nombre = unicodedata.normalize("NFC", archivo.name)
        try:
            texto = archivo.read_text(encoding="utf-8-sig")  # sin BOM: el «#» del título queda al inicio
        except UnicodeDecodeError:
            corpus.advertencias.append(f"{nombre}: no es UTF-8 válido, se omitió")
            continue
        if filtro.es_restringido(nombre, texto):
            corpus.excluidos.append(nombre)
            secretos |= filtro.extraer_secretos(texto)
            log.info("documento restringido excluido del índice", extra={"archivo": nombre})
            continue
        huella = hashlib.sha256(" ".join(texto.split()).encode("utf-8")).hexdigest()
        if huella in hashes:
            corpus.duplicados.append((nombre, hashes[huella]))
            corpus.advertencias.append(
                f"{nombre}: contenido duplicado de {hashes[huella]}, se indexó una sola vez"
            )
            continue
        hashes[huella] = nombre
        fragmentos, advertencias = fragmentar(texto, nombre, filtro.es_instruccion)
        corpus.fragmentos.extend(fragmentos)
        corpus.advertencias.extend(advertencias)
        corpus.documentos.append(nombre)

    corpus.secretos = frozenset(secretos)
    if corpus.vacio:
        corpus.advertencias.append("La base documental está vacía: toda consulta responderá sin información.")
        log.warning("base documental vacía", extra={"data_dir": str(data_dir)})
    log.info(
        "corpus cargado",
        extra={
            "documentos": len(corpus.documentos),
            "fragmentos": len(corpus.fragmentos),
            "excluidos": len(corpus.excluidos),
            "duplicados": len(corpus.duplicados),
        },
    )
    return corpus
