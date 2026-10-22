"""Motor de respuesta extractivo: responde únicamente con líneas de los documentos.

No genera texto nuevo: selecciona las líneas del fragmento recuperado que
responden a la pregunta y las cita. Es el modo por defecto (sin LLM), 100 %
local, determinista y, por construcción, incapaz de "inventar" información.
"""
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
_RE_PREFIJO_LISTA = re.compile(r"^(\d+\.|-)\s")


def seleccionar_lineas(
    fragmento: Fragmento,
    consulta: set[str] | frozenset[str],
    raices_nombradas: frozenset[str] = frozenset(),
    desconocidas: frozenset[str] = frozenset(),
    cubiertos: frozenset[str] = frozenset(),
) -> list[str] | None:
    """Líneas del fragmento que responden a la pregunta, o ``None`` si no responde.

    ``raices_nombradas`` son las raíces de las entidades (productos, secciones)
    que la pregunta nombra; el resto de raíces son los *atributos* pedidos.

    Reglas, en orden:
    1. Si la pregunta nombra la subsección del fragmento (``requisitos``,
       ``garantías``, ``actividades financiables``), toda la subsección es la
       respuesta.
    2. Si la pregunta solo nombra la entidad (``¿Qué es Vida Protegida?``), se
       devuelve el fragmento completo. Si además pide algo que no existe en la base
       (``desconocidas``: «¿hay carencia…?» mal escrito o inexistente), no se responde
       con la descripción del producto: ``None``.
    3. Si el fragmento menciona los atributos pedidos (todos, o al menos dos de
       ellos en preguntas con varios), se devuelven las líneas que más atributos
       contienen (``Monto máximo: $50.000.000``; varias filas si se piden
       varias condiciones).
    4. Si no, el fragmento no responde la pregunta (p. ej. ``periodo de gracia``
       de un producto que no lo tiene, o ``prima mensual`` de un crédito):
       devolver ``None`` evita contestar con datos que no están en el documento.
    """
    if fragmento.ruta_seccion == "Índice":  # la pregunta nombra el documento: su índice es la respuesta
        return list(fragmento.lineas[:MAX_LINEAS_POR_FRAGMENTO])
    atributos = set(consulta) - fragmento.entidad_raices - raices_nombradas - RAICES_GENERICAS
    es_subseccion = fragmento.titulo_propio != fragmento.entidad
    if es_subseccion and raices_unicas(fragmento.titulo_propio) & atributos:
        return list(fragmento.lineas[:MAX_LINEAS_POR_FRAGMENTO])
    if not atributos:
        # B5: con palabras que no existen en la base, la sección completa solo responde si es el índice o
        # una pregunta frecuente cuyo título comparte 2+ términos con la pregunta; si no, «¿qué papeles
        # necesito para el Impulso?» devolvería la descripción del producto («Dirigido a…»).
        responde_todo = (
            not desconocidas
            or fragmento.ruta_seccion == "Índice"
            or (es_titulo_de_pregunta(fragmento) and len(fragmento.entidad_raices & set(consulta)) >= 2)
        )
        return list(fragmento.lineas[:MAX_LINEAS_POR_FRAGMENTO]) if responde_todo else None
    presentes = atributos & raices_unicas(fragmento.texto_indexable)
    # Lo que responde otra sección nombrada en la misma pregunta no se exige aquí («la prima de Vida
    # Protegida y cómo se paga»: el «pago» lo responde «Pago de primas»).
    faltan = atributos - presentes - cubiertos
    if not presentes or (len(presentes) < 2 and faltan):
        return None
    puntuadas = [(raices_unicas(linea) & atributos, linea) for linea in fragmento.lineas]
    maximo = max((len(c) for c, _ in puntuadas), default=0)
    if maximo == 0:  # los atributos están en los encabezados: la sección completa responde
        return list(fragmento.lineas[:MAX_LINEAS_POR_FRAGMENTO])
    umbral = 2 if maximo >= 2 else 1
    elegidas = [linea for c, linea in puntuadas if len(c) >= umbral]
    # Cada atributo pedido que quedó sin cubrir aporta sus líneas («qué cubre y cuánto paga al mes»).
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
    """La pregunta nombra la entidad del fragmento (p. ej. ambos productos de una comparación)."""
    return nombra_entidad(fragmento.entidad_raices, consulta)


def _raices_nombradas(
    resultados: list[Resultado], consulta: set[str] | frozenset[str], solo_productos: bool = False
) -> frozenset[str]:
    """Unión de las raíces de las entidades que la pregunta nombra (no se piden como atributo).

    Para evaluar la ficha de un producto se restan solo los productos nombrados (``solo_productos``): en
    «¿cuánto tarda una reclamación de Negocio Seguro?» la reclamación es lo que se pide y la ficha no
    responde por ella. Para una sección o pregunta frecuente se restan todas: en «¿tiene costo la
    solicitud de crédito?» la «Solicitud de Crédito» es contexto.
    """
    nombradas: set[str] = set()
    for r in resultados:
        if (es_producto(r.fragmento) or not solo_productos) and _entidad_nombrada(r.fragmento, consulta):
            nombradas |= r.fragmento.entidad_raices
    return frozenset(nombradas)


def _faq_pertinente(fragmento: Fragmento, consulta: frozenset[str]) -> bool:
    """Una pregunta frecuente responde si su título comparte 2+ términos con la pregunta: si solo coincide
    su texto («solicitudes de crédito»), es casualidad («¿la solicitud tiene costo?» ≠ actualización de datos)."""
    return not es_titulo_de_pregunta(fragmento) or len(fragmento.entidad_raices & consulta) >= 2


def _producto_ambiguo(
    fragmento: Fragmento, resultados: list[Resultado], consulta: frozenset[str], nombradas: frozenset[str],
) -> bool:
    """B1: la pregunta no nombra producto y otro producto responde lo mismo: elegir uno sería adivinar.

    Un rival cuenta solo si cubre todos los términos de la pregunta que cubre el candidato: si la
    maquinaria o las garantías solo aparecen en un producto, la respuesta no es ambigua.
    """
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
    """Dos fragmentos de la misma entidad (o del mismo documento sin entidad) son redundantes."""
    if a.entidad or b.entidad:
        return a.archivo == b.archivo and a.entidad == b.entidad
    return a.archivo == b.archivo


def _segundo_bloque_valido(
    bloques: list[tuple[Fragmento, list[str]]],
    fragmento: Fragmento,
    consulta: frozenset[str],
    nombrada: bool,
) -> bool:
    """Un segundo bloque aporta algo: otra entidad nombrada (comparación), otra subsección nombrada
    del mismo producto («requisitos y periodo de gracia del Agro Crece», B11) o una sección
    transversal del mismo documento («exclusiones de Vida Protegida»)."""
    primero = bloques[0][0]
    if not _misma_entidad(primero, fragmento):
        return nombrada or (es_transversal(fragmento) and fragmento.archivo == primero.archivo)
    titulos_usados = {b.titulo_propio for b, _ in bloques}
    if fragmento.titulo_propio in titulos_usados:
        return False
    if raices_unicas(fragmento.titulo_propio) & consulta:  # nombra la subsección («…y sus garantías»)
        return True
    # o aporta un atributo pedido que el primer bloque no tiene («requisitos y periodo de gracia del Agro Crece»)
    ya_cubierto = raices_unicas(" ".join(primero.lineas)) | primero.entidad_raices
    nuevos = (consulta & raices_unicas(fragmento.texto_indexable)) - ya_cubierto - fragmento.entidad_raices
    return bool(nuevos - RAICES_GENERICAS)


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
    # Palabras que no existen en la base (sin contar las de categoría como «pasos» o «proceso»).
    desconocidas = frozenset(consulta) - consulta_util - RAICES_GENERICAS
    nombradas = _raices_nombradas(resultados, consulta_util)
    productos_nombrados = _raices_nombradas(resultados, consulta_util, solo_productos=True)
    # Documentos de los productos nombrados: sus secciones generales cuentan el producto como coincidencia
    # («¿qué exclusiones tiene Vida Protegida?» → Exclusiones generales coincide en «exclusiones» + el producto).
    documentos_nombrados = {
        r.fragmento.archivo for r in resultados if _entidad_nombrada(r.fragmento, consulta_util)
    }
    # Atributos que responde una sección general nombrada del mismo documento («la prima de Vida Protegida y
    # cómo se paga» → «Pago de primas»): no se exigen a la ficha del producto. Una pregunta frecuente de otro
    # documento no cuenta: si la nombra, ella es la respuesta.
    secciones_nombradas = frozenset().union(*(
        r.fragmento.entidad_raices for r in resultados
        if es_transversal(r.fragmento) and r.fragmento.archivo in documentos_nombrados
        and _entidad_nombrada(r.fragmento, consulta_util)
    ))
    pocos_terminos_utiles = len(consulta_util - RAICES_GENERICAS) < MINIMO_TERMINOS_COINCIDENTES
    # Lo que la pregunta nombra por su nombre va primero («los pasos de una solicitud de crédito» →
    # «Solicitud de Crédito», aunque una pregunta frecuente mencione «solicitudes de crédito»).
    resultados = sorted(resultados, key=lambda r: not _entidad_nombrada(r.fragmento, consulta_util))
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
        fragmento = resultado.fragmento
        nombrada = _entidad_nombrada(fragmento, consulta_util)
        coincidencias = len(resultado.terminos)
        if es_transversal(fragmento) and fragmento.archivo in documentos_nombrados:
            coincidencias += 1
        # B7: con un solo término útil (en el corpus y no de categoría) basta si ese término es el nombre de
        # la sección («¿cuánto se demora en desembolsar un crédito?» → Desembolso); una palabra suelta no
        # («¿cuál es la capital de Francia?» no debe responder con «abonos a capital»).
        if coincidencias < MINIMO_TERMINOS_COINCIDENTES and not (
            len(consulta) < MINIMO_TERMINOS_COINCIDENTES or (pocos_terminos_utiles and nombrada)
        ):
            continue
        # B9: en una comparación el segundo producto nombrado no se descarta por puntaje.
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
        lineas = seleccionar_lineas(fragmento, consulta_util, restar, desconocidas, secciones_nombradas)
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
