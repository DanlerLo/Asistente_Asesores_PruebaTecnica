"""Pruebas del orquestador, el enrutador y los agentes (especificación 004: RF-O1..O8, RNF-O1)."""
from __future__ import annotations

import logging

import pytest

from asistente.dominio import ESTADO_BLOQUEADA, ESTADO_EXITOSA, ESTADO_SIN_INFO, FRASE_SIN_INFO
from asistente.orquestador import Orquestador

from conftest import ProveedorFalso, orquestador_con

AGENTES = {"credito", "microseguros", "operativo", "fuera_de_dominio"}
PREGUNTA_FUERA_DE_DOMINIO = "¿Quién ganó el partido de fútbol ayer?"


@pytest.mark.parametrize(
    ("pregunta", "agente"),
    [
        ("¿Cuál es el monto máximo del Crédito Productivo Impulso?", "credito"),
        ("¿Cuál es la cobertura máxima de Vida Protegida?", "microseguros"),
        ("¿Cuál es el tiempo objetivo de gestión de PQR?", "operativo"),
        (PREGUNTA_FUERA_DE_DOMINIO, "fuera_de_dominio"),
    ],
)
def test_enrutamiento_por_dominio(orquestador: Orquestador, pregunta: str, agente: str):
    assert orquestador.consultar(pregunta).agente == agente


def test_fuera_de_dominio_responde_frase_canonica_sin_llm(orquestador: Orquestador):
    proveedor = ProveedorFalso("no debería llamarse")
    orquestador.proveedor_llm = proveedor
    resultado = orquestador.consultar(PREGUNTA_FUERA_DE_DOMINIO)
    assert resultado.estado == ESTADO_SIN_INFO
    assert resultado.respuesta == FRASE_SIN_INFO
    assert resultado.fuentes == []
    assert resultado.motivo_ruta == "sin_fragmentos"
    assert proveedor.llamadas == []


def test_agente_de_dominio_usa_el_llm_configurado(orquestador: Orquestador):
    proveedor = ProveedorFalso("Cobertura máxima: $20.000.000\nFuente: Portafolio de Microseguros.md › Vida Protegida")
    orquestador.proveedor_llm = proveedor
    resultado = orquestador.consultar("¿Cuál es la cobertura máxima de Vida Protegida?")
    assert resultado.agente == "microseguros" and resultado.modo == "falso"
    assert len(proveedor.llamadas) == 1


def test_documento_sin_agente_va_al_operativo(tmp_path):
    orquestador = orquestador_con(
        tmp_path / "data",
        {"Horarios de Oficina.md": "# Horarios de Oficina\n\n## Atención\n\nHorario de atención: 8:00 a 17:00\n"},
    )
    resultado = orquestador.consultar("¿Cuál es el horario de atención de la oficina?")
    assert resultado.agente == "operativo"
    assert resultado.estado == ESTADO_EXITOSA


def test_base_vacia_va_a_fuera_de_dominio(tmp_path):
    orquestador = orquestador_con(tmp_path / "vacia", {})
    resultado = orquestador.consultar("¿Cuál es el monto máximo del Crédito Productivo Impulso?")
    assert resultado.agente == "fuera_de_dominio"
    assert resultado.motivo_ruta == "base_vacia"
    assert resultado.respuesta == FRASE_SIN_INFO


def test_pregunta_bloqueada_no_llega_a_ningun_agente(orquestador: Orquestador):
    proveedor = ProveedorFalso("no debería llamarse")
    orquestador.proveedor_llm = proveedor
    resultado = orquestador.consultar("¿Cuál es el token interno del sistema?")
    assert resultado.estado == ESTADO_BLOQUEADA
    assert resultado.agente == ""
    assert proveedor.llamadas == []


def test_enrutamiento_es_determinista(orquestador: Orquestador):
    pregunta = "¿Cuál es la diferencia de plazo entre el Crédito Agro Crece y el Crédito Mujer Emprende?"
    primera, segunda = orquestador.consultar(pregunta), orquestador.consultar(pregunta)
    assert (primera.agente, primera.respuesta) == (segunda.agente, segunda.respuesta)


def test_log_incluye_agente_y_motivo(orquestador: Orquestador, caplog: pytest.LogCaptureFixture):
    with caplog.at_level(logging.INFO, logger="asistente.orquestador"):
        orquestador.consultar("¿Cuál es el monto máximo del Crédito Productivo Impulso?")
    registro = next(r for r in caplog.records if r.getMessage() == "consulta atendida")
    assert registro.agente == "credito"
    assert registro.motivo_ruta == "documento:Productos de Crédito.md"


def test_salud_lista_agentes(cliente):
    assert set(cliente.get("/api/salud").json()["agentes"]) == AGENTES
