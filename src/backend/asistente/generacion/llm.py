from __future__ import annotations

import logging
import re
import threading
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from functools import cache
from typing import Protocol

import httpx

from ..config import Configuracion
from ..dominio import ESTADO_EXITOSA, FRASE_SIN_INFO, Fuente, RespuestaGenerada, respuesta_sin_informacion
from ..herramientas.recuperacion import Resultado
from .plantillas import renderizar

log = logging.getLogger("asistente.llm")

@cache
def instrucciones_sistema() -> str:
    """Se renderiza una sola vez para que el prompt sea estable y aproveche la caché del proveedor."""
    return renderizar("sistema.j2", frase_sin_info=FRASE_SIN_INFO)


class ClienteHttpLLM(httpx.Client):
    """Tipo propio para poder simularlo en pruebas sin afectar a otros clientes httpx."""


class ProveedorLLM(Protocol):
    nombre: str
    modelo: str
    total_llamadas: int
    cuota: CuotaLLM | None

    def completar(self, sistema: str, usuario: str) -> str: ...

    def cerrar(self) -> None: ...


@dataclass(frozen=True)
class CuotaLLM:
    """Cuota informada en la última respuesta del proveedor (``None`` = desconocido)."""

    solicitudes_limite: int | None = None  # por día
    solicitudes_restantes: int | None = None
    solicitudes_reinicio_s: float | None = None
    tokens_limite: int | None = None  # por minuto
    tokens_restantes: int | None = None
    tokens_reinicio_s: float | None = None
    actualizado: str = ""

    def a_dict(self) -> dict:
        return asdict(self)


# Duraciones al estilo Go («2m59.56s», «850µs»): las unidades largas van antes que «m» y «s».
_RE_DURACION = re.compile(r"(\d+(?:\.\d+)?)(h|ms|µs|μs|us|ns|m|s)")
_SEGUNDOS_POR_UNIDAD = {"h": 3600.0, "m": 60.0, "s": 1.0, "ms": 1e-3, "µs": 1e-6, "μs": 1e-6, "us": 1e-6, "ns": 1e-9}


def _entero(valor: str | None) -> int | None:
    try:
        return int(valor) if valor is not None else None
    except ValueError:
        return None


def _duracion(valor: str | None) -> float | None:
    """``2m59.56s`` -> 179.56; ``450ms`` -> 0.45; formato desconocido -> ``None``."""
    texto = (valor or "").strip()
    partes = _RE_DURACION.findall(texto)
    if not partes or "".join(numero + unidad for numero, unidad in partes) != texto:
        return None
    return round(sum(float(numero) * _SEGUNDOS_POR_UNIDAD[unidad] for numero, unidad in partes), 9)


def leer_cuota(cabeceras: Mapping[str, str], actualizado: str) -> CuotaLLM | None:
    """Groq envía las cabeceras ``x-ratelimit-*`` en cada respuesta, también en los 429."""
    if not any(cabeceras.get(f"x-ratelimit-{c}") is not None for c in (
        "limit-requests", "remaining-requests", "reset-requests", "limit-tokens", "remaining-tokens", "reset-tokens",
    )):
        return None
    return CuotaLLM(
        solicitudes_limite=_entero(cabeceras.get("x-ratelimit-limit-requests")),
        solicitudes_restantes=_entero(cabeceras.get("x-ratelimit-remaining-requests")),
        solicitudes_reinicio_s=_duracion(cabeceras.get("x-ratelimit-reset-requests")),
        tokens_limite=_entero(cabeceras.get("x-ratelimit-limit-tokens")),
        tokens_restantes=_entero(cabeceras.get("x-ratelimit-remaining-tokens")),
        tokens_reinicio_s=_duracion(cabeceras.get("x-ratelimit-reset-tokens")),
        actualizado=actualizado,
    )


URL_GROQ = "https://api.groq.com/openai/v1/chat/completions"
MODELO_GROQ_POR_DEFECTO = "openai/gpt-oss-20b"


class ProveedorGroq:
    nombre = "groq"

    def __init__(self, api_key: str, modelo: str, timeout: float) -> None:
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY es obligatoria con LLM_PROVIDER=groq (créala en https://console.groq.com/keys)"
            )
        self.api_key = api_key
        self.modelo = modelo
        self.timeout = timeout
        self.total_llamadas = 0
        self.cuota: CuotaLLM | None = None  # Groq no tiene endpoint de uso: se lee de cada respuesta
        self._candado = threading.Lock()
        # Un cliente por proveedor para reutilizar conexiones TLS.
        self._cliente = ClienteHttpLLM()

    def cerrar(self) -> None:
        self._cliente.close()

    def _contar_llamada(self) -> None:
        with self._candado:
            self.total_llamadas += 1

    def _registrar_cuota(self, cuota: CuotaLLM | None) -> None:
        """Con llamadas concurrentes, una respuesta más vieja no pisa una cuota más reciente."""
        with self._candado:
            if cuota and (self.cuota is None or cuota.actualizado >= self.cuota.actualizado):
                self.cuota = cuota

    def completar(self, sistema: str, usuario: str) -> str:
        self._contar_llamada()
        respuesta = self._cliente.post(
            URL_GROQ,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json=self._cuerpo(sistema, usuario),
            timeout=self.timeout,
        )
        # Antes de raise_for_status: un 429 también informa la cuota.
        ahora = datetime.now(UTC).isoformat(timespec="milliseconds")
        self._registrar_cuota(leer_cuota(respuesta.headers, actualizado=ahora))
        respuesta.raise_for_status()
        opcion = (respuesta.json().get("choices") or [{}])[0]
        # Respuesta cortada o filtrada: mejor que responda el motor extractivo.
        if opcion.get("finish_reason") not in (None, "stop"):
            log.warning("respuesta incompleta del LLM", extra={"finish_reason": opcion.get("finish_reason")})
            return ""
        return (opcion.get("message", {}).get("content") or "").strip()

    def _cuerpo(self, sistema: str, usuario: str) -> dict:
        cuerpo = {
            "model": self.modelo,
            "messages": [
                {"role": "system", "content": sistema},
                {"role": "user", "content": usuario},
            ],
            "temperature": 0,
            "max_completion_tokens": 1024,
            "stream": False,
        }
        if self.modelo.startswith("openai/gpt-oss"):  # otros modelos rechazan estos parámetros
            cuerpo |= {"reasoning_effort": "low", "include_reasoning": False}
        return cuerpo


def construir_proveedor(cfg: Configuracion) -> ProveedorLLM | None:
    if cfg.llm_provider == "groq":
        modelo = cfg.llm_model or MODELO_GROQ_POR_DEFECTO
        return ProveedorGroq(cfg.groq_api_key, modelo, cfg.llm_timeout_segundos)
    return None


def responder_con_llm(
    pregunta: str, resultados: list[Resultado], proveedor: ProveedorLLM
) -> RespuestaGenerada | None:
    """``None`` si el proveedor falla, para que el servicio use el motor extractivo."""
    if not resultados:
        return respuesta_sin_informacion(modo=proveedor.nombre)
    usuario = renderizar("usuario.j2", fragmentos=[r.fragmento for r in resultados], pregunta=pregunta)
    try:
        texto = proveedor.completar(instrucciones_sistema(), usuario)
    except Exception as exc:  # noqa: BLE001 - cualquier fallo del proveedor degrada al modo extractivo
        # Solo tipo y código HTTP: el mensaje de httpx incluye la URL, que puede llevar credenciales.
        estado_http = getattr(getattr(exc, "response", None), "status_code", None)
        log.warning(
            "fallo del proveedor LLM, se usa el motor extractivo",
            extra={"error": type(exc).__name__, "status": estado_http},
        )
        return None
    if not texto:
        return None
    if FRASE_SIN_INFO.lower() in texto.lower():
        return respuesta_sin_informacion(modo=proveedor.nombre)
    puntaje_maximo = resultados[0].puntaje or 1.0
    # Fuentes = secciones citadas en el texto; si no cita ninguna reconocible, el fragmento principal.
    citados = [r for r in resultados if _cita(r, texto)] or resultados[:1]
    fuentes = [
        Fuente(
            documento=r.fragmento.documento,
            archivo=r.fragmento.archivo,
            seccion=r.fragmento.ruta_seccion or "documento completo",
            puntaje=min(1.0, r.puntaje / puntaje_maximo),
            extracto=r.fragmento.contenido[:500],
        )
        for r in citados
    ]
    return RespuestaGenerada(texto=texto, estado=ESTADO_EXITOSA, fuentes=fuentes, modo=proveedor.nombre)


def _normalizar_cita(texto: str) -> str:
    return " ".join(texto.replace("›", ">").lower().split())


def _cita(resultado: Resultado, texto: str) -> bool:
    """Cita exacta de la sección, no solo de su archivo ni de una sección padre."""
    seccion = resultado.fragmento.ruta_seccion or "documento completo"
    cita = _normalizar_cita(f"{resultado.fragmento.archivo} > {seccion}")
    return re.search(re.escape(cita) + r"(?!\s*>)", _normalizar_cita(texto)) is not None
