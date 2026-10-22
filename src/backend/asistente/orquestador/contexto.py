"""Preguntas de seguimiento: hereda el producto o la sección de la conversación (especificación 006).

«¿Cuál es el monto máximo del Crédito Productivo Impulso?» → «¿Y el más bajo?» se responde como
«¿Y el más bajo? (Crédito Productivo Impulso)». Reglas deterministas, sin LLM:

* Solo hay seguimiento con marcadores explícitos: empieza por «y»/«e» («¿Y el plazo?») o usa un
  demostrativo que apunta a algo anterior («ese crédito», «esa póliza»). Se evalúa con tildes
  («está» es verbo, no demostrativo) y sin «su/sus», que suele referirse a alguien de la misma
  frase («¿cada cuánto debe un cliente actualizar su información?»). Una pregunta nueva nunca
  hereda contexto.
* Se hereda la **entidad** (nombre de producto o sección del corpus) que nombraba la pregunta
  más reciente del contexto, nunca texto libre del contexto: no puede inyectar nada.
* Si es seguimiento y no hay referente, no se adivina: ``sin_referente`` (el orquestador responde
  la frase canónica).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..herramientas.corpus import Fragmento
from ..herramientas.texto import normalizar, raices_unicas

_INICIOS_SEGUIMIENTO = frozenset({"y", "e"})
# Demostrativos que no se confunden con verbos: siempre apuntan a algo dicho antes.
_DEMOSTRATIVOS = frozenset({"ese", "esa", "esos", "esas", "aquel", "aquella", "aquellos", "aquellas"})
# «este/esta» solo cuentan seguidos de un sustantivo del negocio («este crédito», no «esta autorizado»).
_DEMOSTRATIVOS_CERCANOS = frozenset({"este", "esta", "estos", "estas"})
_SUSTANTIVOS = frozenset(
    {"credito", "creditos", "seguro", "seguros", "microseguro", "microseguros", "producto", "productos",
     "poliza", "polizas", "prestamo", "prestamos", "plan", "planes"}
)
_RE_PALABRA = re.compile(r"[a-záéíóúüñ]+")
_MAX_RAICES_ENTIDAD = 5


@dataclass(frozen=True)
class Entidad:
    nombre: str
    raices: frozenset[str]


@dataclass(frozen=True)
class Resolucion:
    pregunta: str  # pregunta efectiva (la original si no hubo seguimiento)
    referente: str = ""  # entidades heredadas, separadas por coma
    sin_referente: bool = False  # seguimiento sin entidad resoluble: no adivinar


def entidades_del_corpus(fragmentos: list[Fragmento]) -> list[Entidad]:
    """Productos y secciones (encabezados de nivel 2) que una pregunta puede nombrar.

    Los títulos de preguntas frecuentes («¿Se puede pagar…?») no son referentes.
    """
    vistas: dict[str, Entidad] = {}
    for fragmento in fragmentos:
        raices = fragmento.entidad_raices
        es_pregunta = fragmento.entidad.strip().endswith("?")
        if fragmento.entidad and not es_pregunta and raices and len(raices) <= _MAX_RAICES_ENTIDAD:
            vistas.setdefault(fragmento.entidad, Entidad(fragmento.entidad, raices))
    return sorted(vistas.values(), key=lambda e: e.nombre)


def _nombra(entidad: Entidad, raices: set[str]) -> bool:
    """Mismo criterio que el bloqueo por entidad: nombre completo o casi completo."""
    coincidencias = len(entidad.raices & raices)
    if coincidencias == len(entidad.raices):
        return True
    return coincidencias >= 2 and coincidencias >= len(entidad.raices) - 1


def entidades_nombradas(texto: str, entidades: list[Entidad]) -> list[str]:
    raices = raices_unicas(texto)
    nombradas = [e for e in entidades if _nombra(e, raices)]
    # Si una entidad nombrada está contenida en otra también nombrada, se conserva la más específica.
    return [e.nombre for e in nombradas if not any(e.raices < o.raices for o in nombradas)]


def es_seguimiento(pregunta: str) -> bool:
    palabras = _RE_PALABRA.findall(pregunta.lower())  # con tildes: «está» no es «esta»
    if not palabras:
        return False
    if palabras[0] in _INICIOS_SEGUIMIENTO or any(p in _DEMOSTRATIVOS for p in palabras):
        return True
    return any(
        actual in _DEMOSTRATIVOS_CERCANOS and normalizar(siguiente) in _SUSTANTIVOS
        for actual, siguiente in zip(palabras, palabras[1:])
    )


def resolver_pregunta(pregunta: str, contexto: list[str], entidades: list[Entidad]) -> Resolucion:
    if not es_seguimiento(pregunta) or entidades_nombradas(pregunta, entidades):
        return Resolucion(pregunta)
    for anterior in reversed(contexto):
        heredadas = entidades_nombradas(anterior, entidades)
        if heredadas:
            referente = ", ".join(heredadas)
            return Resolucion(f"{pregunta} ({referente})", referente=referente)
    return Resolucion(pregunta, sin_referente=True)
