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
    """Se inyecta desde ``seguridad.ingesta`` para que esta capa no importe ``seguridad``."""

    def motivo_restriccion(self, nombre: str, texto: str) -> str | None: ...

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
    """Excluye restringidos y duplicados; de los restringidos solo conserva sus secretos para filtrarlos."""
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
    raiz = data_dir.resolve()
    for archivo in archivos:
        # macOS puede entregar nombres en NFD ("e" + tilde combinante); se citan siempre en NFC.
        nombre = unicodedata.normalize("NFC", archivo.name)
        if archivo.is_symlink() and not archivo.resolve().is_relative_to(raiz):
            corpus.advertencias.append(f"{nombre}: enlace a un archivo fuera del directorio de datos, se ignoró")
            continue
        try:
            texto = archivo.read_text(encoding="utf-8-sig")  # sin BOM: el «#» del título queda al inicio
        except UnicodeDecodeError:
            corpus.advertencias.append(f"{nombre}: no es UTF-8 válido, se omitió")
            continue
        motivo = filtro.motivo_restriccion(nombre, texto)
        if motivo:
            corpus.excluidos.append(nombre)
            corpus.advertencias.append(f"{nombre}: excluido del índice ({motivo})")  # el motivo, nunca el texto
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
