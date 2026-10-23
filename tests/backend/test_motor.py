"""Pruebas de recuperación (BM25) y del motor extractivo (RF-03, RF-04, RF-05)."""
from __future__ import annotations

import pytest

from asistente.dominio import ESTADO_EXITOSA, ESTADO_SIN_INFO, FRASE_SIN_INFO
from asistente.generacion.extractivo import responder_extractivo
from asistente.herramientas.corpus import Corpus
from asistente.herramientas.recuperacion import IndiceBM25


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
        (
            "¿Cuál es el monto máximo del Crédito Productivo Impulso?",
            "$50.000.000",
            "Crédito Productivo Impulso > Condiciones",
        ),
        ("¿Qué edad máxima tiene Vida Protegida?", "70 años", "Vida Protegida"),
        ("¿Cuál es el tiempo objetivo de un PQR?", "5 días hábiles", "Gestión de PQR"),
        (
            "¿Qué actividades financia el Crédito Agro Crece?",
            "Sistemas de riego",
            "Crédito Agro Crece > Actividades financiables",
        ),
        ("¿Qué seguro cubre incendios?", "Incendio", "Negocio Seguro"),
        ("¿Qué documentos son válidos para actualizar datos?", "Certificado laboral", "Actualización de Datos"),
        (
            "¿Cuáles son los pasos de una solicitud de crédito?",
            "1. Recepción de documentos.",
            "Solicitud de Crédito",
        ),
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
    pregunta = "¿Cuál es la diferencia de plazo entre el Crédito Agro Crece y el Crédito Mujer Emprende?"
    respuesta = responder(indice, pregunta)
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


@pytest.mark.parametrize(
    "pregunta",
    [
        "¿Cuánto tiempo es válido para una PQR?",  # «válido» ≈ «Validación documental» de microseguros
        "¿Qué tiempo de validación tiene una PQR?",
    ],
)
def test_parafrasis_no_responde_con_datos_de_otro_tema(indice: IndiceBM25, pregunta: str):
    """RF-12: «PQR» nombra una sección; un fragmento que no la menciona no puede responder."""
    respuesta = responder_extractivo(pregunta, indice.buscar(pregunta, top_k=8), umbral_cobertura=0.3)
    assert all(f.archivo != "Portafolio de Microseguros.md" for f in respuesta.fuentes)
    assert "10 a 15 días" not in respuesta.texto
    assert respuesta.estado == ESTADO_SIN_INFO or {f.archivo for f in respuesta.fuentes} == {
        "Procedimientos Operativos.md"
    }


@pytest.mark.parametrize(
    ("pregunta", "esperado"),
    [
        # RF-12: respuestas generales que no repiten el nombre del producto siguen siendo válidas.
        ("¿Se puede pagar anticipado el Crédito Agro Crece?", "pago anticipado sin penalidad"),
        ("¿Puede un cliente con Negocio Seguro contratar otro microseguro?", "Los microseguros son independientes"),
        ("¿El estudio de crédito del Agro Crece tiene costo?", "no tiene costo"),
        ("¿Tiene costo la solicitud de crédito?", "no tiene costo"),
        ("¿Cuánto se demora la aprobación de una solicitud de crédito y el desembolso?", "3 días hábiles"),
        ("¿Cómo presento una reclamación de Vida Protegida?", "Se reporta el evento"),
    ],
)
def test_rf12_no_descarta_respuestas_generales(indice: IndiceBM25, pregunta: str, esperado: str):
    respuesta = responder_extractivo(pregunta, indice.buscar(pregunta, top_k=8), umbral_cobertura=0.3)
    assert respuesta.estado == ESTADO_EXITOSA
    assert esperado in respuesta.texto


def test_no_responde_con_datos_de_otro_producto(indice: IndiceBM25):
    """Agro Crece sí tiene periodo de gracia; Impulso no: no debe contestar con el de Agro Crece."""
    respuesta = responder(indice, "¿Cuál es el periodo de gracia del Crédito Productivo Impulso?")
    assert "Agro" not in respuesta.texto and "6 meses" not in respuesta.texto


# --------------------------------------------------------------------------- RF-13: productos y atributos inexistentes


@pytest.mark.parametrize(
    "pregunta",
    [
        "¿Cuál es la tasa del crédito hipotecario?",
        "¿Cuál es el monto máximo del Crédito Vivienda Feliz?",
        "¿Cuál es la prima mensual del Seguro Exequial Plus?",
        "¿Cuánto cubre el microseguro de mascotas?",
        "¿Qué requisitos tiene el crédito para vivienda?",
        "¿Cuál es el salario de un asesor comercial?",
    ],
)
def test_producto_o_atributo_inexistente_no_responde_con_otro(orquestador, pregunta: str):
    """No debe responder con datos de otro producto (p. ej. la tasa del Mujer Emprende para «hipotecario»)."""
    resultado = orquestador.consultar(pregunta)
    assert resultado.estado == ESTADO_SIN_INFO
    assert resultado.respuesta == FRASE_SIN_INFO and resultado.fuentes == []


@pytest.mark.parametrize(
    "pregunta",
    [
        "¿Qué cubre el seguro Negocio Seguro?",
        "¿Cuánta plata me prestan como máximo en el Productivo Impulso?",
        "Un cliente quiere saber cuándo le desembolsan el crédito que le aprobaron ayer",
        "¿Qué dice el Manual del Asesor Comercial?",
        "¿Qué actividades financia el crédito para compra de maquinaria?",
        "¿Qué crédito financia infraestructura rural?",
        "¿Qué crédito sirve para estudiantes universitarios?",
    ],
)
def test_palabras_desconocidas_que_no_nombran_producto_siguen_respondiendo(orquestador, pregunta: str):
    """RF-13 no debe tomarlas por productos inexistentes (si responden bien lo mide test_evaluacion.py)."""
    assert orquestador.consultar(pregunta).motivo_ruta != "inexistente"


# ------------------------------------------------------- vocabulario y preguntas frecuentes (RF-14, RF-22)

@pytest.mark.parametrize(
    "pregunta, esperado",
    [
        ("¿Hasta cuánta plata prestan en el Agro Crece?", "$80.000.000"),
        ("¿Cuánto hay que pagar al mes por Vida Protegida?", "$9.900"),
        ("¿Cuánto tiempo tengo para pagar el Crédito Productivo Impulso?", "60 meses"),
        ("¿Cuándo me entregan el dinero del crédito?", "2 días hábiles"),
        ("¿Los domingos atiende la línea telefónica?", "Lunes a sábado"),
        ("¿Quién puede ver los datos de los clientes?", "personal autorizado"),
        ("¿Qué pasos sigue el banco para aprobar un crédito?", "Validación de identidad"),
        ("¿Cada cuánto debe un cliente actualizar su información?", "12 meses"),
    ],
)
def test_frases_del_asesor_llegan_al_termino_del_documento(indice: IndiceBM25, pregunta: str, esperado: str):
    r = responder(indice, pregunta)
    assert r.estado == ESTADO_EXITOSA and esperado in r.texto, r.texto


def test_pregunta_frecuente_contenida_completa_responde_primero(indice: IndiceBM25):
    r = responder(indice, "¿Qué pasa si un cliente no actualiza sus datos y pide un nuevo crédito?")
    assert r.fuentes[0].seccion == "¿Qué pasa si un cliente no actualiza sus datos?"
    assert "no es posible tramitar" in r.texto


def test_titulo_de_pregunta_frecuente_no_se_nombra_a_medias(indice: IndiceBM25):
    """«tiempo» y «crédito» no bastan para traer «¿Se puede pagar un crédito antes de tiempo?»."""
    r = responder(indice, "¿Cuál es el tiempo de respuesta de la solicitud de crédito?")
    assert [f.seccion for f in r.fuentes] == ["Solicitud de Crédito"]
    assert "3 días hábiles" in r.texto and "pago anticipado" not in r.texto


def test_subseccion_corta_del_producto_nombrado_responde_entera(indice: IndiceBM25):
    r = responder(indice, "¿Un crédito de 10 millones en el Impulso necesita codeudor?")
    assert "firma personal" in r.texto and "codeudor" in r.texto


def test_sin_producto_nombrado_no_responde_con_otro_producto(indice: IndiceBM25):
    pregunta = "Hola, tengo un cliente comerciante que quiere un crédito de 20 millones, ¿qué garantía le piden?"
    assert "Educativo" not in responder(indice, pregunta).texto


def test_cobrar_interes_no_se_confunde_con_el_costo_del_estudio(indice: IndiceBM25):
    r = responder(indice, "¿Qué interés cobra el Crédito Productivo Impulso?")
    assert "24,5 %" in r.texto
