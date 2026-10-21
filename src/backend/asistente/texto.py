"""Normalización de texto en español: tildes, minúsculas, stopwords y raíces.

El objetivo no es un stemmer lingüísticamente perfecto sino uno determinista,
sin dependencias y consistente: se aplica exactamente igual a documentos y a
preguntas, que es lo que importa para el emparejamiento.
"""
from __future__ import annotations

import re
import unicodedata

STOPWORDS: frozenset[str] = frozenset(
    """
    a al algo alguna algunas alguno algunos ante antes aquel aquella aquellas aquello
    aquellos asi aun bajo cada como con contra cual cuales cualquier cuando cuanta cuantas
    cuanto cuantos de del desde donde dos durante e el ella ellas ellos en entre era eran
    es esa esas ese eso esos esta estan estas este esto estos fue fueron ha hace hacen
    hacer hacia han hasta hay la las le les lo los mas me mi mis mucho muy nada ni no nos
    o os otra otras otro otros para pero poco por porque puede pueden puedo que quien
    quienes se sea ser si sin sobre son su sus tal tambien te tener tengo tiene tienen
    todo todos tu tus un una unas uno unos usted ustedes y ya yo
    dime digame cuentame explicame informacion informame indique indica quisiera quiero
    necesito saber sabes favor hola gracias respecto acerca detalle detalles podria
    podrias puedes seria existe existen cuales dan da dar tarda tardan demora demoran
    dice dicen habla hablan contiene contienen trata tratan ofrece ofrecen debe deben debo deberia
    """.split()
)

# Raíces equivalentes para el emparejamiento (pregunta coloquial -> término del documento).
SINONIMOS: dict[str, str] = {
    "cubr": "cobertur",
    "cubren": "cobertur",
    "cuest": "cost",
    "preci": "cost",
    "vale": "cost",
    "valen": "cost",
    "requier": "requisit",
    "necesit": "requisit",
    "pid": "requisit",
    "pide": "requisit",
    "piden": "requisit",
    "exig": "requisit",
    "exigen": "requisit",
    "tiemp": "tiemp",
}

_RE_TOKEN = re.compile(r"[a-z0-9]+")
_VOCALES = "aeiou"


def normalizar(texto: str) -> str:
    """Quita tildes/diacríticos y pasa a minúsculas (``Crédito`` -> ``credito``)."""
    descompuesto = unicodedata.normalize("NFKD", texto)
    sin_marcas = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return sin_marcas.lower()


def raiz(palabra: str) -> str:
    """Raíz aproximada: elimina plurales, sufijos -ción/-sión, terminaciones
    verbales frecuentes y la vocal final de género.

    ``reclamaciones``/``reclamación`` -> ``reclam``, ``clientes`` -> ``client``,
    ``máximo``/``máxima`` -> ``maxim``, ``créditos``/``crédito`` -> ``credit``,
    ``actualizan``/``actualiza``/``actualización`` -> ``actualiz``.
    """
    p = palabra
    if len(p) <= 3:
        return p
    for _ in range(2):  # plural (dos pasadas: "intereses" -> "interes" -> "inter")
        if p.endswith("es") and len(p) > 4 and p[-3] in "nrldzs":
            p = p[:-2]
        elif p.endswith("s") and len(p) > 3:
            p = p[:-1]
        else:
            break
    if len(p) > 7 and p.endswith(("cion", "sion")):
        p = p[:-4]
    if len(p) > 5 and p.endswith(("ar", "er", "ir")):
        p = p[:-2]
    elif len(p) > 6 and p.endswith(("an", "en")):
        p = p[:-2]
    if len(p) > 4 and p[-1] in "aoe":
        p = p[:-1]
    return p


def tokenizar(texto: str, *, quitar_stopwords: bool = True) -> list[str]:
    """Convierte texto en una lista de raíces normalizadas."""
    tokens = _RE_TOKEN.findall(normalizar(texto))
    salida: list[str] = []
    for token in tokens:
        if len(token) < 2 and not token.isdigit():
            continue
        if quitar_stopwords and token in STOPWORDS:
            continue
        base = raiz(token)
        salida.append(SINONIMOS.get(base, base))
    return salida


def raices_unicas(texto: str) -> set[str]:
    """Conjunto de raíces (sin stopwords) de un texto."""
    return set(tokenizar(texto))
