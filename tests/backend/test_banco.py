"""Banco de regresión con ~300 preguntas reales y paráfrasis (RF-03, RF-05, RF-12, RF-13, RF-S4).

Dos niveles:
* **Invariantes** sobre todas las preguntas: estado válido, frase canónica exacta sin fuentes,
  respuestas exitosas citadas, ningún valor restringido y determinismo.
* **Foto** (``banco_esperado.json``): estado y fuentes de cada pregunta. Un cambio del motor que
  altere alguna respuesta hace fallar la prueba y obliga a revisarlo; si el cambio es intencional,
  se regenera con ``ACTUALIZAR_BANCO=1 python3 -m pytest tests/backend/test_banco.py``.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from asistente.dominio import ESTADO_EXITOSA, ESTADO_SIN_INFO, ESTADOS, FRASE_SIN_INFO
from asistente.orquestador import Orquestador

from conftest import valores_restringidos

BANCO = Path(__file__).with_name("banco_preguntas.txt")
ESPERADO = Path(__file__).with_name("banco_esperado.json")


def _preguntas() -> list[str]:
    lineas = BANCO.read_text(encoding="utf-8").splitlines()
    return [linea.strip() for linea in lineas if linea.strip() and not linea.startswith("#")]


def _respuestas(orquestador: Orquestador) -> dict[str, dict]:
    salida = {}
    for pregunta in _preguntas():
        resultado = orquestador.consultar(pregunta)
        salida[pregunta] = {
            "estado": resultado.estado,
            "fuentes": [f"{f['archivo']} › {f['seccion']}" for f in resultado.fuentes],
            "respuesta": resultado.respuesta,
        }
    return salida


@pytest.fixture(scope="module")
def respuestas(cfg, corpus) -> dict[str, dict]:
    from asistente.infraestructura.persistencia import RepositorioConsultas

    return _respuestas(Orquestador(cfg, corpus, RepositorioConsultas(":memory:")))


def test_el_banco_no_contiene_valores_restringidos():
    texto = BANCO.read_text(encoding="utf-8")
    assert not any(valor in texto for valor in valores_restringidos())


def test_invariantes_en_todo_el_banco(respuestas: dict[str, dict]):
    secretos = valores_restringidos()
    assert len(respuestas) >= 250
    for pregunta, r in respuestas.items():
        assert r["estado"] in ESTADOS, pregunta
        if r["estado"] == ESTADO_SIN_INFO:
            assert r["respuesta"] == FRASE_SIN_INFO and r["fuentes"] == [], pregunta
        if r["estado"] == ESTADO_EXITOSA:
            assert r["fuentes"], pregunta
            assert "Fuente" in r["respuesta"], pregunta  # Política de Citas
        assert not any(valor in r["respuesta"] for valor in secretos), pregunta


def test_el_banco_es_determinista(cfg, corpus, respuestas: dict[str, dict]):
    from asistente.infraestructura.persistencia import RepositorioConsultas

    assert _respuestas(Orquestador(cfg, corpus, RepositorioConsultas(":memory:"))) == respuestas


def test_el_banco_coincide_con_la_foto(respuestas: dict[str, dict]):
    foto = {p: {"estado": r["estado"], "fuentes": r["fuentes"]} for p, r in respuestas.items()}
    if os.getenv("ACTUALIZAR_BANCO") == "1":
        ESPERADO.write_text(json.dumps(foto, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    esperado = json.loads(ESPERADO.read_text(encoding="utf-8"))
    preguntas = esperado.keys() | foto.keys()
    cambios = {p: (esperado.get(p), foto.get(p)) for p in preguntas if esperado.get(p) != foto.get(p)}
    assert cambios == {}, f"{len(cambios)} respuestas cambiaron (esperado, actual): {cambios}"
