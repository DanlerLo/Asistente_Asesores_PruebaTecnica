"""Guardrails: validación de entrada, bloqueo por seguridad y filtro de salida.

Tres capas independientes (defensa en profundidad):

1. ``validar_pregunta``: forma de la entrada (tipo, vacía, longitud, caracteres
   de control). Un fallo aquí es un error de solicitud (HTTP 400), no una
   consulta.
2. ``evaluar_entrada``: intención de la pregunta. Bloquea solicitudes de
   credenciales, configuraciones internas, información restringida, datos de
   otros clientes e intentos de inyección de prompt. Estado "Bloqueada por
   seguridad".
3. ``filtrar_salida``: última línea de defensa sobre la respuesta generada
   (especialmente relevante con LLM): si contiene un valor sensible conocido o
   algo con forma de credencial, la respuesta se reemplaza por el bloqueo.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import partial

from ..herramientas.texto import normalizar

# Políticas que respaldan un bloqueo (archivo, sección). El orquestador las cita solo si existen en el corpus.
CITAS_BLOQUEO: tuple[tuple[str, str], ...] = (
    ("Manual del Asesor Comercial.md", "Información Sensible"),
    ("Políticas de Atención.md", "Política de Escalamiento"),
)


class ErrorValidacion(ValueError):
    def __init__(self, codigo: str, mensaje: str) -> None:
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje


_RE_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def validar_pregunta(valor: object, max_longitud: int) -> str:
    """Devuelve la pregunta saneada o lanza ``ErrorValidacion``."""
    if not isinstance(valor, str):
        raise ErrorValidacion("TIPO_INVALIDO", "El campo 'pregunta' debe ser un texto.")
    # RF-S9: sin caracteres invisibles de formato (espacio de ancho cero, guion suave…), que solo sirven
    # para partir palabras y evadir las reglas; tampoco se guardan ni viajan al LLM.
    pregunta = _sin_invisibles(valor).strip()
    if not pregunta:
        raise ErrorValidacion("PREGUNTA_VACIA", "La pregunta no puede estar vacía.")
    if len(pregunta) > max_longitud:
        raise ErrorValidacion(
            "PREGUNTA_DEMASIADO_LARGA",
            f"La pregunta supera el máximo de {max_longitud} caracteres (tiene {len(pregunta)}).",
        )
    if _RE_CONTROL.search(pregunta):
        raise ErrorValidacion(
            "CARACTERES_NO_PERMITIDOS", "La pregunta contiene caracteres de control no permitidos."
        )
    return " ".join(pregunta.split())


MAX_ELEMENTOS_CONTEXTO = 3


def validar_contexto(valor: object, max_longitud: int) -> list[str]:
    """Preguntas anteriores de la conversación (opcional): hasta las 3 más recientes, validadas como preguntas."""
    if valor is None:
        return []
    if not isinstance(valor, list):
        raise ErrorValidacion("CONTEXTO_INVALIDO", "El campo 'contexto' debe ser una lista de preguntas anteriores.")
    contexto: list[str] = []
    for elemento in valor[-MAX_ELEMENTOS_CONTEXTO:]:
        try:
            contexto.append(validar_pregunta(elemento, max_longitud))
        except ErrorValidacion as error:
            raise ErrorValidacion("CONTEXTO_INVALIDO", f"Contexto inválido: {error.mensaje}") from error
    return contexto


def _sin_invisibles(texto: str) -> str:
    return "".join(c for c in texto if unicodedata.category(c) != "Cf")


# RF-S9: letras cirílicas y griegas que se ven idénticas a las latinas («tоken» con «о» cirílica).
_HOMOGLIFOS = str.maketrans(
    {"а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "і": "i", "ј": "j", "ѕ": "s",
     "к": "k", "м": "m", "т": "t", "в": "b", "н": "h", "ο": "o", "α": "a", "ε": "e", "ι": "i", "κ": "k",
     "ν": "v", "ρ": "p", "τ": "t", "υ": "u", "χ": "x"}
)
# Dígitos usados como letras, solo dentro de palabras que mezclan letras y dígitos («t0ken», «c1ave»):
# los montos («$50.000.000») y cantidades («10 meses») no se tocan.
# El «1» se lee como «i» («adm1n») o como «l» («c1ave»): se prueban ambas lecturas.
_LEET = (str.maketrans("013457", "oieast"), str.maketrans("013457", "oleast"))
_RE_PALABRA_MIXTA = re.compile(r"\b(?=[a-z0-9]*[a-z])(?=[a-z0-9]*[0-9])[a-z0-9]+\b")


def _traducir(coincidencia: re.Match[str], tabla: dict[int, int]) -> str:
    return coincidencia.group(0).translate(tabla)


def textos_para_reglas(pregunta: str) -> list[str]:
    """Variantes normalizadas sobre las que se evalúan las reglas de entrada (RF-S9)."""
    base = unicodedata.normalize("NFKC", _sin_invisibles(pregunta)).lower().translate(_HOMOGLIFOS)
    texto = normalizar(base)
    variantes = [texto]
    for tabla in _LEET:
        sin_leet = _RE_PALABRA_MIXTA.sub(partial(_traducir, tabla=tabla), texto)
        if sin_leet not in variantes:
            variantes.append(sin_leet)
    return variantes


# RF-S14: piezas para reconocer la intención, no palabras sueltas.
_ORDEN_DE_ENTREGA = (
    r"\b(dame|damel[oa]s?|dime|muestra|muestrame|muestramel[oa]s?|pasame|pasamel[oa]s?|revela|revelame|"
    r"entrega|entregame|enviame|comparteme|compartemel[oa]s?|consultame|buscame|necesito|"
    r"quiero (ver|saber|conocer|tener)|cual es|cuales son|cuanto debe)\b"
)
_DATO_DE_PERSONA = (
    r"(datos|informacion|saldo|cedula|telefono|celular|direccion|historial|deuda|cuenta|cuentas|correo|"
    r"movimientos)"
)
_DATO_PERSONAL_ESTRICTO = r"(saldo|cedula|telefono|celular|direccion|deuda|movimientos|correo)"
# Preguntas sobre la propia política («¿qué hago si…?», «¿puedo…?», «¿qué se considera…?»): las responde
# el Manual. Solo eximen de las categorías de abajo y nunca si además traen una orden de entrega.
_PREGUNTA_DE_POLITICA = re.compile(
    r"^\W*(que (hago|debo hacer|se hace|hacer|se considera|es|significa)|"
    r"como (debo |se debe |puedo |se )?(actuar|responder|manejar|proceder|proteger|tratar|protege|maneja)|"
    r"puedo|se puede|esta permitido|es permitido|debo|que dice|segun)\b"
)
_RE_ORDEN_DE_ENTREGA = re.compile(_ORDEN_DE_ENTREGA)
_CATEGORIAS_EXENTAS_EN_POLITICA = frozenset({"datos_de_terceros", "informacion_restringida"})

# Reglas evaluadas sobre el texto normalizado (minúsculas, sin tildes).
REGLAS_ENTRADA: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (categoria, re.compile(patron))
    for categoria, patron in (
        (
            "credenciales",
            r"\b(tokens?|claves?|contrasenas?|passwords?|credencial(es)?|api ?keys?|secretos?|"
            r"llaves? (de acceso|privadas?))\b",
        ),
        (
            "acceso_administrativo",
            r"\b(usuarios?|cuentas?|accesos?|credenciales?|claves?) (del? )?(administrador(es)?|admin)\b|\badmin\b",
        ),
        (
            "configuracion_interna",
            r"\b(sistemas?|configuracion(es)?|infraestructura|servidor(es)?|bases? de datos|arquitectura|"
            r"codigo|prompts?|variables?|parametros?) (de )?(internos?|internas?|administrativos?|"
            r"administrativas?|del sistema|reservados?|reservadas?|del asistente)\b|"
            r"\bprompt (administrativo|del sistema|de sistema)\b|\bsystem prompt\b|"
            r"\binstrucciones (internas|del sistema|del asistente)\b",
        ),
        (
            "informacion_restringida",
            r"\binformacion (restringida|confidencial|reservada|interna|secreta)\b|"
            r"\b(documentos?|archivos?|datos?) (restringid[ao]s?|confidencial(es)?|reservad[ao]s?)\b|"
            # RF-S14: «restringido»/«confidencial» sueltos ya no bloquean («actividades restringidas»).
            r"\b(todo )?lo (restringido|confidencial|reservado)\b",
        ),
        (
            "inyeccion_de_prompt",
            r"\b(ignora(r)?|ignore|disregard|forget|olvida(r)?) (all |todas? )?"
            r"(previous |prior |your |the |las? |tus? |sus? |estas? )?"
            r"(instrucciones|instructions|reglas|rules|politicas|restricciones|guidelines)\b|"
            r"\b(actua|actue|comportate) como\b|"
            r"\beres (ahora )?(un|una|el|la) (administrador|desarrollador|sistema|ia sin)\b|"
            r"\bmodo (desarrollador|administrador|admin|dios|sin restricciones)\b|"
            r"\b(revela|muestra|imprime|repite|entrega)(me)? (tu|el|las|tus|toda la) "
            r"(prompt|instrucciones|configuracion|informacion restringida)\b|"
            r"\bjailbreak\b|\bsin restricciones\b|\bno tienes (reglas|restricciones)\b",
        ),
        (
            "datos_de_terceros",
            # RF-S14: intención de obtener un dato de una persona concreta, no la mención de «datos de un
            # cliente» («¿cada cuánto se actualizan los datos de un cliente?» es una pregunta de procedimiento).
            _ORDEN_DE_ENTREGA + r".{0,40}\b" + _DATO_DE_PERSONA + r"\b.{0,25}\b(del?|de la|de los|de las) "
            r"(un |una |este |ese |esta |esa |otro |otra |otros |otras )?"
            r"(cliente|clientes|senor|senora|persona|personas|usuario|usuarios|asociado|asociada)\b|"
            + _ORDEN_DE_ENTREGA + r".{0,40}\b" + _DATO_PERSONAL_ESTRICTO + r" de "
            r"(?!(la |el |las |los )?(oficina|sede|sucursal|banco|entidad|empresa|atencion|credito|microseguro))|"
            r"\b" + _DATO_DE_PERSONA + r"\b.{0,25}\b(de|del) otr[oa]s? clientes?\b|"
            r"\b(base|lista|listado) de clientes\b",
        ),
    )
)


@dataclass(frozen=True)
class EvaluacionEntrada:
    permitido: bool
    categoria: str = ""
    coincidencia: str = ""


def _es_pregunta_de_politica(texto: str) -> bool:
    return bool(_PREGUNTA_DE_POLITICA.search(texto)) and not _RE_ORDEN_DE_ENTREGA.search(texto)


def evaluar_entrada(pregunta: str) -> EvaluacionEntrada:
    for texto in textos_para_reglas(pregunta):
        politica = _es_pregunta_de_politica(texto)
        for categoria, patron in REGLAS_ENTRADA:
            if politica and categoria in _CATEGORIAS_EXENTAS_EN_POLITICA:
                continue
            encontrado = patron.search(texto)
            if encontrado:
                return EvaluacionEntrada(False, categoria, encontrado.group(0))
    return EvaluacionEntrada(True)


# Patrones con forma de credencial/identificador técnico en la salida.
# (patrón, requiere_digito): los códigos tipo "ABC-123" deben tener un dígito para no
# confundirse con siglas; las claves de API y los usuarios admin se bloquean siempre.
PATRONES_SALIDA: tuple[tuple[re.Pattern[str], bool], ...] = (
    (re.compile(r"\b[A-Z]{2,6}(?:-[A-Z0-9]+){1,4}\b"), True),  # p. ej. ABC-1234-XYZ-99, TMP-123456
    (re.compile(r"\badmin_[A-Za-z0-9_]+\b|\b[A-Za-z0-9_]+_admin\b"), False),
    (re.compile(r"\b(sk|key|tok|tkn|api)[-_][A-Za-z0-9]{10,}\b", re.IGNORECASE), False),
)


@dataclass(frozen=True)
class EvaluacionSalida:
    permitido: bool
    motivo: str = ""


def filtrar_salida(texto: str, secretos: frozenset[str] | set[str] = frozenset()) -> EvaluacionSalida:
    texto_min = texto.lower()
    for secreto in secretos:
        if secreto.lower() in texto_min:
            return EvaluacionSalida(False, "valor sensible de documento restringido")
    for patron, requiere_digito in PATRONES_SALIDA:
        for encontrado in patron.finditer(texto):
            if not requiere_digito or any(c.isdigit() for c in encontrado.group(0)):
                return EvaluacionSalida(False, "patrón con forma de credencial")
    return EvaluacionSalida(True)


# ----------------------------------------------------------------------------
# Enmascarado antes de persistir (RF-S13)
# ----------------------------------------------------------------------------

_DATO_OCULTO = "[DATO OCULTO]"
_RE_CORREO = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Número tras una palabra que lo identifica como dato personal: «cédula 1023456789», «CC 1.023.456.789».
_RE_DATO_CON_ETIQUETA = re.compile(
    r"(\b(?:c[eé]dula|c\.?c\.?|documento|identificaci[oó]n|nit|cuenta|tarjeta|celular|tel[eé]fono|m[oó]vil)\b"
    r"(?:\s+(?:de|del|n[uú]mero|no\.?|n°|es|:))*\s*[:#]?\s*)(\d[\d .-]{4,}\d)",
    re.IGNORECASE,
)
_RE_TARJETA = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")
_RE_TOKEN_TECNICO = re.compile(
    r"\b(?=[A-Za-z0-9_-]*[A-Za-z])(?=[A-Za-z0-9_-]*\d)[A-Za-z0-9]+(?:[-_][A-Za-z0-9]+)+\b"
)
_RE_NUMERO_LARGO = re.compile(r"(?<![$\d.])\d[\d .-]{4,}\d")
_MINIMO_DIGITOS = 6
_MINIMO_TOKEN = 8


def _ocultar_si_largo(coincidencia: re.Match[str]) -> str:
    digitos = sum(c.isdigit() for c in coincidencia.group(0))
    return _DATO_OCULTO if digitos >= _MINIMO_DIGITOS else coincidencia.group(0)


def enmascarar(texto: str, secretos: frozenset[str] | set[str] = frozenset(), *, bloqueada: bool = False) -> str:
    """Versión de ``texto`` apta para guardarse en el historial compartido (RF-S13).

    Oculta valores del documento restringido, correos, tokens con forma de credencial, números de
    tarjeta y números que siguen a «cédula», «cuenta», «celular»… Conserva montos («$10.000.000»),
    plazos y nombres de producto. En una consulta bloqueada oculta además cualquier número largo.
    """
    for secreto in sorted(secretos, key=len, reverse=True):
        texto = re.sub(re.escape(secreto), "[OCULTO]", texto, flags=re.IGNORECASE)
    texto = _RE_CORREO.sub("[CORREO OCULTO]", texto)
    texto = _RE_DATO_CON_ETIQUETA.sub(lambda m: m.group(1) + _DATO_OCULTO, texto)
    texto = _RE_TARJETA.sub(_DATO_OCULTO, texto)
    texto = _RE_TOKEN_TECNICO.sub(lambda m: "[OCULTO]" if len(m.group(0)) >= _MINIMO_TOKEN else m.group(0), texto)
    if bloqueada:
        texto = _RE_NUMERO_LARGO.sub(_ocultar_si_largo, texto)
    return texto
