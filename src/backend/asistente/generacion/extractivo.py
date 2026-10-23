from __future__ import annotations

import re

from ..dominio import ESTADO_EXITOSA, Fuente, RespuestaGenerada, respuesta_sin_informacion
from ..herramientas.corpus import Fragmento
from ..herramientas.entidades import es_producto, es_titulo_de_pregunta, es_transversal, nombra_entidad
from ..herramientas.recuperacion import Resultado
from ..herramientas.texto import RAICES_GENERICAS, raices_unicas

MAX_LINEAS_POR_FRAGMENTO = 12
MAX_FRAGMENTOS_EN_RESPUESTA = 2
RELACION_MINIMA_SEGUNDO_FRAGMENTO = 0.8
MINIMO_TERMINOS_COINCIDENTES = 2
MAX_LINEAS_SUBSECCION_CORTA = 3
_RE_PREFIJO_LISTA = re.compile(r"^(\d+\.|-)\s")


def seleccionar_lineas(
    fragmento: Fragmento,
    consulta: set[str] | frozenset[str],
    raices_nombradas: frozenset[str] = frozenset(),
    desconocidas: frozenset[str] = frozenset(),
    cubiertos: frozenset[str] = frozenset(),
    parcial: bool = False,
) -> list[str] | None:
    """Líneas del fragmento que responden a la pregunta, o ``None`` si el fragmento no la responde."""
    if fragmento.ruta_seccion == "Índice":
        return list(fragmento.lineas[:MAX_LINEAS_POR_FRAGMENTO])
    # Una pregunta frecuente cuyo título completo está en la pregunta la responde entera.
    if es_titulo_de_pregunta(fragmento) and _faq_completa(fragmento, consulta):
        return list(fragmento.lineas[:MAX_LINEAS_POR_FRAGMENTO])
    atributos = set(consulta) - fragmento.entidad_raices - raices_nombradas - RAICES_GENERICAS
    es_subseccion = fragmento.titulo_propio != fragmento.entidad
    if es_subseccion and raices_unicas(fragmento.titulo_propio) & atributos:
        return list(fragmento.lineas[:MAX_LINEAS_POR_FRAGMENTO])
    if not atributos:
        # Con palabras desconocidas, no devolver la descripción del producto como si respondiera.
        responde_todo = (
            not desconocidas
            or fragmento.ruta_seccion == "Índice"
            or (es_titulo_de_pregunta(fragmento) and len(fragmento.entidad_raices & set(consulta)) >= 2)
        )
        return list(fragmento.lineas[:MAX_LINEAS_POR_FRAGMENTO]) if responde_todo else None
    presentes = atributos & raices_unicas(fragmento.texto_indexable)
    # Lo que responde otra sección nombrada en la pregunta no se exige aquí («…y cómo se paga»).
    faltan = atributos - presentes - cubiertos
    if not presentes:
        return None
    if len(presentes) < 2 and faltan:
        # Subsección de un producto nombrado: si es corta responde entera; si no, solo completa otra que ya respondió.
        nombrado = bool(fragmento.entidad_raices) and fragmento.entidad_raices <= raices_nombradas
        corta = len(fragmento.lineas) <= MAX_LINEAS_SUBSECCION_CORTA
        if not (es_subseccion and (parcial or (nombrado and corta))):
            return None
        if len(fragmento.lineas) <= MAX_LINEAS_SUBSECCION_CORTA:
            return list(fragmento.lineas)
        return [linea for linea in fragmento.lineas if raices_unicas(linea) & presentes] or None
    puntuadas = [(raices_unicas(linea) & atributos, linea) for linea in fragmento.lineas]
    maximo = max((len(c) for c, _ in puntuadas), default=0)
    if maximo == 0:  # los atributos están en los encabezados
        return list(fragmento.lineas[:MAX_LINEAS_POR_FRAGMENTO])
    umbral = 2 if maximo >= 2 else 1
    elegidas = [linea for c, linea in puntuadas if len(c) >= umbral]
    # Cada atributo aún sin cubrir aporta sus líneas («qué cubre y cuánto paga al mes»).
    cubiertos_aqui = set().union(*(c for c, linea in puntuadas if linea in elegidas))
    for c, linea in puntuadas:
        if linea not in elegidas and c - cubiertos_aqui:
            elegidas.append(linea)
    orden = {linea: i for i, linea in enumerate(fragmento.lineas)}
    return sorted(elegidas, key=orden.__getitem__)[:MAX_LINEAS_POR_FRAGMENTO]


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


def _entidad_nombrada(fragmento: Fragmento, consulta: set[str] | frozenset[str]) -> bool:
    if es_titulo_de_pregunta(fragmento):  # un título de pregunta frecuente solo se «nombra» completo
        return _faq_completa(fragmento, consulta)
    return nombra_entidad(fragmento.entidad_raices, consulta)


def _faq_completa(fragmento: Fragmento, consulta: set[str] | frozenset[str]) -> bool:
    """La pregunta contiene el título; las palabras genéricas («microseguro») se omiten si quedan 2+ distintivas."""
    distintivas = fragmento.entidad_raices - RAICES_GENERICAS
    exigidas = distintivas if len(distintivas) >= 2 else fragmento.entidad_raices
    return bool(exigidas) and exigidas <= set(consulta)


def _raices_nombradas(
    resultados: list[Resultado], consulta: set[str] | frozenset[str], solo_productos: bool = False
) -> frozenset[str]:
    """Raíces de las entidades que la pregunta nombra: son contexto, no atributos pedidos."""
    nombradas: set[str] = set()
    for r in resultados:
        if (es_producto(r.fragmento) or not solo_productos) and _entidad_nombrada(r.fragmento, consulta):
            nombradas |= r.fragmento.entidad_raices
    return frozenset(nombradas)


def _faq_pertinente(fragmento: Fragmento, consulta: frozenset[str]) -> bool:
    """Una pregunta frecuente solo responde si su título comparte 2+ términos con la pregunta."""
    return not es_titulo_de_pregunta(fragmento) or len(fragmento.entidad_raices & consulta) >= 2


def _producto_ambiguo(
    fragmento: Fragmento, resultados: list[Resultado], consulta: frozenset[str], nombradas: frozenset[str],
) -> bool:
    """Sin producto nombrado, otro producto del documento responde igual de bien: elegir uno sería adivinar."""
    if nombradas or not es_producto(fragmento):
        return False

    def cubre(f: Fragmento) -> frozenset[str]:
        return frozenset(consulta & raices_unicas(f.texto_indexable)) - f.entidad_raices - RAICES_GENERICAS

    propios = cubre(fragmento)
    return any(
        es_producto(r.fragmento)
        and r.fragmento.entidad != fragmento.entidad
        and r.fragmento.archivo == fragmento.archivo
        and cubre(r.fragmento) >= propios
        and seleccionar_lineas(r.fragmento, consulta, nombradas) is not None
        for r in resultados
    )


def _misma_entidad(a: Fragmento, b: Fragmento) -> bool:
    if a.entidad or b.entidad:
        return a.archivo == b.archivo and a.entidad == b.entidad
    return a.archivo == b.archivo


def _segundo_bloque_valido(
    bloques: list[tuple[Fragmento, list[str]]],
    fragmento: Fragmento,
    consulta: frozenset[str],
    nombrada: bool,
) -> bool:
    """El segundo bloque aporta algo: otra entidad nombrada, otra subsección pedida o una sección transversal."""
    primero = bloques[0][0]
    if not _misma_entidad(primero, fragmento):
        return nombrada or (es_transversal(fragmento) and fragmento.archivo == primero.archivo)
    titulos_usados = {b.titulo_propio for b, _ in bloques}
    if fragmento.titulo_propio in titulos_usados:
        return False
    if raices_unicas(fragmento.titulo_propio) & consulta:
        return True
    ya_cubierto = raices_unicas(" ".join(primero.lineas)) | primero.entidad_raices
    nuevos = (consulta & raices_unicas(fragmento.texto_indexable)) - ya_cubierto - fragmento.entidad_raices
    return bool(nuevos - RAICES_GENERICAS)


def _terminos_distintivos(principal: Fragmento, consulta: frozenset[str]) -> frozenset[str]:
    """Raíces de la pregunta que nombran la sección del fragmento principal («pqr» en «Gestión de PQR»)."""
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
    desconocidas = frozenset(consulta) - consulta_util - RAICES_GENERICAS
    nombradas = _raices_nombradas(resultados, consulta_util)
    productos_nombrados = _raices_nombradas(resultados, consulta_util, solo_productos=True)
    # Las secciones generales de un documento nombrado cuentan el producto como coincidencia.
    documentos_nombrados = {
        r.fragmento.archivo for r in resultados if _entidad_nombrada(r.fragmento, consulta_util)
    }
    # Lo que responde una sección general nombrada del mismo documento no se exige a la ficha del producto.
    secciones_nombradas = frozenset().union(*(
        r.fragmento.entidad_raices for r in resultados
        if es_transversal(r.fragmento) and r.fragmento.archivo in documentos_nombrados
        and _entidad_nombrada(r.fragmento, consulta_util)
    ))
    pocos_terminos_utiles = len(consulta_util - RAICES_GENERICAS) < MINIMO_TERMINOS_COINCIDENTES
    # Lo que la pregunta nombra va primero; una pregunta frecuente contenida completa, antes que todo.
    resultados = sorted(resultados, key=lambda r: (
        not (es_titulo_de_pregunta(r.fragmento) and _faq_completa(r.fragmento, consulta_util)),
        not _entidad_nombrada(r.fragmento, consulta_util),
    ))
    # RF-12: un fragmento de respaldo debe mencionar algún término de la sección principal, no solo palabras comunes.
    exigidos = _terminos_distintivos(resultados[0].fragmento, consulta_util)

    bloques: list[tuple[Fragmento, list[str]]] = []
    fuentes: list[Fuente] = []
    puntaje_principal = 0.0
    for posicion, resultado in enumerate(resultados):
        fragmento = resultado.fragmento
        faq_completa = es_titulo_de_pregunta(fragmento) and _faq_completa(fragmento, consulta_util)
        if resultado.cobertura < umbral_cobertura and not faq_completa:
            continue
        nombrada = _entidad_nombrada(fragmento, consulta_util)
        coincidencias = len(resultado.terminos)
        if es_transversal(fragmento) and fragmento.archivo in documentos_nombrados:
            coincidencias += 1
        # Una sola coincidencia basta solo si es el nombre de la sección («capital» suelto no responde).
        if coincidencias < MINIMO_TERMINOS_COINCIDENTES and not (
            len(consulta) < MINIMO_TERMINOS_COINCIDENTES or (pocos_terminos_utiles and nombrada)
        ):
            continue
        # En una comparación el segundo producto nombrado no se descarta por puntaje.
        if bloques and resultado.puntaje < puntaje_principal * RELACION_MINIMA_SEGUNDO_FRAGMENTO and not nombrada:
            break
        if bloques and (bloques[0][0].ruta_seccion == "Índice" or not _segundo_bloque_valido(
            bloques, fragmento, consulta_util, nombrada
        )):
            continue
        es_respaldo = posicion > 0 and not bloques
        mismo_documento = fragmento.archivo == resultados[0].fragmento.archivo
        transversal_del_mismo_documento = es_transversal(fragmento) and mismo_documento
        if (
            es_respaldo
            and exigidos
            and not transversal_del_mismo_documento
            and not exigidos & raices_unicas(fragmento.texto_indexable)
        ):
            continue
        if not _faq_pertinente(fragmento, consulta_util):
            continue
        if not bloques and _producto_ambiguo(fragmento, resultados, consulta_util, productos_nombrados):
            continue
        restar = productos_nombrados if es_producto(fragmento) else nombradas
        parcial = bool(bloques) and nombrada and _misma_entidad(bloques[0][0], fragmento)
        lineas = seleccionar_lineas(fragmento, consulta_util, restar, desconocidas, secciones_nombradas, parcial)
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
