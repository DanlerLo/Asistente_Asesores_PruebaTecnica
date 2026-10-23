"""Prueba de arquitectura: las capas del paquete solo dependen hacia abajo (especificación 004, RNF-O3)."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

import asistente

from conftest import valores_restringidos

PAQUETE = Path(asistente.__file__).parent

# capa -> capas que NO puede importar
PROHIBIDAS = {
    "herramientas": {"agentes", "orquestador", "api", "generacion", "seguridad", "infraestructura"},
    "seguridad": {"agentes", "orquestador", "api", "generacion", "infraestructura"},
    "infraestructura": {"agentes", "orquestador", "api", "generacion", "herramientas"},
    # generacion y agentes no aplican seguridad ni persisten: eso lo hace el orquestador (hallazgo F11).
    "generacion": {"agentes", "orquestador", "api", "seguridad", "infraestructura"},
    "agentes": {"orquestador", "api", "seguridad", "infraestructura"},
    "orquestador": {"api"},
}


def _capas_importadas(archivo: Path) -> set[str]:
    """Primer componente bajo ``asistente`` de cada importación (absoluta o relativa)."""
    relativo = archivo.relative_to(PAQUETE).with_suffix("").parts
    capas: set[str] = set()
    for nodo in ast.walk(ast.parse(archivo.read_text(encoding="utf-8"))):
        if isinstance(nodo, ast.ImportFrom):
            if nodo.level:  # relativa: se resuelve contra el paquete del archivo
                base = list(relativo[:-1])[: len(relativo) - nodo.level]
                destino = [*base, *(nodo.module or "").split(".")]
                if not nodo.module:
                    destino.extend(alias.name for alias in nodo.names)
            elif nodo.module == "asistente":  # from asistente import orquestador
                capas.update(alias.name for alias in nodo.names)
                continue
            elif (nodo.module or "").startswith("asistente."):
                destino = nodo.module.split(".")[1:]
            else:
                continue
            capas.add(next((p for p in destino if p), ""))
        elif isinstance(nodo, ast.Import):
            for alias in nodo.names:
                if alias.name.startswith("asistente."):
                    capas.add(alias.name.split(".")[1])
    return capas


def test_existen_las_capas():
    for capa in [*PROHIBIDAS, "generacion/prompts"]:
        assert (PAQUETE / capa).is_dir(), f"falta la carpeta {capa}/"


@pytest.mark.parametrize("capa", sorted(PROHIBIDAS))
def test_las_capas_no_importan_hacia_arriba(capa: str):
    violaciones = {
        str(archivo.relative_to(PAQUETE)): sorted(_capas_importadas(archivo) & PROHIBIDAS[capa])
        for archivo in (PAQUETE / capa).rglob("*.py")
    }
    assert {a: c for a, c in violaciones.items() if c} == {}


def test_detecta_importaciones_de_capa_en_todas_sus_formas(tmp_path, monkeypatch):
    monkeypatch.setattr(sys.modules[__name__], "PAQUETE", tmp_path)
    archivo = tmp_path / "agentes" / "x.py"
    archivo.parent.mkdir()
    archivo.write_text(
        "from asistente import orquestador\nfrom asistente.api import app\nfrom ..orquestador import y\n",
        encoding="utf-8",
    )
    assert _capas_importadas(archivo) >= {"orquestador", "api"}


@pytest.mark.parametrize("modulo", ["dominio.py", "config.py"])
def test_modulos_transversales_no_importan_capas(modulo: str):
    assert _capas_importadas(PAQUETE / modulo) - {"dominio", "config"} == set()


def test_no_quedan_modulos_sueltos_en_la_raiz():
    sueltos = {p.name for p in PAQUETE.glob("*.py")}
    assert sueltos == {"__init__.py", "config.py", "dominio.py", "main.py"}


def test_ningun_archivo_contiene_valores_restringidos():
    """Los valores del documento restringido solo pueden estar en Data/ (se leen en tiempo de prueba)."""
    raiz = PAQUETE.parents[2]
    valores = valores_restringidos()
    revisados = [raiz / n for n in ("README.md", "AGENTS.md", ".env.example")]
    for carpeta in ("src", "tests", "docs", "sdd"):
        revisados += [p for p in (raiz / carpeta).rglob("*") if p.is_file() and "node_modules" not in p.parts
                      and p.suffix in {".py", ".ts", ".tsx", ".md", ".j2", ".txt", ".json", ".css", ".html"}]
    con_fuga = [str(p.relative_to(raiz)) for p in revisados if any(v in p.read_text(encoding="utf-8") for v in valores)]
    assert len(revisados) > 50 and con_fuga == []
