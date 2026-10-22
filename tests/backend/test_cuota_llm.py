"""Cuota de la API gratuita y modo sin conexión (especificación 005). Sin red: ``httpx.post`` se reemplaza."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from asistente.api import crear_app
from asistente.config import Configuracion
from asistente.generacion import llm
from asistente.generacion.llm import CuotaLLM, ProveedorGroq, leer_cuota
from asistente.herramientas.corpus import Corpus
from asistente.infraestructura.persistencia import RepositorioConsultas
from asistente.orquestador import Orquestador

from conftest import ProveedorFalso

PREGUNTA = "¿Cuál es el monto máximo del Crédito Productivo Impulso?"
CABECERAS = {
    "x-ratelimit-limit-requests": "1000",
    "x-ratelimit-remaining-requests": "997",
    "x-ratelimit-reset-requests": "2m59.56s",
    "x-ratelimit-limit-tokens": "8000",
    "x-ratelimit-remaining-tokens": "7500",
    "x-ratelimit-reset-tokens": "7.66s",
}


class RespuestaHttpFalsa:
    def __init__(self, cuerpo: dict, cabeceras: dict[str, str], status: int = 200) -> None:
        self.cuerpo, self.headers, self.status_code = cuerpo, cabeceras, status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self.cuerpo


def _responder_groq(monkeypatch: pytest.MonkeyPatch, cabeceras: dict[str, str], status: int = 200) -> list[str]:
    llamadas: list[str] = []
    cuerpo = {"choices": [{"finish_reason": "stop", "message": {"content": "Monto máximo: $50.000.000"}}]}

    def post_falso(url: str, **kwargs) -> RespuestaHttpFalsa:
        llamadas.append(url)
        return RespuestaHttpFalsa(cuerpo if status == 200 else {"error": {}}, cabeceras, status)

    monkeypatch.setattr(llm.httpx, "post", post_falso)
    return llamadas


# --------------------------------------------------------------------------- lectura de cabeceras (RF-L1)


def test_leer_cuota_con_cabeceras_completas():
    cuota = leer_cuota(CABECERAS, actualizado="2026-10-22T10:00:00+00:00")
    assert cuota == CuotaLLM(
        solicitudes_limite=1000,
        solicitudes_restantes=997,
        solicitudes_reinicio_s=179.56,
        tokens_limite=8000,
        tokens_restantes=7500,
        tokens_reinicio_s=7.66,
        actualizado="2026-10-22T10:00:00+00:00",
    )


@pytest.mark.parametrize(
    ("valor", "segundos"),
    [("2m59.56s", 179.56), ("7.66s", 7.66), ("1h0m0s", 3600.0), ("1h2m3s", 3723.0), ("450ms", 0.45), ("x", None)],
)
def test_leer_cuota_interpreta_duraciones(valor: str, segundos: float | None):
    cuota = leer_cuota({"x-ratelimit-reset-requests": valor}, actualizado="t")
    assert cuota.solicitudes_reinicio_s == segundos


def test_leer_cuota_tolera_cabeceras_ausentes_o_mal_formadas():
    cuota = leer_cuota({"x-ratelimit-remaining-requests": "muchas"}, actualizado="t")
    assert cuota.solicitudes_restantes is None and cuota.solicitudes_limite is None


def test_leer_cuota_sin_cabeceras_de_cuota_devuelve_none():
    assert leer_cuota({"content-type": "application/json"}, actualizado="t") is None


# --------------------------------------------------------------------------- registro en el proveedor (RF-L1, RF-L2)


def test_groq_registra_cuota_y_cuenta_llamadas(monkeypatch: pytest.MonkeyPatch):
    _responder_groq(monkeypatch, CABECERAS)
    proveedor = ProveedorGroq(api_key="prueba", modelo="m", timeout=1.0)
    assert proveedor.cuota is None and proveedor.total_llamadas == 0
    proveedor.completar("s", "u")
    proveedor.completar("s", "u")
    assert proveedor.total_llamadas == 2
    assert proveedor.cuota.solicitudes_restantes == 997 and proveedor.cuota.solicitudes_limite == 1000


def test_groq_registra_cuota_agotada_en_429_y_degrada_al_extractivo(
    orquestador: Orquestador, monkeypatch: pytest.MonkeyPatch
):
    _responder_groq(monkeypatch, {**CABECERAS, "x-ratelimit-remaining-requests": "0", "retry-after": "2"}, 429)
    proveedor = ProveedorGroq(api_key="prueba", modelo="m", timeout=1.0)
    orquestador.proveedor_llm = proveedor
    resultado = orquestador.consultar(PREGUNTA)
    assert resultado.modo == "extractivo" and "$50.000.000" in resultado.respuesta
    assert proveedor.cuota.solicitudes_restantes == 0 and proveedor.total_llamadas == 1


# --------------------------------------------------------------------------- orquestador (RF-L3, RF-L4, RF-L5)


def _orquestador_con_groq(corpus: Corpus) -> tuple[Orquestador, ProveedorGroq]:
    proveedor = ProveedorGroq(api_key="prueba", modelo="openai/gpt-oss-20b", timeout=1.0)
    cfg = Configuracion(llm_provider="groq", groq_api_key="prueba")
    return Orquestador(cfg, corpus, RepositorioConsultas(":memory:"), proveedor), proveedor


def test_estado_llm_sin_proveedor(orquestador: Orquestador):
    assert orquestador.estado_llm() == {
        "proveedor": None, "modelo": None, "activo": False, "modo": "extractivo", "llamadas": 0, "cuota": None,
    }


def test_desactivar_evita_llamadas_al_llm_y_reactivar_las_restaura(corpus: Corpus, monkeypatch: pytest.MonkeyPatch):
    llamadas = _responder_groq(monkeypatch, CABECERAS)
    orquestador, _ = _orquestador_con_groq(corpus)

    estado = orquestador.cambiar_modo_llm(False)
    assert estado["activo"] is False and estado["modo"] == "extractivo" and estado["proveedor"] == "groq"
    assert orquestador.consultar(PREGUNTA).modo == "extractivo"
    assert llamadas == []

    estado = orquestador.cambiar_modo_llm(True)
    assert estado["activo"] is True and estado["modo"] == "groq"
    assert orquestador.consultar(PREGUNTA).modo == "groq"
    assert len(llamadas) == 1
    assert orquestador.estado_llm()["cuota"]["solicitudes_restantes"] == 997


# --------------------------------------------------------------------------- API (RF-L3..RF-L5, RNF-L2)


@pytest.fixture
def cliente_groq(cfg: Configuracion, corpus: Corpus, monkeypatch: pytest.MonkeyPatch):
    proveedor = ProveedorGroq("prueba-secreta", "openai/gpt-oss-20b", 1.0)
    monkeypatch.setattr(llm, "construir_proveedor", lambda c: proveedor)
    monkeypatch.setattr("asistente.api.app.construir_proveedor", llm.construir_proveedor)
    app = crear_app(cfg=cfg, corpus=corpus, repositorio=RepositorioConsultas(":memory:"))
    with TestClient(app) as cliente_http:
        yield cliente_http


def test_get_llm_sin_proveedor(cliente: TestClient):
    datos = cliente.get("/api/llm").json()
    assert datos["proveedor"] is None and datos["activo"] is False and datos["cuota"] is None


def test_get_llm_con_groq_y_cuota_tras_una_consulta(cliente_groq: TestClient, monkeypatch: pytest.MonkeyPatch):
    assert cliente_groq.get("/api/llm").json()["cuota"] is None  # se conoce tras la primera llamada
    _responder_groq(monkeypatch, CABECERAS)
    cliente_groq.post("/api/consultar", json={"pregunta": PREGUNTA})
    datos = cliente_groq.get("/api/llm").json()
    assert datos["proveedor"] == "groq" and datos["modelo"] == "openai/gpt-oss-20b" and datos["activo"] is True
    assert datos["llamadas"] == 1 and datos["cuota"]["solicitudes_restantes"] == 997


def test_get_llm_no_expone_la_clave(cliente_groq: TestClient):
    assert "prueba-secreta" not in cliente_groq.get("/api/llm").text


def test_put_llm_desactiva_y_reactiva(cliente_groq: TestClient):
    assert cliente_groq.put("/api/llm", json={"activo": False}).json()["activo"] is False
    assert cliente_groq.get("/api/salud").json()["modo"] == "extractivo"
    assert cliente_groq.put("/api/llm", json={"activo": True}).json()["activo"] is True


@pytest.mark.parametrize("cuerpo", [{"activo": "no"}, {"activo": 1}, {}, {"otro": True}])
def test_put_llm_tipo_invalido_400(cliente_groq: TestClient, cuerpo: dict):
    respuesta = cliente_groq.put("/api/llm", json=cuerpo)
    assert respuesta.status_code == 400 and respuesta.json()["codigo"] == "SOLICITUD_INVALIDA"
    assert cliente_groq.get("/api/llm").json()["activo"] is True  # el modo no cambió


def test_put_llm_activar_sin_proveedor_400(cliente: TestClient):
    respuesta = cliente.put("/api/llm", json={"activo": True})
    assert respuesta.status_code == 400 and respuesta.json()["codigo"] == "LLM_NO_CONFIGURADO"


def test_put_llm_desactivar_sin_proveedor_es_valido(cliente: TestClient):
    assert cliente.put("/api/llm", json={"activo": False}).json()["activo"] is False


def test_proveedor_falso_sin_cuota_reporta_none(orquestador: Orquestador):
    orquestador._proveedor_configurado = orquestador.proveedor_llm = ProveedorFalso("x")
    estado = orquestador.estado_llm()
    assert estado["proveedor"] == "falso" and estado["cuota"] is None and estado["llamadas"] == 0


# --------------------------------------------------------------------------- revisión adversarial


@pytest.mark.parametrize(
    ("valor", "segundos"), [("850µs", 0.00085), ("850us", 0.00085), ("300ns", 3e-07), ("1.5ms", 0.0015)]
)
def test_leer_cuota_interpreta_microsegundos_y_nanosegundos(valor: str, segundos: float):
    assert leer_cuota({"x-ratelimit-reset-tokens": valor}, actualizado="t").tokens_reinicio_s == pytest.approx(segundos)


@pytest.mark.parametrize("cuerpo", ["null", "{malo", "[true]", "true"])
def test_put_llm_cuerpo_no_json_menciona_activo(cliente: TestClient, cuerpo: str):
    respuesta = cliente.put("/api/llm", content=cuerpo, headers={"content-type": "application/json"})
    assert respuesta.status_code == 400 and respuesta.json()["codigo"] == "SOLICITUD_INVALIDA"
    assert "activo" in respuesta.json()["error"] and "pregunta" not in respuesta.json()["error"]


def test_log_de_fallo_no_incluye_la_url_ni_credenciales(
    orquestador: Orquestador, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    def post_falla(url: str, **kwargs):
        # El mensaje de httpx incluye la URL; una URL de proxy puede llevar usuario y clave.
        raise RuntimeError(f"Server error '500' for url 'http://usuario:clave@proxy{url[8:]}'")

    monkeypatch.setattr(llm.httpx, "post", post_falla)
    orquestador.proveedor_llm = ProveedorGroq(api_key="prueba", modelo="m", timeout=1.0)
    with caplog.at_level("WARNING", logger="asistente.llm"):
        orquestador.consultar(PREGUNTA)
    registro = next(r for r in caplog.records if "fallo del proveedor LLM" in r.getMessage())
    assert "clave" not in str(registro.__dict__) and "usuario" not in str(registro.__dict__)
    assert registro.error == "RuntimeError"


def test_put_llm_responde_mientras_una_consulta_espera_al_llm(cfg: Configuracion, corpus: Corpus):
    """Una llamada lenta al LLM no debe bloquear el servidor: el asesor puede pasar a modo sin conexión."""
    import threading

    liberar, en_llm = threading.Event(), threading.Event()

    class ProveedorLento:
        nombre, modelo, total_llamadas, cuota = "lento", "m", 0, None

        def completar(self, sistema: str, usuario: str) -> str:
            en_llm.set()
            liberar.wait(timeout=5)
            return "Monto máximo: $50.000.000"

    app = crear_app(cfg=cfg, corpus=corpus, repositorio=RepositorioConsultas(":memory:"))
    with TestClient(app) as cliente_http:
        app.state.orquestador._proveedor_configurado = app.state.orquestador.proveedor_llm = ProveedorLento()
        hilo = threading.Thread(target=lambda: cliente_http.post("/api/consultar", json={"pregunta": PREGUNTA}))
        hilo.start()
        assert en_llm.wait(timeout=5)
        resultado: dict = {}
        desactivar = lambda: resultado.update(cliente_http.put("/api/llm", json={"activo": False}).json())  # noqa: E731
        put = threading.Thread(target=desactivar)
        put.start()
        put.join(timeout=2)
        bloqueado = put.is_alive()
        liberar.set()
        hilo.join(timeout=5)
        put.join(timeout=5)
    assert not bloqueado, "PUT /api/llm quedó bloqueado por la consulta en curso"
    assert resultado["activo"] is False
