"""Pruebas de recuperación (BM25) y del motor extractivo (RF-03, RF-04, RF-05)."""
from __future__ import annotations

import pytest

from asistente.corpus import Corpus
from asistente.motor import ESTADO_EXITOSA, ESTADO_SIN_INFO, FRASE_SIN_INFO, responder_extractivo
from asistente.recuperacion import IndiceBM25


@pytest.fixture(scope="module")
def indice(corpus: Corpus) -> IndiceBM25:
    return IndiceBM25(corpus.fragmentos)


def responder(indice: IndiceBM25, pregunta: str):
    return responder_extractivo(pregunta, indice.buscar(pregunta, top_k=8), umbral_cobertura=0.5)


# --------------------------------------------------------------------------- recuperación


def test_bm25_prioriza_la_seccion_correcta(indice: IndiceBM25):
    resultados = indice.buscar("¿Cuál es el monto máximo del Crédito Productivo Impulso?")
    assert resultados[0].fragmento.ruta_seccion == "Crédito Productivo Impulso > Condiciones"
    assert resultados[0].cobertura == 1.0


def test_bm25_bloqueo_por_entidad_restringe_a_los_fragmentos_del_producto(indice: IndiceBM25):
    resultados = indice.buscar("¿Cuál es el periodo de gracia del Crédito Productivo Impulso?")
    assert resultados, "debe haber candidatos"
    assert all(r.fragmento.entidad == "Crédito Productivo Impulso" for r in resultados)


def test_bm25_sin_terminos_utiles_devuelve_vacio(indice: IndiceBM25):
    assert indice.buscar("¿?") == []
    assert indice.buscar("el la de") == []


def test_indice_vacio_no_falla():
    assert IndiceBM25([]).buscar("monto máximo") == []


# --------------------------------------------------------------------------- motor extractivo


@pytest.mark.parametrize(
    "pregunta, esperado, seccion",
    [
        ("¿Cuál es el monto máximo del Crédito Productivo Impulso?", "$50.000.000", "Crédito Productivo Impulso > Condiciones"),
        ("¿Qué edad máxima tiene Vida Protegida?", "70 años", "Vida Protegida"),
        ("¿Cuál es el tiempo objetivo de un PQR?", "5 días hábiles", "Gestión de PQR"),
        ("¿Qué actividades financia el Crédito Agro Crece?", "Sistemas de riego", "Crédito Agro Crece > Actividades financiables"),
        ("¿Qué seguro cubre incendios?", "Incendio", "Negocio Seguro"),
        ("¿Qué documentos son válidos para actualizar datos?", "Certificado laboral", "Actualización de Datos"),
        ("¿Cuáles son los pasos de una solicitud de crédito?", "1. Recepción de documentos.", "Solicitud de Crédito"),
        ("¿Qué productos de crédito existen?", "Crédito Educativo Avanza", "Índice"),
    ],
)
def test_responde_con_la_linea_correcta_y_cita_la_fuente(indice, pregunta, esperado, seccion):
    respuesta = responder(indice, pregunta)
    assert respuesta.estado == ESTADO_EXITOSA
    assert esperado in respuesta.texto
    assert respuesta.fuentes[0].seccion == seccion
    assert "Fuente" in respuesta.texto and respuesta.fuentes[0].archivo in respuesta.texto


def test_comparacion_entre_dos_productos_usa_dos_fuentes(indice: IndiceBM25):
    respuesta = responder(indice, "¿Cuál es la diferencia de plazo entre el Crédito Agro Crece y el Crédito Mujer Emprende?")
    assert respuesta.estado == ESTADO_EXITOSA
    assert "84 meses" in respuesta.texto and "48 meses" in respuesta.texto
    assert {f.seccion for f in respuesta.fuentes} == {
        "Crédito Agro Crece > Condiciones",
        "Crédito Mujer Emprende > Condiciones",
    }


@pytest.mark.parametrize(
    "pregunta",
    [
        "¿Cuál es la capital de Francia?",
        "¿Qué es la fotosíntesis?",
        "¿Cuál es el periodo de gracia del Crédito Productivo Impulso?",  # atributo inexistente para ese producto
        "¿Cuál es la cobertura máxima del Crédito Agro Crece?",  # atributo de otro tipo de producto
    ],
)
def test_sin_evidencia_responde_la_frase_canonica(indice, pregunta):
    respuesta = responder(indice, pregunta)
    assert respuesta.estado == ESTADO_SIN_INFO
    assert respuesta.texto == FRASE_SIN_INFO
    assert respuesta.fuentes == []


def test_no_responde_con_datos_de_otro_producto(indice: IndiceBM25):
    """Agro Crece sí tiene periodo de gracia; Impulso no: no debe contestar con el de Agro Crece."""
    respuesta = responder(indice, "¿Cuál es el periodo de gracia del Crédito Productivo Impulso?")
    assert "Agro" not in respuesta.texto and "6 meses" not in respuesta.texto
