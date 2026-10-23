"""Endpoints de la API. Cada uno delega en el orquestador que el ciclo de vida deja en ``app.state``.

Los que tocan SQLite (consultar, historial, estadísticas, consulta por id) son ``def``: FastAPI los
ejecuta en el threadpool, así el candado de la base ni una llamada lenta al LLM bloquean el bucle.
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Query, Request

from .esquemas import MENSAJE_MODO_INVALIDO, ConsultaRequest, ConsultaResponse, ModoLlmRequest, error_json

# RF-18: solo dígitos ASCII; «²» o «٣» pasan ``str.isdigit`` y rompían ``int``.
_RE_ID_CONSULTA = re.compile(r"[1-9][0-9]{0,17}")

rutas = APIRouter(prefix="/api")


@rutas.post("/consultar", response_model=ConsultaResponse, responses={400: {"description": "Entrada inválida"}})
def consultar(solicitud: ConsultaRequest, request: Request):
    resultado = request.app.state.orquestador.consultar(solicitud.pregunta, solicitud.contexto)
    return resultado.a_dict()


@rutas.get("/historial")
def historial(request: Request, limite: int = Query(default=20, ge=1, le=200)):
    return {"consultas": request.app.state.orquestador.repositorio.listar(limite)}


@rutas.get(
    "/consultas/{id_consulta}",
    responses={400: {"description": "Id inválido"}, 404: {"description": "No existe"}},
)
def obtener_consulta(id_consulta: str, request: Request):
    if not _RE_ID_CONSULTA.fullmatch(id_consulta):
        return error_json(400, "ID_INVALIDO", "El id de la consulta debe ser un entero positivo.")
    registro = request.app.state.orquestador.repositorio.obtener(int(id_consulta))
    if registro is None:
        return error_json(404, "CONSULTA_NO_ENCONTRADA", f"No existe una consulta con id {id_consulta}.")
    return registro


@rutas.get("/estadisticas")
def estadisticas(request: Request):
    return request.app.state.orquestador.repositorio.estadisticas()


@rutas.get("/llm")
async def estado_llm(request: Request):
    return request.app.state.orquestador.estado_llm()


@rutas.put("/llm", responses={400: {"description": "Entrada inválida o LLM no configurado"}})
async def cambiar_modo_llm(solicitud: ModoLlmRequest, request: Request):
    if not isinstance(solicitud.activo, bool):
        return error_json(400, "SOLICITUD_INVALIDA", MENSAJE_MODO_INVALIDO)
    return request.app.state.orquestador.cambiar_modo_llm(solicitud.activo)


@rutas.get("/salud")
async def salud(request: Request):
    return {"estado": "ok", **request.app.state.orquestador.estado_sistema()}
