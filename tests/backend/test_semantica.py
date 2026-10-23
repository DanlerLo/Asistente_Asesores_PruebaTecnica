"""Recuperación semántica local y contexto ampliado del LLM (especificación 007), sin red."""
from __future__ import annotations

import logging
import re
import zlib
from dataclasses import replace

import numpy as np
import pytest

from asistente.config import Configuracion
from asistente.dominio import ESTADO_BLOQUEADA, ESTADO_EXITOSA, FRASE_SIN_INFO
from asistente.herramientas.corpus import Corpus
from asistente.herramientas.semantica import ContextoSemantico, IndiceSemantico, LineaSimilar, construir_embebedor
from asistente.herramientas.texto import STOPWORDS, normalizar
from asistente.infraestructura.persistencia import RepositorioConsultas
from asistente.orquestador import Orquestador

from conftest import ProveedorFalso, valores_restringidos

# Palabras del mismo grupo comparten dimensión: así se simula una paráfrasis sin palabras en común.
_CONCEPTOS = {
    "riesgos": "cobertura", "cubre": "cobertura", "coberturas": "cobertura", "incendio": "cobertura",
    "percances": "cobertura", "indemnizan": "cobertura",
    "negocios": "negocio", "negocio": "negocio",
}


class EmbebedorDePrueba:
    """Bolsa de conceptos con hash estable: determinista y sin modelo."""

    def __init__(self, falla: bool = False) -> None:
        self.falla = falla

    def embeber(self, textos):
        if self.falla:
            raise RuntimeError("modelo no disponible")
        matriz = np.zeros((len(textos), 512), dtype=np.float32)
        for fila, texto in enumerate(textos):
            for palabra in re.findall(r"[a-z0-9]+", normalizar(texto)):
                if palabra in STOPWORDS:
                    continue
                concepto = _CONCEPTOS.get(palabra, palabra)
                matriz[fila, zlib.crc32(concepto.encode()) % 512] += 1.0
        return matriz


def _orquestador(cfg: Configuracion, corpus: Corpus, **ajustes) -> Orquestador:
    cfg = replace(cfg, **{"umbral_semantico": 0.5, **ajustes})
    return Orquestador(cfg, corpus, RepositorioConsultas(":memory:"), embebedor=EmbebedorDePrueba())


# --------------------------------------------------------------------------- índice (RF-E2)

def test_el_indice_tiene_una_entrada_por_linea(corpus: Corpus):
    indice = IndiceSemantico(corpus.fragmentos, EmbebedorDePrueba())
    esperadas = sum(len(f.lineas) for f in corpus.fragmentos if f.ruta_seccion != "Índice")
    assert len(indice.lineas) == esperadas


def test_el_indice_no_contiene_lineas_restringidas(corpus: Corpus):
    texto = " ".join(IndiceSemantico(corpus.fragmentos, EmbebedorDePrueba()).lineas)
    assert not any(valor in texto for valor in valores_restringidos())


# --------------------------------------------------------------------------- uso de la similitud (RF-E3, RF-E4, RF-E6)

def test_sin_embeddings_la_parafrasis_no_se_responde(cfg, corpus):
    pregunta = "¿Qué riesgos cubre el seguro para negocios?"
    assert Orquestador(cfg, corpus, RepositorioConsultas(":memory:")).consultar(pregunta).respuesta == FRASE_SIN_INFO


def test_con_similitud_clara_se_lee_la_seccion_completa(cfg, corpus):
    """RF-E4 / ADR-27: la similitud elige qué sección leer; la respuesta es la sección literal, con su cita."""
    resultado = _orquestador(cfg, corpus).consultar("¿Qué riesgos cubre el seguro para negocios?")
    assert resultado.estado == ESTADO_EXITOSA
    assert "Coberturas: Incendio; Inundación; Daños accidentales." in resultado.respuesta
    assert [f["seccion"] for f in resultado.fuentes] == ["Negocio Seguro"]


def test_seccion_clara_exige_umbral_y_margen(corpus):
    """Dos secciones casi igual de parecidas: elegir una sería adivinar (ADR-27)."""
    a, b = corpus.fragmentos[0], corpus.fragmentos[1]

    def contexto(*pares):
        return ContextoSemantico(tuple(LineaSimilar(f, f.lineas[0], s) for f, s in pares), 0.6, 12)

    assert contexto((a, 0.80), (a, 0.79), (b, 0.70)).seccion_clara(0.65, 0.06) == a  # misma sección no compite
    assert contexto((a, 0.80), (b, 0.77)).seccion_clara(0.65, 0.06) is None  # margen insuficiente
    assert contexto((a, 0.60), (b, 0.40)).seccion_clara(0.65, 0.06) is None  # bajo el umbral


def test_un_producto_nombrado_sin_el_dato_no_se_rescata_por_similitud(cfg, corpus):
    """Si la pregunta nombra el producto y no tiene ese dato, mostrar su ficha parecería una respuesta."""
    resultado = _orquestador(cfg, corpus).consultar("¿Qué edad máxima tiene Negocio Seguro?")
    assert resultado.respuesta == FRASE_SIN_INFO


def test_sin_resultados_lexicos_enruta_por_similitud(cfg, corpus):
    resultado = _orquestador(cfg, corpus).consultar("¿Qué percances indemnizan?")
    assert resultado.agente == "microseguros"


def test_con_groq_lo_parecido_llega_al_llm(cfg, corpus):
    proveedor = ProveedorFalso("Coberturas: Incendio\nFuente: Portafolio de Microseguros.md › Negocio Seguro")
    cfg = replace(cfg, umbral_semantico=0.5)
    orquestador = Orquestador(cfg, corpus, RepositorioConsultas(":memory:"), proveedor, embebedor=EmbebedorDePrueba())
    resultado = orquestador.consultar("¿Qué percances indemnizan?")
    assert resultado.estado == ESTADO_EXITOSA and len(proveedor.llamadas) == 1
    _, usuario = proveedor.llamadas[0]
    assert 'archivo="Portafolio de Microseguros.md"' in usuario


@pytest.mark.parametrize(
    "pregunta, estado",
    [
        ("¿Cuál es la tasa del crédito de vivienda?", "Sin información suficiente"),
        ("¿Cuál es el token interno?", ESTADO_BLOQUEADA),
        ("¿Y el plazo?", "Sin información suficiente"),
    ],
)
def test_la_similitud_no_rescata_bloqueos_ni_inexistentes(cfg, corpus, pregunta, estado):
    proveedor = ProveedorFalso("no debería llamarse")
    cfg = replace(cfg, umbral_semantico=0.01)
    orquestador = Orquestador(cfg, corpus, RepositorioConsultas(":memory:"), proveedor, embebedor=EmbebedorDePrueba())
    assert orquestador.consultar(pregunta).estado == estado
    assert proveedor.llamadas == []


# --------------------------------------------------------------------------- degradación y configuración (RF-E1, RF-E7)

def test_si_el_modelo_falla_sigue_con_recuperacion_lexica(cfg, corpus, caplog: pytest.LogCaptureFixture):
    with caplog.at_level(logging.WARNING, logger="asistente"):
        repositorio = RepositorioConsultas(":memory:")
        orquestador = Orquestador(cfg, corpus, repositorio, embebedor=EmbebedorDePrueba(falla=True))
    assert any("recuperación léxica" in r.getMessage() for r in caplog.records)
    resultado = orquestador.consultar("¿Cuál es el monto máximo del Crédito Productivo Impulso?")
    assert "$50.000.000" in resultado.respuesta


def test_embeddings_activados_por_defecto_al_arrancar(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """RF-E1: el servicio arranca con embeddings; en código y en pruebas el valor por defecto no carga modelos."""
    monkeypatch.delenv("EMBEDDINGS", raising=False)
    assert Configuracion.desde_entorno().embeddings == "local"
    assert Configuracion().embeddings == "none"
    assert construir_embebedor("none", "cualquiera", tmp_path) is None


def test_la_suite_nunca_carga_el_modelo_real():
    """RNF-E2: el fixture automático de conftest fija EMBEDDINGS=none para toda la suite."""
    assert Configuracion.desde_entorno().embeddings == "none"


@pytest.mark.parametrize(
    "ajustes",
    [{"embeddings": "openai"}, {"umbral_semantico": 0.0}, {"llm_max_fragmentos": 0}],
)
def test_configuracion_de_embeddings_invalida(ajustes):
    with pytest.raises(ValueError):
        Configuracion(**ajustes)


# --------------------------------------------------------------------------- contexto del LLM (RF-E5)

def test_el_llm_recibe_contexto_ampliado_con_tope(cfg, corpus):
    proveedor = ProveedorFalso("Prima mensual: $9.900\nFuente: Portafolio de Microseguros.md › Vida Protegida")
    cfg = replace(cfg, llm_max_fragmentos=6)
    orquestador = Orquestador(cfg, corpus, RepositorioConsultas(":memory:"), proveedor, embebedor=EmbebedorDePrueba())
    pregunta = "¿Cuál es la prima mensual de Vida Protegida?"
    orquestador.consultar(pregunta)
    _, usuario = proveedor.llamadas[0]
    assert usuario.count("<fragmento ") == 6
    de_bm25 = {r.fragmento.ruta_seccion for r in orquestador.indice.buscar(pregunta, top_k=cfg.top_k)}
    secciones = set(re.findall(r'seccion="([^"]+)"', usuario))
    assert secciones - de_bm25, "el contexto debe incluir fragmentos que BM25 no trajo"
