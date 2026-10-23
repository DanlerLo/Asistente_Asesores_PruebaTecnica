from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]

PROVEEDORES_LLM = ("none", "groq")
PROVEEDORES_EMBEDDINGS = ("none", "local")
MODELO_EMBEDDINGS_POR_DEFECTO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
NIVELES_LOG = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

log = logging.getLogger("asistente.config")

def _numero[N: (int, float)](variable: str, por_defecto: str, tipo: Callable[[str], N]) -> N:
    """Lee un número del entorno; si no lo es, el error nombra la variable."""
    valor = os.getenv(variable, por_defecto).strip()
    try:
        return tipo(valor)
    except ValueError:
        raise ValueError(f"{variable} debe ser un número; se recibió '{valor}'.") from None


def _proveedor_llm(proveedor: str, clave: str) -> str:
    """Un LLM mal configurado no impide arrancar: el servicio queda en modo sin conexión y lo advierte."""
    if proveedor not in PROVEEDORES_LLM:
        log.warning(f"LLM_PROVIDER inválido ('{proveedor}'); se arranca en modo sin conexión ({PROVEEDORES_LLM}).")
        return "none"
    if proveedor == "groq" and not clave:
        log.warning("LLM_PROVIDER=groq sin GROQ_API_KEY; se arranca en modo sin conexión hasta configurar la clave.")
        return "none"
    return proveedor


@dataclass(frozen=True)
class Configuracion:
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
    log_level: str = "INFO"
    embeddings: str = "none"
    embeddings_modelo: str = MODELO_EMBEDDINGS_POR_DEFECTO
    embeddings_cache: Path = RAIZ_PROYECTO / "storage" / "modelos"
    umbral_semantico: float = 0.6
    llm_max_fragmentos: int = 12

    def __post_init__(self) -> None:
        """RF-19: un valor fuera de rango falla al arrancar, no en la primera consulta."""
        if self.max_longitud_pregunta < 1:
            raise ValueError("MAX_LONGITUD_PREGUNTA debe ser un entero mayor que 0.")
        if self.top_k < 1:
            raise ValueError("TOP_K debe ser un entero mayor que 0.")
        if not 0 < self.umbral_cobertura <= 1:
            raise ValueError("UMBRAL_COBERTURA debe estar entre 0 (excluido) y 1.")
        if self.llm_timeout_segundos <= 0:
            raise ValueError("LLM_TIMEOUT_SEGUNDOS debe ser mayor que 0.")
        if self.log_level not in NIVELES_LOG:
            raise ValueError(f"LOG_LEVEL inválido: '{self.log_level}'. Valores permitidos: {NIVELES_LOG}")
        if self.embeddings not in PROVEEDORES_EMBEDDINGS:
            raise ValueError(f"EMBEDDINGS inválido: '{self.embeddings}'. Valores permitidos: {PROVEEDORES_EMBEDDINGS}")
        if not 0 < self.umbral_semantico <= 1:
            raise ValueError("UMBRAL_SEMANTICO debe estar entre 0 (excluido) y 1.")
        if self.llm_max_fragmentos < 1:
            raise ValueError("LLM_MAX_FRAGMENTOS debe ser un entero mayor que 0.")
        if self.llm_provider not in PROVEEDORES_LLM:
            raise ValueError(f"LLM_PROVIDER inválido: '{self.llm_provider}'. Valores permitidos: {PROVEEDORES_LLM}")

    @classmethod
    def desde_entorno(cls) -> Configuracion:
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
        clave = os.getenv("GROQ_API_KEY", "").strip()
        proveedor = _proveedor_llm(os.getenv("LLM_PROVIDER", "none").strip().lower(), clave)
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
            groq_api_key=clave,
            llm_timeout_segundos=_numero("LLM_TIMEOUT_SEGUNDOS", "30", float),
            log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
            embeddings=os.getenv("EMBEDDINGS", "none").strip().lower(),
            embeddings_modelo=os.getenv("EMBEDDINGS_MODELO", MODELO_EMBEDDINGS_POR_DEFECTO).strip(),
            embeddings_cache=Path(os.getenv("EMBEDDINGS_CACHE", str(RAIZ_PROYECTO / "storage" / "modelos"))),
            umbral_semantico=_numero("UMBRAL_SEMANTICO", "0.6", float),
            llm_max_fragmentos=_numero("LLM_MAX_FRAGMENTOS", "12", int),
        )
