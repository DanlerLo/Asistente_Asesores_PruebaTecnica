from __future__ import annotations

import logging
import re
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from ..config import Configuracion
from ..generacion.llm import construir_proveedor
from ..herramientas.corpus import Corpus
from ..infraestructura.observabilidad import configurar_logging, id_solicitud, instalar_id_de_solicitud
from ..infraestructura.persistencia import RepositorioConsultas
from ..orquestador import Orquestador
from ..seguridad.guardrails import ErrorValidacion
from ..seguridad.ingesta import cargar_corpus_seguro
from .esquemas import (
    MENSAJE_CUERPO_INVALIDO,
    MENSAJE_ERROR_INTERNO,
    MENSAJE_LIMITE_INVALIDO,
    MENSAJE_MODO_INVALIDO,
    error_json,
)
from .rutas import rutas

log = logging.getLogger("asistente.api")

# RF-17: un x-request-id ajeno solo se respeta si es corto y sin caracteres raros (no ensucia ni falsea logs).
_RE_ID_SOLICITUD = re.compile(r"[A-Za-z0-9._-]{1,64}")
# Mensaje de un 400 de validación de FastAPI según la ruta (el genérico menciona «pregunta»).
_MENSAJES_SOLICITUD_INVALIDA = {"/api/llm": MENSAJE_MODO_INVALIDO, "/api/historial": MENSAJE_LIMITE_INVALIDO}


def crear_app(
    cfg: Configuracion | None = None,
    corpus: Corpus | None = None,
    repositorio: RepositorioConsultas | None = None,
) -> FastAPI:
    cfg = cfg or Configuracion.desde_entorno()
    configurar_logging(cfg.log_level)
    instalar_id_de_solicitud()

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI):
        corpus_real = corpus if corpus is not None else cargar_corpus_seguro(cfg.data_dir, cfg.archivos_restringidos)
        repo = repositorio if repositorio is not None else RepositorioConsultas(cfg.db_path)
        app.state.orquestador = Orquestador(cfg, corpus_real, repo, construir_proveedor(cfg))
        log.info("aplicación iniciada", extra={"data_dir": str(cfg.data_dir), "modo": cfg.llm_provider})
        yield
        app.state.orquestador.cerrar()
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
    _registrar_middleware(app)
    _registrar_errores(app)
    app.include_router(rutas)
    return app


def _registrar_middleware(app: FastAPI) -> None:
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


def _registrar_errores(app: FastAPI) -> None:
    @app.exception_handler(ErrorValidacion)
    async def manejar_validacion(_: Request, exc: ErrorValidacion):
        return error_json(400, exc.codigo, exc.mensaje)

    @app.exception_handler(RequestValidationError)
    async def manejar_solicitud_invalida(request: Request, exc: RequestValidationError):
        mensaje = _MENSAJES_SOLICITUD_INVALIDA.get(request.url.path, MENSAJE_CUERPO_INVALIDO)
        return error_json(400, "SOLICITUD_INVALIDA", mensaje)

    @app.exception_handler(Exception)
    async def manejar_error_interno(request: Request, exc: Exception):
        ident = getattr(request.state, "id", "")
        log.exception("error interno", extra={"request_id": ident})
        respuesta = error_json(500, "ERROR_INTERNO", MENSAJE_ERROR_INTERNO)
        if ident:  # el 500 no pasa por el middleware
            respuesta.headers["x-request-id"] = ident
        return respuesta
