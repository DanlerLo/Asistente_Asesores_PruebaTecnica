"""API HTTP del asistente (FastAPI).

Endpoints:
* ``POST /api/consultar``   -> {"respuesta", "fuentes", "estado", ...}; ``contexto`` opcional (006)
* ``GET  /api/historial``   -> últimas consultas registradas
* ``GET  /api/estadisticas``-> conteo por estado y latencias
* ``GET  /api/salud``       -> estado del corpus y modo de operación
* ``GET  /api/consultas/{id}`` -> una consulta guardada (pregunta, fecha, respuesta, fuentes, estado)
* ``GET  /api/llm``         -> proveedor LLM, si está activo, llamadas y cuota de la API gratuita
* ``PUT  /api/llm``         -> {"activo": bool}: modo sin conexión o reactivar el LLM configurado

``crear_app`` es una fábrica para poder construir la aplicación con
configuración y repositorio propios en las pruebas; la instancia que sirve
uvicorn se crea en ``asistente.main``.
"""
from __future__ import annotations

import logging
import os
import re
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..config import Configuracion
from ..generacion.llm import construir_proveedor
from ..herramientas.corpus import Corpus, cargar_corpus
from ..infraestructura.observabilidad import configurar_logging, id_solicitud
from ..infraestructura.persistencia import RepositorioConsultas
from ..orquestador import Orquestador
from ..seguridad.guardrails import ErrorValidacion

log = logging.getLogger("asistente.api")


class ConsultaRequest(BaseModel):
    pregunta: Any = Field(default=None, description="Pregunta del asesor en lenguaje natural")
    contexto: Any = Field(default=None, description="Opcional: hasta 3 preguntas anteriores de la conversación")


class ModoLlmRequest(BaseModel):
    activo: Any = Field(default=None, description="false = modo sin conexión; true = reactivar el LLM configurado")


class FuenteResponse(BaseModel):
    documento: str
    archivo: str
    seccion: str
    puntaje: float
    extracto: str = ""


class ConsultaResponse(BaseModel):
    id: int
    respuesta: str
    fuentes: list[FuenteResponse]
    estado: str
    fecha_hora: str
    latencia_ms: int
    modo: str


MENSAJE_MODO_INVALIDO = "El cuerpo debe ser JSON con el campo booleano 'activo'."
MENSAJE_LIMITE_INVALIDO = "El parámetro 'limite' debe ser un entero entre 1 y 200."
# RF-17: un x-request-id ajeno solo se respeta si es corto y sin caracteres raros (no ensucia ni falsea logs).
_RE_ID_SOLICITUD = re.compile(r"[A-Za-z0-9._-]{1,64}")
# RF-18: solo dígitos ASCII; «²» o «٣» pasan ``str.isdigit`` y rompían ``int``.
_RE_ID_CONSULTA = re.compile(r"[1-9][0-9]{0,17}")


def _error(status: int, codigo: str, mensaje: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": mensaje, "codigo": codigo})


def crear_app(
    cfg: Configuracion | None = None,
    corpus: Corpus | None = None,
    repositorio: RepositorioConsultas | None = None,
) -> FastAPI:
    configurar_logging(os.getenv("LOG_LEVEL", "INFO"))
    cfg = cfg or Configuracion.desde_entorno()

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI):
        corpus_real = corpus if corpus is not None else cargar_corpus(cfg.data_dir, cfg.archivos_restringidos)
        repo = repositorio if repositorio is not None else RepositorioConsultas(cfg.db_path)
        app.state.orquestador = Orquestador(cfg, corpus_real, repo, construir_proveedor(cfg))
        log.info("aplicación iniciada", extra={"data_dir": str(cfg.data_dir), "modo": cfg.llm_provider})
        yield
        if repositorio is None:
            repo.cerrar()

    app = FastAPI(
        title="Asistente interno para asesores comerciales",
        version="1.0.0",
        lifespan=ciclo_de_vida,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(cfg.cors_origenes),
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def id_de_solicitud(request: Request, call_next):
        recibido = request.headers.get("x-request-id", "")
        request.state.id = recibido if _RE_ID_SOLICITUD.fullmatch(recibido) else uuid.uuid4().hex[:12]
        marca = id_solicitud.set(request.state.id)
        try:
            respuesta = await call_next(request)
        finally:
            id_solicitud.reset(marca)
        respuesta.headers["x-request-id"] = request.state.id
        return respuesta

    @app.exception_handler(ErrorValidacion)
    async def manejar_validacion(_: Request, exc: ErrorValidacion):
        return _error(400, exc.codigo, exc.mensaje)

    @app.exception_handler(RequestValidationError)
    async def manejar_solicitud_invalida(request: Request, exc: RequestValidationError):
        if request.url.path == "/api/llm":
            return _error(400, "SOLICITUD_INVALIDA", MENSAJE_MODO_INVALIDO)
        if request.url.path == "/api/historial":
            return _error(400, "SOLICITUD_INVALIDA", MENSAJE_LIMITE_INVALIDO)
        return _error(400, "SOLICITUD_INVALIDA", "El cuerpo de la solicitud debe ser JSON con el campo 'pregunta'.")

    @app.exception_handler(Exception)
    async def manejar_error_interno(request: Request, exc: Exception):
        ident = getattr(request.state, "id", "")
        log.exception("error interno", extra={"request_id": ident})
        respuesta = _error(500, "ERROR_INTERNO", "Ocurrió un error interno. Intenta de nuevo o escala el caso.")
        if ident:  # el 500 no pasa por el middleware: se agrega aquí para poder rastrearlo
            respuesta.headers["x-request-id"] = ident
        return respuesta

    @app.post("/api/consultar", response_model=ConsultaResponse, responses={400: {"description": "Entrada inválida"}})
    def consultar(solicitud: ConsultaRequest, request: Request):
        # Síncrona a propósito: FastAPI la ejecuta en un hilo aparte, así una llamada lenta al LLM
        # no bloquea el servidor (p. ej. PUT /api/llm para pasar a modo sin conexión).
        resultado = request.app.state.orquestador.consultar(solicitud.pregunta, solicitud.contexto)
        return resultado.a_dict()

    @app.get("/api/historial")
    async def historial(request: Request, limite: int = Query(default=20, ge=1, le=200)):
        return {"consultas": request.app.state.orquestador.repositorio.listar(limite)}

    @app.get(
        "/api/consultas/{id_consulta}",
        responses={400: {"description": "Id inválido"}, 404: {"description": "No existe"}},
    )
    def obtener_consulta(id_consulta: str, request: Request):
        if not _RE_ID_CONSULTA.fullmatch(id_consulta):
            return _error(400, "ID_INVALIDO", "El id de la consulta debe ser un entero positivo.")
        registro = request.app.state.orquestador.repositorio.obtener(int(id_consulta))
        if registro is None:
            return _error(404, "CONSULTA_NO_ENCONTRADA", f"No existe una consulta con id {id_consulta}.")
        return registro

    @app.get("/api/estadisticas")
    async def estadisticas(request: Request):
        return request.app.state.orquestador.repositorio.estadisticas()

    @app.get("/api/llm")
    async def estado_llm(request: Request):
        return request.app.state.orquestador.estado_llm()

    @app.put("/api/llm", responses={400: {"description": "Entrada inválida o LLM no configurado"}})
    async def cambiar_modo_llm(solicitud: ModoLlmRequest, request: Request):
        if not isinstance(solicitud.activo, bool):
            return _error(400, "SOLICITUD_INVALIDA", MENSAJE_MODO_INVALIDO)
        return request.app.state.orquestador.cambiar_modo_llm(solicitud.activo)

    @app.get("/api/salud")
    async def salud(request: Request):
        return {"estado": "ok", **request.app.state.orquestador.estado_sistema()}

    return app
