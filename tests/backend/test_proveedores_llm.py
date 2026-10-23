"""Pruebas de los proveedores LLM y su configuración (RF-11). Sin red: ``ClienteHttpLLM.post`` se reemplaza."""
from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

from asistente.api import crear_app
from asistente.config import Configuracion
from asistente.dominio import ESTADO_EXITOSA
from asistente.generacion import llm
from asistente.generacion.llm import MODELO_GROQ_POR_DEFECTO, URL_GROQ, ProveedorGroq, construir_proveedor
from asistente.orquestador import Orquestador

from conftest import ProveedorFalso


def _metodo(funcion):
    """Adapta ``funcion(url, **kw)`` para reemplazar ``ClienteHttpLLM.post`` (recibe también el cliente)."""
    return lambda _cliente, url, **kwargs: funcion(url, **kwargs)


class RespuestaHttpFalsa:
    def __init__(self, cuerpo: dict) -> None:
        self.cuerpo = cuerpo
        self.headers: dict[str, str] = {}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.cuerpo


@pytest.fixture
def solicitudes(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Captura cada llamada a ``httpx.post`` y responde como Groq (contenido + razonamiento aparte)."""
    capturadas: list[dict] = []

    def post_falso(url: str, **kwargs) -> RespuestaHttpFalsa:
        capturadas.append({"url": url, **kwargs})
        mensaje = {"role": "assistant", "content": "  Monto máximo: $50.000.000  ", "reasoning": "pensando…"}
        return RespuestaHttpFalsa({"choices": [{"message": mensaje}]})

    monkeypatch.setattr(llm.ClienteHttpLLM, "post", _metodo(post_falso))
    return capturadas


def test_groq_envia_solicitud_compatible_con_openai(solicitudes: list[dict]):
    proveedor = ProveedorGroq(api_key="prueba", modelo="openai/gpt-oss-20b", timeout=5.0)
    assert proveedor.completar("instrucciones", "fragmentos y pregunta") == "Monto máximo: $50.000.000"
    solicitud = solicitudes[0]
    assert solicitud["url"] == URL_GROQ == "https://api.groq.com/openai/v1/chat/completions"
    assert solicitud["headers"]["Authorization"] == "Bearer prueba"
    assert solicitud["timeout"] == 5.0
    cuerpo = solicitud["json"]
    assert cuerpo["model"] == "openai/gpt-oss-20b"
    assert cuerpo["messages"] == [
        {"role": "system", "content": "instrucciones"},
        {"role": "user", "content": "fragmentos y pregunta"},
    ]
    assert cuerpo["temperature"] == 0
    assert cuerpo["include_reasoning"] is False  # el razonamiento nunca llega a la respuesta
    assert cuerpo["stream"] is False


def test_groq_respuesta_sin_choices_devuelve_texto_vacio(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(llm.ClienteHttpLLM, "post", _metodo(lambda url, **kw: RespuestaHttpFalsa({"choices": []})))
    assert ProveedorGroq(api_key="prueba", modelo="m", timeout=1.0).completar("s", "u") == ""


def test_construir_proveedor_groq_usa_modelo_por_defecto():
    proveedor = construir_proveedor(Configuracion(llm_provider="groq", groq_api_key="prueba"))
    assert isinstance(proveedor, ProveedorGroq)
    assert proveedor.modelo == MODELO_GROQ_POR_DEFECTO == "openai/gpt-oss-20b"
    assert proveedor.nombre == "groq"


def test_construir_proveedor_groq_respeta_llm_model():
    cfg = Configuracion(llm_provider="groq", groq_api_key="prueba", llm_model="openai/gpt-oss-120b")
    assert construir_proveedor(cfg).modelo == "openai/gpt-oss-120b"


def test_groq_sin_clave_falla_con_mensaje_claro():
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        construir_proveedor(Configuracion(llm_provider="groq"))


def test_configuracion_lee_groq_del_entorno(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", " prueba ")
    cfg = Configuracion.desde_entorno()
    assert cfg.llm_provider == "groq" and cfg.groq_api_key == "prueba"


def test_por_defecto_no_hay_proveedor(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert construir_proveedor(Configuracion.desde_entorno()) is None


def test_orquestador_con_groq_vacio_degrada_al_extractivo(
    orquestador: Orquestador, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(llm.ClienteHttpLLM, "post", _metodo(lambda url, **kw: RespuestaHttpFalsa({"choices": []})))
    orquestador.proveedor_llm = ProveedorGroq(api_key="prueba", modelo="m", timeout=1.0)
    resultado = orquestador.consultar("¿Cuál es el monto máximo del Crédito Productivo Impulso?")
    assert resultado.estado == ESTADO_EXITOSA and resultado.modo == "extractivo"
    assert "$50.000.000" in resultado.respuesta


@pytest.mark.parametrize("motivo", ["length", "content_filter"])
def test_groq_respuesta_incompleta_degrada_al_extractivo(monkeypatch: pytest.MonkeyPatch, motivo: str):
    # Cortada por límite de tokens (o filtrada): no se puede entregar un monto a medias como "Exitosa".
    cuerpo = {"choices": [{"finish_reason": motivo, "message": {"content": "El monto máximo es de $"}}]}
    monkeypatch.setattr(llm.ClienteHttpLLM, "post", _metodo(lambda url, **kw: RespuestaHttpFalsa(cuerpo)))
    assert ProveedorGroq(api_key="prueba", modelo="m", timeout=1.0).completar("s", "u") == ""


def test_groq_solo_envia_parametros_de_razonamiento_a_gpt_oss(solicitudes: list[dict]):
    ProveedorGroq(api_key="prueba", modelo="qwen/qwen3.8-27b", timeout=1.0).completar("s", "u")
    ProveedorGroq(api_key="prueba", modelo="openai/gpt-oss-120b", timeout=1.0).completar("s", "u")
    otro, gpt_oss = solicitudes[0]["json"], solicitudes[1]["json"]
    assert "reasoning_effort" not in otro and "include_reasoning" not in otro
    assert gpt_oss["reasoning_effort"] == "low" and gpt_oss["include_reasoning"] is False


def test_fuentes_son_solo_las_secciones_citadas_por_el_llm(orquestador: Orquestador):
    # El texto cita una sola sección; la lista de fuentes no debe incluir otras del mismo archivo.
    texto = "El tiempo objetivo es de 5 días hábiles.\nFuente: Procedimientos Operativos.md › Gestión de PQR"
    orquestador.proveedor_llm = ProveedorFalso(texto)
    resultado = orquestador.consultar("¿Cuántos días tengo para resolver una queja de PQR?")
    citadas = [(f["archivo"], f["seccion"]) for f in resultado.fuentes]
    assert citadas == [("Procedimientos Operativos.md", "Gestión de PQR")]


def test_fuentes_sin_cita_reconocible_usan_el_fragmento_principal(orquestador: Orquestador):
    orquestador.proveedor_llm = ProveedorFalso("El monto máximo es $50.000.000.")
    resultado = orquestador.consultar("¿Cuál es el monto máximo del Crédito Productivo Impulso?")
    assert [f["seccion"] for f in resultado.fuentes] == ["Crédito Productivo Impulso > Condiciones"]


@pytest.mark.parametrize("proveedor", ["", "  ", "mistral", "openai"])
def test_llm_provider_vacio_o_desconocido_arranca_sin_conexion(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, proveedor: str
):
    """RF-11: un valor que no sirve no impide arrancar; el servicio queda en modo sin conexión y lo advierte."""
    monkeypatch.setenv("LLM_PROVIDER", proveedor)
    with caplog.at_level(logging.WARNING, logger="asistente"):
        cfg = Configuracion.desde_entorno()
    assert cfg.llm_provider == "none" and construir_proveedor(cfg) is None
    assert any("LLM_PROVIDER" in r.getMessage() for r in caplog.records)


def test_groq_sin_clave_en_el_entorno_arranca_sin_conexion(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "  ")
    with caplog.at_level(logging.WARNING, logger="asistente"):
        cfg = Configuracion.desde_entorno()
    assert cfg.llm_provider == "none" and construir_proveedor(cfg) is None
    assert any("GROQ_API_KEY" in r.getMessage() for r in caplog.records)


def test_el_backend_arranca_y_responde_con_groq_sin_clave(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "consultas.db"))
    with TestClient(crear_app(Configuracion.desde_entorno())) as cliente:
        r = cliente.post("/api/consultar", json={"pregunta": "¿Cuál es el monto máximo del Crédito Agro Crece?"})
    assert r.status_code == 200 and r.json()["modo"] == "extractivo"


def test_groq_reutiliza_un_cliente_http_y_lo_cierra(solicitudes: list[dict]):
    """F4: un ``httpx.Client`` por proveedor (pool y keep-alive), cerrado al apagar el servicio."""
    proveedor = ProveedorGroq(api_key="prueba", modelo="m", timeout=5.0)
    cliente = proveedor._cliente
    proveedor.completar("s", "u")
    proveedor.completar("s", "u")
    assert proveedor._cliente is cliente and len(solicitudes) == 2
    proveedor.cerrar()
    assert cliente.is_closed


def test_el_prompt_del_sistema_se_renderiza_solo_al_usarse():
    """F4: importar el paquete no lee plantillas si el LLM está desactivado."""
    assert llm.instrucciones_sistema() is llm.instrucciones_sistema()  # una sola vez, en caché
