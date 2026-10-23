from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

MENSAJE_CUERPO_INVALIDO = "El cuerpo de la solicitud debe ser JSON con el campo 'pregunta'."
MENSAJE_MODO_INVALIDO = "El cuerpo debe ser JSON con el campo booleano 'activo'."
MENSAJE_LIMITE_INVALIDO = "El parámetro 'limite' debe ser un entero entre 1 y 200."
MENSAJE_ERROR_INTERNO = "Ocurrió un error interno. Intenta de nuevo o escala el caso."


class ConsultaRequest(BaseModel):
    # ``Any`` a propósito: un tipo inválido debe dar 400 con el código del contrato, no el 422 de FastAPI.
    model_config = ConfigDict(json_schema_extra={"required": ["pregunta"]})

    pregunta: Any = Field(
        default=None,
        description="Pregunta del asesor en lenguaje natural (máximo MAX_LONGITUD_PREGUNTA, 1000 por defecto)",
        json_schema_extra={"type": "string", "minLength": 1},
    )
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


def error_json(status: int, codigo: str, mensaje: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": mensaje, "codigo": codigo})
