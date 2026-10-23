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
    valor tipo tipos clase clases algun buen buena buenas buenos tardes dias noches saludo saludos cordial
    banco sigue siguen seguir quiere quieren sirve sirven servir ayer hoy
    """.split()
)

# Raíces equivalentes para el emparejamiento (pregunta coloquial -> término del documento).
SINONIMOS: dict[str, str] = {
    "cubr": "cobertur",
    "cubren": "cobertur",
    "cuest": "prim",
    "preci": "prim",
    "vale": "prim",
    "valen": "prim",
    "requier": "requisit",
    "necesit": "requisit",
    "pid": "requisit",
    "pide": "requisit",
    "piden": "requisit",
    "exig": "requisit",
    "exigen": "requisit",
    "tiemp": "tiemp",
    # Vocabulario del asesor -> término de los documentos.
    "incluy": "cobertur",  # los microseguros listan sus coberturas como «Incluye:»
    "ampar": "cobertur",
    "carenci": "graci",
    "respald": "garanti",
    "limit": "maxim",
    "tope": "maxim",
    "cost": "prim",  # en microseguros el precio es la «Prima mensual»
    "quej": "pqr",
    "peti": "pqr",
    "hora": "horari",
    "atiend": "aten",
    "pagan": "pago",
    "pagar": "pago",
    "paga": "pago",
    "pagu": "pago",
    "difer": "plaz",
    "entreg": "desembols",
    "tramit": "radic",
    "segur": "microsegur",
    "asegurad": "cobertur",  # «valor asegurado» = cobertura máxima
    "mes": "mensual",  # «cuánto cuesta al mes» ≈ «Prima mensual»; «60 meses» queda como plazo mensual
    "mensualidad": "prim",
    "millon": "mont",  # «¿puedo pedir 100 millones?» pregunta por el monto
    "papel": "requisit",  # «¿qué papeles necesito?»
    "doming": "horari",
    "festiv": "horari",
    "feriad": "horari",
    "ver": "consult",  # «¿quién puede ver los datos?» ≈ «podrá ser consultada»
    "consultad": "consult",
}

# Palabras de categoría: no cuentan como atributo pedido ni como desconocidas, y no se corrigen.
RAICES_GENERICAS = frozenset(
    {
        "segur", "microsegur", "credit", "product", "servici", "poliz",  # categorías
        "paso", "proces", "procedimient", "etap", "fase",  # meta-palabras de procedimientos
        "diferenci", "compar", "versus", "vs", "diferent",  # meta-palabras de comparación
        "client",  # «un cliente quiere…» es el contexto del asesor, no lo que pregunta
    }
)

_RE_TOKEN = re.compile(r"[a-z0-9]+")
# Frases del asesor -> término de los documentos (RF-14). Se aplican igual a preguntas y documentos.
_FRASES_DEL_ASESOR: tuple[tuple[str, str], ...] = (
    (r"\bhasta\s+cuant[oa]s?\b", "maximo"),
    (r"\b(cuant[oa]s?\s+)?(plata|dinero)\s+(me\s+|le\s+|les\s+)?(prestan|presta|dan|financian)\b", "monto"),
    (r"\bcuanto\s+(me\s+|le\s+|les\s+)?(prestan|presta|financian)\b", "monto"),
    (r"\bnecesit\w*\s+(\d[\d.]*\s*)?(millones|millon)\b", "monto"),
    (r"\bcuanto\s+(hay\s+que|tengo\s+que|tiene\s+que|debo|toca|se\s+debe)\s+pag\w*", "cuanto prima"),
    (r"\btiempo\s+(tengo|tiene|hay|dan)?\s*(para\s+)?pagar(lo|la)?\b", "plazo maximo"),
    (r"\b(entreg\w*|recib\w*|dan|consign\w*)\s+(el\s+|la\s+)?(dinero|plata)\b", "desembolso"),
    (r"\btiempo\s+(estimado\s+)?de\s+respuesta\b", "tiempo"),
    (r"\bcada\s+cuanto\b", "periodicidad"),
    (r"\b(hay\s+que\s+|toca\s+)?(pag|cobr)\w*\s+(por\s+)?(la|el)\s+(solicitud|estudio)\b", "costo del estudio"),
    (r"\b(estudio|solicitud)\b(\s+\w+){0,4}?\s+(se\s+)?cobr\w*", "costo del estudio"),
    (r"\b(costo\w*|cuest\w*)\b(\s+\w+){0,3}?\s+solicitud\b", "costo del estudio"),
    (r"\bsolicitud\b(\s+\w+){0,5}?\s+costo\b", "estudio costo"),
    (r"\baprobacion\s+de\s+(una|la)\s+solicitud\b", "aprobacion de un credito"),
    (r"\b(pasos|proceso|etapas)\s+(\w+\s+){0,4}?(aprob\w*|solicit\w*|pedir|tramit\w*)\s+(un\s+|el\s+)?credito\b",
     "pasos solicitud de credito"),
    (r"\b(tener|contratar|tomar|comprar)\s+(tambien|ademas|otro|otra|dos|varios|mas\s+de\s+un)\b", "tener varios"),
    (r"\bactualiz\w*\s+(su|sus|la|los)\s+(informacion|datos)\b", "actualizacion de datos"),
    (r"\bdatos\s+de\s+(los\s+|un\s+|otros\s+)?clientes?\b", "informacion de clientes"),
)
# Comparativos («¿y el más bajo?») -> el atributo que usan los documentos («mínimo»).
_COMPARATIVOS_DEL_ASESOR: tuple[tuple[str, str], ...] = (
    (r"\bmas\s+(bajo|baja|bajos|bajas|pequeno|pequena)\b|\bmenor(es)?\b", "minimo"),
    (r"\bmas\s+(alto|alta|altos|altas|grande|grandes)\b|\bmayor(es)?\b", "maximo"),
    (r"\bmas\s+(largo|larga|largos|largas|extenso|extensa)\b", "maximo"),
    (r"\bmas\s+(corto|corta|cortos|cortas)\b", "minimo"),
    (r"\bmas\s+barat[oa]s?\b", "prima"),
    (r"\bmas\s+car[oa]s?\b", "prima"),
)
_COMPARATIVOS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(patron), reemplazo) for patron, reemplazo in _FRASES_DEL_ASESOR + _COMPARATIVOS_DEL_ASESOR
)
_VOCALES = "aeiou"


def normalizar(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFKD", texto)
    sin_marcas = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return sin_marcas.lower()


def raiz(palabra: str) -> str:
    """Stemmer determinista y aproximado; importa que se aplique igual a documentos y preguntas."""
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


def palabras(texto: str) -> list[str]:
    """Palabras normalizadas en orden, sin quitar stopwords."""
    normalizado = normalizar(texto)
    for patron, reemplazo in _COMPARATIVOS:
        normalizado = patron.sub(reemplazo, normalizado)
    return _RE_TOKEN.findall(normalizado)


def raiz_con_sinonimos(palabra: str) -> str:
    base = raiz(palabra)
    return SINONIMOS.get(base, base)


def tokenizar(texto: str, *, quitar_stopwords: bool = True) -> list[str]:
    salida: list[str] = []
    for token in palabras(texto):
        if len(token) < 2 and not token.isdigit():
            continue
        if quitar_stopwords and token in STOPWORDS:
            continue
        salida.append(raiz_con_sinonimos(token))
    return salida


def raices_unicas(texto: str) -> set[str]:
    return set(tokenizar(texto))
