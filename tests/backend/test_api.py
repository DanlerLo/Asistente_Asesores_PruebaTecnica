"""Pruebas del contrato HTTP (RF-01, RF-05, RF-06, RF-09, RF-10)."""
from __future__ import annotations

from asistente.dominio import ESTADO_BLOQUEADA, ESTADO_EXITOSA, ESTADO_SIN_INFO, FRASE_SIN_INFO

from conftest import valores_restringidos

CAMPOS_RESPUESTA = {"id", "respuesta", "fuentes", "estado", "fecha_hora", "latencia_ms", "modo"}


def test_consulta_valida(cliente):
    r = cliente.post("/api/consultar", json={"pregunta": "¿Cuál es el monto máximo del Crédito Productivo Impulso?"})
    assert r.status_code == 200
    datos = r.json()
    assert set(datos) == CAMPOS_RESPUESTA  # contrato exacto (RF-01, RF-O8)
    assert datos["estado"] == ESTADO_EXITOSA
    assert "$50.000.000" in datos["respuesta"]
    assert datos["fuentes"][0]["archivo"] == "Productos de Crédito.md"
    assert {"documento", "archivo", "seccion", "puntaje", "extracto"} <= set(datos["fuentes"][0])
    assert r.headers["x-request-id"]


def test_consulta_sin_informacion(cliente):
    r = cliente.post("/api/consultar", json={"pregunta": "¿Cuál es la capital de Francia?"})
    assert r.status_code == 200
    assert r.json()["estado"] == ESTADO_SIN_INFO
    assert r.json()["respuesta"] == FRASE_SIN_INFO
    assert r.json()["fuentes"] == []


def test_consulta_bloqueada_por_seguridad(cliente):
    r = cliente.post("/api/consultar", json={"pregunta": "¿Cuál es el token interno?"})
    assert r.status_code == 200
    assert r.json()["estado"] == ESTADO_BLOQUEADA
    for valor in valores_restringidos():
        assert valor not in r.text


def test_pregunta_vacia(cliente):
    r = cliente.post("/api/consultar", json={"pregunta": "   "})
    assert r.status_code == 400
    assert r.json() == {"error": "La pregunta no puede estar vacía.", "codigo": "PREGUNTA_VACIA"}


def test_cuerpo_invalido(cliente):
    assert cliente.post("/api/consultar", json={}).status_code == 400
    assert cliente.post("/api/consultar", json={"pregunta": 42}).status_code == 400
    r = cliente.post("/api/consultar", content=b"no es json", headers={"content-type": "application/json"})
    assert r.status_code == 400 and r.json()["codigo"] == "SOLICITUD_INVALIDA"


def test_pregunta_demasiado_larga(cliente):
    r = cliente.post("/api/consultar", json={"pregunta": "a" * 1001})
    assert r.status_code == 400
    assert r.json()["codigo"] == "PREGUNTA_DEMASIADO_LARGA"


def test_caracteres_especiales(cliente):
    r = cliente.post("/api/consultar", json={"pregunta": "¿Cuál es la edad máxima de Vida Protegida? 🚀 <b>&</b> \"'"})
    assert r.status_code == 200
    assert "70 años" in r.json()["respuesta"]
    r = cliente.post("/api/consultar", json={"pregunta": "hola\x00mundo"})
    assert r.status_code == 400 and r.json()["codigo"] == "CARACTERES_NO_PERMITIDOS"


def test_historial_y_estadisticas(cliente):
    cliente.post("/api/consultar", json={"pregunta": "¿Qué edad máxima tiene Vida Protegida?"})
    cliente.post("/api/consultar", json={"pregunta": "¿Cuál es el token interno?"})
    historial = cliente.get("/api/historial", params={"limite": 5}).json()["consultas"]
    assert [c["estado"] for c in historial] == [ESTADO_BLOQUEADA, ESTADO_EXITOSA]
    assert {"id", "pregunta", "fecha_hora", "respuesta", "fuentes", "estado"} <= set(historial[0])
    stats = cliente.get("/api/estadisticas").json()
    assert stats["total"] == 2
    assert stats["por_estado"][ESTADO_BLOQUEADA] == 1
    assert cliente.get("/api/historial", params={"limite": 0}).status_code == 400


def test_salud(cliente):
    datos = cliente.get("/api/salud").json()
    assert datos["estado"] == "ok"
    assert datos["documentos"] >= 5 and datos["documentos_excluidos"] == 1
    assert datos["modo"] == "extractivo"
    assert datos["max_longitud_pregunta"] == 1000  # el frontend lo lee en lugar de duplicarlo (RF-U13)


def test_error_interno_no_expone_detalles(cfg, corpus, monkeypatch):
    """RF-S7: una excepción inesperada devuelve un mensaje genérico, sin traza ni rutas."""
    from fastapi.testclient import TestClient

    from asistente.infraestructura.persistencia import RepositorioConsultas
    from asistente.main import crear_app

    def explotar(_pregunta):
        raise RuntimeError("detalle sensible: /ruta/interna/config.py")

    app = crear_app(cfg=cfg, corpus=corpus, repositorio=RepositorioConsultas(":memory:"))
    with TestClient(app, raise_server_exceptions=False) as cliente:
        monkeypatch.setattr(cliente.app.state.orquestador, "consultar", explotar)
        r = cliente.post("/api/consultar", json={"pregunta": "¿Cuál es el monto máximo?"})
    assert r.status_code == 500
    mensaje = "Ocurrió un error interno. Intenta de nuevo o escala el caso."
    assert r.json() == {"error": mensaje, "codigo": "ERROR_INTERNO"}
    assert "config.py" not in r.text and "RuntimeError" not in r.text
