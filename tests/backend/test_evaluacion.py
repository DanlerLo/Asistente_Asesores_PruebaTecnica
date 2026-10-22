"""Evaluación de corrección del motor extractivo (modo por defecto, sin LLM).

El banco (``test_banco.py``) detecta *cambios*; este conjunto mide *aciertos*: cada pregunta trae el dato
exacto que la respuesta debe contener según ``Data/`` o exige la frase canónica. La precisión no puede
bajar de ``PRECISION_MINIMA`` (trinquete): cuando un cambio del motor la mejora, se sube el mínimo.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from asistente.dominio import ESTADO_EXITOSA, ESTADO_SIN_INFO, FRASE_SIN_INFO
from asistente.infraestructura.persistencia import RepositorioConsultas
from asistente.orquestador import Orquestador

EVALUACION = Path(__file__).with_name("evaluacion.json")
PRECISION_MINIMA = 0.83  # línea base 47/97 (48,5 %); tras las mejoras del motor 81/97 (83,5 %); solo sube


def _acierta(caso: dict, estado: str, respuesta: str) -> bool:
    if any(texto in respuesta for texto in caso.get("no_contiene", [])):
        return False
    if caso.get("sin_informacion"):
        return estado == ESTADO_SIN_INFO and respuesta == FRASE_SIN_INFO
    return estado == ESTADO_EXITOSA and all(texto in respuesta for texto in caso["contiene"])


def evaluar(orquestador: Orquestador) -> tuple[float, list[str]]:
    casos = json.loads(EVALUACION.read_text(encoding="utf-8"))["preguntas"]
    fallos = []
    for caso in casos:
        r = orquestador.consultar(caso["pregunta"], contexto=caso.get("contexto"))
        if not _acierta(caso, r.estado, r.respuesta):
            fallos.append(caso["id"])
    return 1 - len(fallos) / len(casos), fallos


@pytest.fixture(scope="module")
def resultado(cfg, corpus) -> tuple[float, list[str]]:
    return evaluar(Orquestador(cfg, corpus, RepositorioConsultas(":memory:")))


def test_la_precision_no_baja_del_minimo(resultado):
    precision, fallos = resultado
    assert precision >= PRECISION_MINIMA, f"precisión {precision:.1%} < {PRECISION_MINIMA:.1%}; fallan: {fallos}"


def test_el_conjunto_esta_bien_formado():
    casos = json.loads(EVALUACION.read_text(encoding="utf-8"))["preguntas"]
    assert len({c["id"] for c in casos}) == len(casos) >= 90
    assert all(("contiene" in c) != bool(c.get("sin_informacion")) for c in casos)
