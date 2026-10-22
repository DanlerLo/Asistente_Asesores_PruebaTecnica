"""Robustez del contrato HTTP y de la configuración (RF-17, RF-18, RF-19)."""
from __future__ import annotations

import json
import logging

import pytest
from fastapi.testclient import TestClient

from asistente.config import Configuracion
from asistente.infraestructura.observabilidad import FormateadorJSON, id_solicitud, instalar_id_de_solicitud
from asistente.infraestructura.persistencia import RepositorioConsultas
from asistente.main import crear_app

# --- RF-17: identificador de solicitud ---------------------------------------------------------------------

def test_id_de_solicitud_valido_se_respeta(cliente: TestClient):
    r = cliente.get("/api/salud", headers={"x-request-id": "abc-123_X.9"})
    assert r.headers["x-request-id"] == "abc-123_X.9"


@pytest.mark.parametrize("id_recibido", ["con espacios", "a" * 65, "x/../y", "<script>", "a;b"])
def test_id_de_solicitud_invalido_se_reemplaza(cliente: TestClient, id_recibido: str):
    r = cliente.get("/api/salud", headers={"x-request-id": id_recibido})
    devuelto = r.headers["x-request-id"]
    assert devuelto != id_recibido and len(devuelto) == 12 and devuelto.isalnum()


def test_el_id_de_solicitud_llega_a_los_logs_de_la_consulta(cliente: TestClient, caplog: pytest.LogCaptureFixture):
    with caplog.at_level(logging.INFO, logger="asistente"):
        cliente.post("/api/consultar", json={"pregunta": "¿Monto máximo?"}, headers={"x-request-id": "traza-42"})
    registros = [r for r in caplog.records if r.name.startswith("asistente.orquestador")]
    assert registros and all(getattr(r, "request_id", None) == "traza-42" for r in registros)


def test_el_formateador_incluye_el_id_de_solicitud():
    instalar_id_de_solicitud()
    marca = id_solicitud.set("traza-7")
    try:
        registro = logging.getLogRecordFactory()("asistente", logging.INFO, "", 0, "hola", None, None)
    finally:
        id_solicitud.reset(marca)
    assert json.loads(FormateadorJSON().format(registro))["request_id"] == "traza-7"


def test_el_error_interno_conserva_el_id_de_solicitud(cfg, corpus, monkeypatch):
    def explotar(*_args):
        raise RuntimeError("fallo")

    app = crear_app(cfg=cfg, corpus=corpus, repositorio=RepositorioConsultas(":memory:"))
    with TestClient(app, raise_server_exceptions=False) as cliente:
        monkeypatch.setattr(cliente.app.state.orquestador, "consultar", explotar)
        r = cliente.post("/api/consultar", json={"pregunta": "x"}, headers={"x-request-id": "falla-1"})
    assert r.status_code == 500 and r.headers.get("x-request-id") == "falla-1"


# --- RF-18: parámetros inválidos -------------------------------------------------------------------------

@pytest.mark.parametrize("ident", ["²", "¹²", "٣", "007x"])
def test_id_de_consulta_con_digitos_no_ascii_es_400(cliente: TestClient, ident: str):
    r = cliente.get(f"/api/consultas/{ident}")
    assert r.status_code == 400 and r.json()["codigo"] == "ID_INVALIDO"


@pytest.mark.parametrize("limite", ["abc", "0", "201"])
def test_limite_de_historial_invalido_explica_el_parametro(cliente: TestClient, limite: str):
    r = cliente.get("/api/historial", params={"limite": limite})
    assert r.status_code == 400
    mensaje = "El parámetro 'limite' debe ser un entero entre 1 y 200."
    assert r.json() == {"error": mensaje, "codigo": "SOLICITUD_INVALIDA"}


# --- RF-19: configuración inválida ---------------------------------------------------------------------

@pytest.mark.parametrize(
    "ajustes",
    [
        {"top_k": 0},
        {"max_longitud_pregunta": 0},
        {"umbral_cobertura": 0.0},
        {"umbral_cobertura": 1.5},
        {"llm_timeout_segundos": 0.0},
        {"llm_provider": "openai"},
    ],
)
def test_configuracion_invalida_se_rechaza(ajustes: dict):
    with pytest.raises(ValueError):
        Configuracion(**ajustes)


@pytest.mark.parametrize("variable, valor", [("TOP_K", "abc"), ("TOP_K", "-3"), ("UMBRAL_COBERTURA", "mucho")])
def test_variable_de_entorno_invalida_nombra_la_variable(monkeypatch: pytest.MonkeyPatch, variable: str, valor: str):
    monkeypatch.setenv(variable, valor)
    with pytest.raises(ValueError, match=variable):
        Configuracion.desde_entorno()
