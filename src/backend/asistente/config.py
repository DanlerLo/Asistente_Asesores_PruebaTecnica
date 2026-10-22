"""Configuración del asistente, leída desde variables de entorno.

Toda la configuración es explícita y tiene valores por defecto seguros para
ejecución 100 % local: sin LLM, base documental en ``Data/`` y SQLite en
``storage/consultas.db``.
"""
from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

# src/backend/asistente/config.py -> parents[3] es la raíz del repositorio.
RAIZ_PROYECTO = Path(__file__).resolve().parents[3]

PROVEEDORES_LLM = ("none", "groq")

def _numero[N: (int, float)](variable: str, por_defecto: str, tipo: Callable[[str], N]) -> N:
    """Lee un número del entorno; si no lo es, el error nombra la variable."""
    valor = os.getenv(variable, por_defecto).strip()
    try:
        return tipo(valor)
    except ValueError:
        raise ValueError(f"{variable} debe ser un número; se recibió '{valor}'.") from None


@dataclass(frozen=True)
class Configuracion:
    """Parámetros de ejecución. Inmutable para evitar cambios accidentales."""

    data_dir: Path = RAIZ_PROYECTO / "Data"
    db_path: Path = RAIZ_PROYECTO / "storage" / "consultas.db"
    max_longitud_pregunta: int = 1000
    top_k: int = 8
    umbral_cobertura: float = 0.3
    archivos_restringidos: tuple[str, ...] = ("Información restringida.md",)
    cors_origenes: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    )
    llm_provider: str = "none"
    llm_model: str = ""
    groq_api_key: str = ""
    llm_timeout_segundos: float = 30.0

    def __post_init__(self) -> None:
        """RF-19: un valor fuera de rango falla al arrancar con un mensaje claro, no en la primera consulta."""
        if self.max_longitud_pregunta < 1:
            raise ValueError("MAX_LONGITUD_PREGUNTA debe ser un entero mayor que 0.")
        if self.top_k < 1:
            raise ValueError("TOP_K debe ser un entero mayor que 0.")
        if not 0 < self.umbral_cobertura <= 1:
            raise ValueError("UMBRAL_COBERTURA debe estar entre 0 (excluido) y 1.")
        if self.llm_timeout_segundos <= 0:
            raise ValueError("LLM_TIMEOUT_SEGUNDOS debe ser mayor que 0.")
        if self.llm_provider not in PROVEEDORES_LLM:
            raise ValueError(f"LLM_PROVIDER inválido: '{self.llm_provider}'. Valores permitidos: {PROVEEDORES_LLM}")

    @classmethod
    def desde_entorno(cls) -> Configuracion:
        """Construye la configuración a partir de variables de entorno."""
        restringidos = tuple(
            nombre.strip()
            for nombre in os.getenv("ARCHIVOS_RESTRINGIDOS", "Información restringida.md").split(";")
            if nombre.strip()
        )
        origenes = tuple(
            origen.strip()
            for origen in os.getenv(
                "CORS_ORIGENES", "http://localhost:5173;http://127.0.0.1:5173"
            ).split(";")
            if origen.strip()
        )
        proveedor = os.getenv("LLM_PROVIDER", "none").strip().lower()
        return cls(
            data_dir=Path(os.getenv("DATA_DIR", str(RAIZ_PROYECTO / "Data"))),
            db_path=Path(os.getenv("DB_PATH", str(RAIZ_PROYECTO / "storage" / "consultas.db"))),
            max_longitud_pregunta=_numero("MAX_LONGITUD_PREGUNTA", "1000", int),
            top_k=_numero("TOP_K", "8", int),
            umbral_cobertura=_numero("UMBRAL_COBERTURA", "0.3", float),
            archivos_restringidos=restringidos,
            cors_origenes=origenes,
            llm_provider=proveedor,
            llm_model=os.getenv("LLM_MODEL", "").strip(),
            groq_api_key=os.getenv("GROQ_API_KEY", "").strip(),
            llm_timeout_segundos=_numero("LLM_TIMEOUT_SEGUNDOS", "30", float),
        )
