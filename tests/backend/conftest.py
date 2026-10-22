"""Fixtures compartidas para las pruebas del backend."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from asistente.api import crear_app
from asistente.config import RAIZ_PROYECTO, Configuracion
from asistente.herramientas.corpus import Corpus, cargar_corpus
from asistente.infraestructura.persistencia import RepositorioConsultas
from asistente.orquestador import Orquestador

DATA_DIR = RAIZ_PROYECTO / "Data"

# Cadenas ficticias del archivo restringido de ejemplo: deben estar fuera del índice
# y NUNCA aparecer en una respuesta. Se leen del archivo para no duplicarlas en el código.
_RESTRINGIDO = DATA_DIR / "Información restringida.md"


def valores_restringidos() -> list[str]:
    valores = []
    for linea in _RESTRINGIDO.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea and ("-" in linea or "_" in linea) and " " not in linea and not linea.startswith("#"):
            valores.append(linea)
    return valores


@pytest.fixture(scope="session")
def cfg() -> Configuracion:
    return Configuracion(data_dir=DATA_DIR)


@pytest.fixture(scope="session")
def corpus(cfg: Configuracion) -> Corpus:
    return cargar_corpus(cfg.data_dir, cfg.archivos_restringidos)


@pytest.fixture
def orquestador(cfg: Configuracion, corpus: Corpus) -> Orquestador:
    return Orquestador(cfg, corpus, RepositorioConsultas(":memory:"))


@pytest.fixture
def cliente(cfg: Configuracion, corpus: Corpus):
    app = crear_app(cfg=cfg, corpus=corpus, repositorio=RepositorioConsultas(":memory:"))
    with TestClient(app) as cliente_http:
        yield cliente_http


def crear_base_documental(directorio: Path, archivos: dict[str, str]) -> Path:
    """Escribe documentos de prueba en un directorio temporal y lo devuelve."""
    directorio.mkdir(parents=True, exist_ok=True)
    for nombre, contenido in archivos.items():
        (directorio / nombre).write_text(contenido, encoding="utf-8")
    return directorio


def orquestador_con(directorio: Path, archivos: dict[str, str], **ajustes) -> Orquestador:
    """Orquestador construido sobre una base documental ad hoc."""
    data_dir = crear_base_documental(directorio, archivos)
    cfg = Configuracion(data_dir=data_dir, **ajustes)
    corpus = cargar_corpus(data_dir, cfg.archivos_restringidos)
    return Orquestador(cfg, corpus, RepositorioConsultas(":memory:"))


class ProveedorFalso:
    """Proveedor LLM de prueba: devuelve una respuesta fija (o lanza) y registra las llamadas."""

    nombre = "falso"

    def __init__(self, respuesta: str | Exception) -> None:
        self.respuesta = respuesta
        self.llamadas: list[tuple[str, str]] = []

    def completar(self, sistema: str, usuario: str) -> str:
        self.llamadas.append((sistema, usuario))
        if isinstance(self.respuesta, Exception):
            raise self.respuesta
        return self.respuesta
