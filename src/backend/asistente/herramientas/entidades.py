from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from .corpus import Fragmento
from .texto import normalizar, raices_unicas

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
    """Crédito o microseguro con ficha, no una sección general, procedimiento ni pregunta frecuente."""
    return fragmento.producto and not es_transversal(fragmento)


def pertenece_a(archivo: str, documentos: Sequence[str]) -> bool:
    """Compara el nombre del archivo con los documentos sin tildes ni mayúsculas."""
    return normalizar(Path(archivo).stem) in {normalizar(d) for d in documentos}
