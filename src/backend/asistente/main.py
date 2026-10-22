"""Punto de entrada ASGI: ``uvicorn asistente.main:app --app-dir src/backend``."""
from .api import crear_app

app = crear_app()
