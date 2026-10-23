from __future__ import annotations

import re
from dataclasses import dataclass

from ..herramientas.corpus import Fragmento
from ..herramientas.entidades import MAX_RAICES_ENTIDAD, nombra_entidad
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
# «su/sus» apuntan atrás salvo que la frase nombre a una persona («un cliente actualiza su información»).
_POSESIVOS = frozenset({"su", "sus"})
_PERSONAS = frozenset({"cliente", "clientes", "clienta", "asesor", "asesora", "asesores", "usuario", "persona"})
_ADVERBIOS_DE_SEGUIMIENTO = frozenset({"también", "tambien"})


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
    """Productos y secciones de nivel 2 que una pregunta puede nombrar; las preguntas frecuentes no cuentan."""
    vistas: dict[str, Entidad] = {}
    for fragmento in fragmentos:
        raices = fragmento.entidad_raices
        es_pregunta = fragmento.entidad.strip().endswith("?")
        if fragmento.entidad and not es_pregunta and raices and len(raices) <= MAX_RAICES_ENTIDAD:
            vistas.setdefault(fragmento.entidad, Entidad(fragmento.entidad, raices))
    return sorted(vistas.values(), key=lambda e: e.nombre)


def entidades_nombradas(texto: str, entidades: list[Entidad]) -> list[str]:
    raices = raices_unicas(texto)
    nombradas = [e for e in entidades if nombra_entidad(e.raices, raices)]
    # Si una entidad nombrada está contenida en otra también nombrada, se conserva la más específica.
    return [e.nombre for e in nombradas if not any(e.raices < o.raices for o in nombradas)]


def es_seguimiento(pregunta: str) -> bool:
    palabras = _RE_PALABRA.findall(pregunta.lower())  # con tildes: «está» no es «esta»
    if not palabras:
        return False
    if palabras[0] in _INICIOS_SEGUIMIENTO or any(p in _DEMOSTRATIVOS for p in palabras):
        return True
    if any(p in _ADVERBIOS_DE_SEGUIMIENTO for p in palabras):
        return True
    if any(p in _POSESIVOS for p in palabras) and not any(p in _PERSONAS for p in palabras):
        return True
    return any(
        actual in _DEMOSTRATIVOS_CERCANOS and normalizar(siguiente) in _SUSTANTIVOS
        for actual, siguiente in zip(palabras, palabras[1:], strict=False)
    )


def resolver_pregunta(pregunta: str, contexto: list[str], entidades: list[Entidad]) -> Resolucion:
    if not es_seguimiento(pregunta) or entidades_nombradas(pregunta, entidades):
        return Resolucion(pregunta)
    for anterior in reversed(contexto):
        # Se hereda un nombre del corpus, nunca texto libre del contexto: no hay por dónde inyectar.
        heredadas = entidades_nombradas(anterior, entidades)
        if heredadas:
            referente = ", ".join(heredadas)
            return Resolucion(f"{pregunta} ({referente})", referente=referente)
    return Resolucion(pregunta, sin_referente=True)
