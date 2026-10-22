"""Motor de respuesta extractivo: responde únicamente con líneas de los documentos.

No genera texto nuevo: selecciona las líneas del fragmento recuperado que
responden a la pregunta y las cita. Es el modo por defecto (sin LLM), 100 %
local, determinista y, por construcción, incapaz de "inventar" información.
"""
from __future__ import annotations

import re

from ..dominio import ESTADO_EXITOSA, Fuente, RespuestaGenerada, respuesta_sin_informacion
from ..herramientas.corpus import Fragmento
from ..herramientas.recuperacion import Resultado
from ..herramientas.texto import raices_unicas

MAX_LINEAS_POR_FRAGMENTO = 12
MAX_FRAGMENTOS_EN_RESPUESTA = 2
RELACION_MINIMA_SEGUNDO_FRAGMENTO = 0.8
MINIMO_TERMINOS_COINCIDENTES = 2
# Palabras de categoría que no distinguen un atributo ("¿qué cubre el seguro X?").
RAICES_GENERICAS = frozenset(
    {
        "segur", "microsegur", "credit", "product", "servici", "poliz",  # categorías
        "paso", "proces", "procedimient", "etap", "fase",  # meta-palabras de procedimientos
        "diferenci", "compar", "versus", "vs", "diferent",  # meta-palabras de comparación
    }
)  # para preguntas con 2+ términos; evita falsos positivos por una sola palabra
_RE_PREFIJO_LISTA = re.compile(r"^(\d+\.|-)\s")


def seleccionar_lineas(
    fragmento: Fragmento, consulta: set[str] | frozenset[str], raices_nombradas: frozenset[str] = frozenset()
) -> list[str] | None:
    """Líneas del fragmento que responden a la pregunta, o ``None`` si no responde.

    ``raices_nombradas`` son las raíces de las entidades (productos, secciones)
    que la pregunta nombra; el resto de raíces son los *atributos* pedidos.

    Reglas, en orden:
    1. Si la pregunta nombra la subsección del fragmento (``requisitos``,
       ``garantías``, ``actividades financiables``), toda la subsección es la
       respuesta.
    2. Si la pregunta solo nombra la entidad (``¿Qué es Vida Protegida?``), se
       devuelve el fragmento completo.
    3. Si el fragmento menciona los atributos pedidos (todos, o al menos dos de
       ellos en preguntas con varios), se devuelven las líneas que más atributos
       contienen (``Monto máximo: $50.000.000``; varias filas si se piden
       varias condiciones).
    4. Si no, el fragmento no responde la pregunta (p. ej. ``periodo de gracia``
       de un producto que no lo tiene, o ``prima mensual`` de un crédito):
       devolver ``None`` evita contestar con datos que no están en el documento.
    """
    atributos = set(consulta) - fragmento.entidad_raices - raices_nombradas - RAICES_GENERICAS
    es_subseccion = fragmento.titulo_propio != fragmento.entidad
    if es_subseccion and raices_unicas(fragmento.titulo_propio) & atributos:
        return list(fragmento.lineas[:MAX_LINEAS_POR_FRAGMENTO])
    if not atributos:
        return list(fragmento.lineas[:MAX_LINEAS_POR_FRAGMENTO])
    presentes = atributos & raices_unicas(fragmento.texto_indexable)
    if not presentes or (len(presentes) < 2 and len(presentes) < len(atributos)):
        return None
    puntuadas = [(len(raices_unicas(linea) & atributos), linea) for linea in fragmento.lineas]
    maximo = max((n for n, _ in puntuadas), default=0)
    if maximo == 0:  # los atributos están en los encabezados: la sección completa responde
        return list(fragmento.lineas[:MAX_LINEAS_POR_FRAGMENTO])
    umbral = 2 if maximo >= 2 else 1
    return [linea for n, linea in puntuadas if n >= umbral][:MAX_LINEAS_POR_FRAGMENTO]


def _componer_texto(bloques: list[tuple[Fragmento, list[str]]]) -> str:
    partes: list[str] = []
    for fragmento, lineas in bloques:
        seccion = fragmento.ruta_seccion or "documento completo"
        partes.append(f"Según «{fragmento.documento}» (sección: {seccion}):")
        for linea in lineas:
            partes.append(linea if _RE_PREFIJO_LISTA.match(linea) else f"- {linea}")
        partes.append("")
    citas = "; ".join(
        f"{fragmento.archivo} › {fragmento.ruta_seccion or 'documento completo'}" for fragmento, _ in bloques
    )
    partes.append(f"{'Fuentes' if len(bloques) > 1 else 'Fuente'}: {citas}")
    return "\n".join(partes)


def _entidad_nombrada(fragmento: Fragmento, consulta: set[str] | frozenset[str], minimo: int = 2) -> bool:
    """La pregunta nombra la entidad del fragmento (p. ej. ambos productos de una comparación)."""
    raices = fragmento.entidad_raices
    if not raices:
        return False
    coincidencias = len(raices & consulta)
    if coincidencias == len(raices):  # nombre completo ("Desembolso", "Vida Protegida")
        return True
    return coincidencias >= minimo and coincidencias >= len(raices) - 1


def _raices_nombradas(resultados: list[Resultado], consulta: set[str] | frozenset[str]) -> frozenset[str]:
    """Unión de las raíces de todas las entidades que la pregunta nombra."""
    nombradas: set[str] = set()
    for r in resultados:
        if _entidad_nombrada(r.fragmento, consulta):
            nombradas |= r.fragmento.entidad_raices
    return frozenset(nombradas)


def _misma_entidad(a: Fragmento, b: Fragmento) -> bool:
    """Dos fragmentos de la misma entidad (o del mismo documento sin entidad) son redundantes."""
    if a.entidad or b.entidad:
        return a.archivo == b.archivo and a.entidad == b.entidad
    return a.archivo == b.archivo


def _terminos_distintivos(principal: Fragmento, consulta: frozenset[str]) -> frozenset[str]:
    """Raíces de la pregunta que nombran la sección del fragmento mejor puntuado («pqr» en «Gestión de PQR»).

    Los títulos con forma de pregunta (preguntas frecuentes, llenos de palabras comunes) y las
    palabras de categoría no cuentan.
    """
    titulos: set[str] = set()
    for parte in principal.ruta_seccion.split(">"):
        if not parte.strip().endswith("?"):
            titulos |= raices_unicas(parte)
    return frozenset((consulta & titulos) - RAICES_GENERICAS)


def responder_extractivo(pregunta: str, resultados: list[Resultado], umbral_cobertura: float) -> RespuestaGenerada:
    consulta = raices_unicas(pregunta)
    if not consulta or not resultados:
        return respuesta_sin_informacion()
    consulta_util = resultados[0].consulta_util or frozenset(consulta)
    nombradas = _raices_nombradas(resultados, consulta_util)
    # RF-12: si el fragmento mejor puntuado trata lo que nombra la pregunta («Gestión de PQR») pero
    # no responde el atributo pedido, no se recurre a otro fragmento que solo coincide en palabras
    # comunes («tiempo», «válido» ≈ «Validación» de microseguros): el respaldo debe mencionar al
    # menos un término de esa sección. Solo aplica a ese respaldo, nunca al fragmento principal.
    exigidos = _terminos_distintivos(resultados[0].fragmento, consulta_util)

    bloques: list[tuple[Fragmento, list[str]]] = []
    fuentes: list[Fuente] = []
    puntaje_principal = 0.0
    for posicion, resultado in enumerate(resultados):
        if resultado.cobertura < umbral_cobertura:
            continue
        if len(consulta) >= MINIMO_TERMINOS_COINCIDENTES and len(resultado.terminos) < MINIMO_TERMINOS_COINCIDENTES:
            continue
        if bloques and resultado.puntaje < puntaje_principal * RELACION_MINIMA_SEGUNDO_FRAGMENTO:
            break
        if bloques and (
            bloques[0][0].ruta_seccion == "Índice"
            or _misma_entidad(bloques[0][0], resultado.fragmento)
            or not _entidad_nombrada(resultado.fragmento, consulta_util)
        ):
            continue
        es_respaldo = posicion > 0 and not bloques
        if es_respaldo and exigidos and not exigidos & raices_unicas(resultado.fragmento.texto_indexable):
            continue
        lineas = seleccionar_lineas(resultado.fragmento, consulta_util, nombradas)
        if not lineas:
            continue
        if not bloques:
            puntaje_principal = resultado.puntaje
        bloques.append((resultado.fragmento, lineas))
        fuentes.append(
            Fuente(
                documento=resultado.fragmento.documento,
                archivo=resultado.fragmento.archivo,
                seccion=resultado.fragmento.ruta_seccion or "documento completo",
                puntaje=min(1.0, resultado.puntaje / resultados[0].puntaje) if resultados[0].puntaje else 0.0,
                extracto=" ".join(lineas)[:500],
            )
        )
        if len(bloques) >= MAX_FRAGMENTOS_EN_RESPUESTA:
            break

    if not bloques:
        return respuesta_sin_informacion()
    return RespuestaGenerada(texto=_componer_texto(bloques), estado=ESTADO_EXITOSA, fuentes=fuentes)
