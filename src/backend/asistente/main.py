"""API HTTP del asistente (FastAPI).

Endpoints:
* ``POST /api/consultar``   -> {"respuesta", "fuentes", "estado", ...}
* ``GET  /api/historial``   -> últimas consultas registradas
* ``GET  /api/estadisticas``-> conteo por estado y latencias
* ``GET  /api/salud``       -> estado del corpus y modo de operación

``crear_app`` es una fábrica para poder construir la aplicación con
configuración y repositorio propios en las pruebas.
"""
from __future__ import annotations

import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .config import Configuracion
from .corpus import Corpus, cargar_corpus
from .guardrails import ErrorValidacion
from .llm import construir_proveedor
from .observabilidad import configurar_logging
from .persistencia import RepositorioConsultas
from .servicio import ServicioConsultas

log = logging.getLogger("asistente.api")


class ConsultaRequest(BaseModel):
    pregunta: Any = Field(default=None, description="Pregunta del asesor en lenguaje natural")


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
        app.state.servicio = ServicioConsultas(cfg, corpus_real, repo, construir_proveedor(cfg))
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
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def id_de_solicitud(request: Request, call_next):
        request.state.id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        respuesta = await call_next(request)
        respuesta.headers["x-request-id"] = request.state.id
        return respuesta

    @app.exception_handler(ErrorValidacion)
    async def manejar_validacion(_: Request, exc: ErrorValidacion):
        return _error(400, exc.codigo, exc.mensaje)

    @app.exception_handler(RequestValidationError)
    async def manejar_solicitud_invalida(_: Request, exc: RequestValidationError):
        return _error(400, "SOLICITUD_INVALIDA", "El cuerpo de la solicitud debe ser JSON con el campo 'pregunta'.")

    @app.exception_handler(Exception)
    async def manejar_error_interno(request: Request, exc: Exception):
        log.exception("error interno", extra={"request_id": getattr(request.state, "id", "")})
        return _error(500, "ERROR_INTERNO", "Ocurrió un error interno. Intenta de nuevo o escala el caso.")

    @app.post("/api/consultar", response_model=ConsultaResponse, responses={400: {"description": "Entrada inválida"}})
    async def consultar(solicitud: ConsultaRequest, request: Request):
        resultado = request.app.state.servicio.consultar(solicitud.pregunta)
        return resultado.a_dict()

    @app.get("/api/historial")
    async def historial(request: Request, limite: int = Query(default=20, ge=1, le=200)):
        return {"consultas": request.app.state.servicio.repositorio.listar(limite)}

    @app.get("/api/estadisticas")
    async def estadisticas(request: Request):
        return request.app.state.servicio.repositorio.estadisticas()

    @app.get("/api/salud")
    async def salud(request: Request):
        return {"estado": "ok", **request.app.state.servicio.estado_sistema()}

    return app


app = crear_app()
