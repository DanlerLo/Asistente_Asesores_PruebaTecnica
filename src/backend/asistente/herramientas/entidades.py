"""Reglas sobre las entidades del corpus (productos y secciones de nivel 2), compartidas por la recuperación,
el motor extractivo, el contexto de conversación y los agentes.

* Una pregunta **nombra** una entidad si contiene su nombre completo o casi completo.
* Una entidad es **transversal** si aplica a todo su documento («Exclusiones generales», «Reclamaciones»,
  «Pago de primas», «Condiciones generales de los créditos»): cuando la pregunta nombra un producto, sus
  secciones transversales también pueden responder («¿qué exclusiones tiene Vida Protegida?»).
* Los títulos con forma de pregunta (preguntas frecuentes) no son entidades: no nombran un producto ni
  deben acaparar la búsqueda.
"""
from __future__ import annotations

from .corpus import Fragmento
from .texto import raices_unicas

MAX_RAICES_ENTIDAD = 5
_RAICES_TRANSVERSALES = frozenset(raices_unicas("general generales reclamaciones pago exclusiones"))


def nombra_entidad(raices_entidad: frozenset[str], consulta: set[str] | frozenset[str]) -> bool:
    """Nombre completo («Desembolso», «Vida Protegida») o casi completo («Productivo Impulso»)."""
    if not raices_entidad or len(raices_entidad) > MAX_RAICES_ENTIDAD:
        return False
    coincidencias = len(raices_entidad & consulta)
    if coincidencias == len(raices_entidad):
        return True
    return coincidencias >= 2 and coincidencias >= len(raices_entidad) - 1


def es_titulo_de_pregunta(fragmento: Fragmento) -> bool:
    return fragmento.entidad.strip().endswith("?")


def es_transversal(fragmento: Fragmento) -> bool:
    return bool(fragmento.entidad_raices & _RAICES_TRANSVERSALES) and not es_titulo_de_pregunta(fragmento)


def es_producto(fragmento: Fragmento) -> bool:
    """Un crédito o un microseguro con ficha (lo marca ``corpus._marcar_productos``), no una sección general,
    un procedimiento, una política ni una pregunta frecuente."""
    return fragmento.producto and not es_transversal(fragmento)
