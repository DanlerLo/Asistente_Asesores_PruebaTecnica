from __future__ import annotations

from collections.abc import Sequence

from ..dominio import ESTADO_EXITOSA, Fuente, RespuestaGenerada
from ..herramientas.corpus import Fragmento
from ..herramientas.entidades import es_producto, nombra_entidad, pertenece_a
from ..herramientas.texto import normalizar, raices_unicas

# Palabras que no son atributos: categorías y calificadores de superlativo.
_NO_ATRIBUTOS = frozenset(raices_unicas("credito creditos microseguro microseguros producto productos poliza"))
_CALIFICADORES = frozenset(raices_unicas("minimo maximo"))
_MINIMO_PRODUCTOS = 2
_MAX_LINEAS_POR_PRODUCTO = 3


def listar_por_producto(
    pregunta: str, fragmentos: Sequence[Fragmento], documentos: Sequence[str]
) -> RespuestaGenerada | None:
    """Respuesta «por producto», o ``None`` si la pregunta nombra un producto o no pide un atributo común."""
    consulta = raices_unicas(pregunta)
    productos = [f for f in fragmentos if pertenece_a(f.archivo, documentos) and es_producto(f)]
    if not productos or any(nombra_entidad(f.entidad_raices, consulta) for f in productos):
        return None
    # Tampoco si nombra un producto a medias («el Educativo») o una sección que no es producto.
    if any((f.entidad_raices - _NO_ATRIBUTOS) & consulta for f in productos):
        return None
    secciones = [f for f in fragmentos if pertenece_a(f.archivo, documentos) and f.entidad and not es_producto(f)]
    if any(nombra_entidad(f.entidad_raices, consulta) for f in secciones):
        return None
    atributos = consulta - _NO_ATRIBUTOS - _CALIFICADORES
    calificadores = consulta & _CALIFICADORES
    if not atributos:
        return None

    candidatas: dict[str, list[tuple[Fragmento, str]]] = {}
    for fragmento in productos:
        for linea in fragmento.lineas:
            if atributos <= raices_unicas(linea):
                candidatas.setdefault(fragmento.entidad, []).append((fragmento, linea))
    if len(candidatas) < _MINIMO_PRODUCTOS:
        # Atributo que es subsección («requisitos»): si coinciden varias, la que tienen menos productos.
        por_titulo: dict[str, dict[str, list[tuple[Fragmento, str]]]] = {}
        for fragmento in productos:
            es_subseccion = fragmento.titulo_propio != fragmento.entidad
            if es_subseccion and raices_unicas(fragmento.titulo_propio) & atributos:
                por_titulo.setdefault(normalizar(fragmento.titulo_propio), {})[fragmento.entidad] = [
                    (fragmento, linea) for linea in fragmento.lineas
                ]
        candidatas = min(por_titulo.values(), key=len) if por_titulo else {}
    if len(candidatas) < _MINIMO_PRODUCTOS:
        return None

    elegidas: list[tuple[Fragmento, str]] = []
    for lineas in candidatas.values():
        con_calificador = [(f, linea) for f, linea in lineas if calificadores & raices_unicas(linea)]
        elegidas.extend((con_calificador or lineas)[:_MAX_LINEAS_POR_PRODUCTO])

    documento = elegidas[0][0].documento
    partes = [f"Según «{documento}», por producto:"]
    partes += [f"- {fragmento.entidad}: {linea.lstrip('- ')}" for fragmento, linea in elegidas]
    citadas = list(dict.fromkeys((f.archivo, f.ruta_seccion) for f, _ in elegidas))
    citas = "; ".join(f"{archivo} › {seccion}" for archivo, seccion in citadas)
    partes += ["", f"Fuentes: {citas}"]
    fuentes = [
        Fuente(
            documento=documento,
            archivo=archivo,
            seccion=seccion,
            puntaje=1.0,
            extracto=" ".join(
                linea for f, linea in elegidas if (f.archivo, f.ruta_seccion) == (archivo, seccion)
            )[:500],
        )
        for archivo, seccion in citadas
    ]
    return RespuestaGenerada(texto="\n".join(partes), estado=ESTADO_EXITOSA, fuentes=fuentes)
