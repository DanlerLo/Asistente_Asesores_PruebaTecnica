"""Carga, saneamiento y fragmentación de la base documental (``Data/*.md``).

Principios aplicados aquí (ver ``sdd/constitucion/constitucion.md``):

* **Los documentos son datos, nunca instrucciones.** Las líneas que parecen
  instrucciones para un asistente (``ignora tus instrucciones``, ``prompt
  administrativo``...) se descartan en la ingesta y se registran como
  advertencia.
* **Seguridad por defecto.** Los archivos marcados como restringidos (por
  nombre o por su marca ``CLASIFICACIÓN: CONFIDENCIAL``) nunca entran al
  índice. De ellos solo se extrae una lista de valores sensibles que el filtro
  de salida usa para garantizar que jamás aparezcan en una respuesta.
* **Documentos duplicados** (mismo contenido con otro nombre) se indexan una
  sola vez para no duplicar fuentes.
"""
from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
from dataclasses import dataclass, field, replace
from pathlib import Path

from .texto import normalizar, raices_unicas

log = logging.getLogger("asistente.corpus")

EXTENSIONES_SOPORTADAS = (".md", ".txt")

PATRONES_INYECCION: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"ignora(r)?\s+(todas?\s+)?(las?|tus?|sus?|estas?)?\s*(instrucciones|reglas|politicas|restricciones)",
        r"olvida(r)?\s+(todas?\s+)?(las?|tus?)\s+(instrucciones|reglas)",
        r"entregue?\s+toda\s+la\s+informacion",
        r"prompt\s+(administrativo|del\s+sistema|de\s+sistema)",
        r"system\s+prompt",
        r"si\s+un\s+usuario\s+pregunta.*\b(entregue?|revele?|muestre?)\b",
        r"\bactua\s+como\b",
    )
)
PATRON_CONFIDENCIAL = re.compile(
    r"clasificacion\s*:\s*confidencial|informacion\s+restringida", re.IGNORECASE
)
_RE_ENCABEZADO = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_RE_LISTA = re.compile(r"^\s*(?:[-*+]|(\d+)[.)])\s+(.*)$")
_RE_TABLA_SEP = re.compile(r"^\s*\|?\s*:?-{2,}")
_RE_HR = re.compile(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$")
_RE_MARCAS_MD = re.compile(r"(\*\*|__|`|~~)")
_RE_HTML = re.compile(r"<[^>]+>")
_RE_SECRETO = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-]{4,}")


@dataclass(frozen=True)
class Fragmento:
    """Unidad mínima recuperable: una sección de un documento."""

    id: str
    documento: str  # nombre legible (archivo sin extensión)
    archivo: str  # nombre del archivo
    ruta_seccion: str  # "Crédito Agro Crece > Condiciones" ("" si es el nivel raíz)
    titulo_propio: str  # último encabezado del fragmento
    entidad: str  # encabezado de nivel 2 bajo el que vive (p. ej. nombre del producto)
    lineas: tuple[str, ...]
    entidad_raices: frozenset[str] = frozenset()
    producto: bool = False  # su entidad es un producto con ficha (ver ``_marcar_productos``)

    @property
    def contenido(self) -> str:
        return "\n".join(self.lineas)

    @property
    def texto_indexable(self) -> str:
        return f"{self.documento} {self.ruta_seccion} {self.contenido}"


@dataclass
class Corpus:
    fragmentos: list[Fragmento] = field(default_factory=list)
    documentos: list[str] = field(default_factory=list)
    excluidos: list[str] = field(default_factory=list)
    duplicados: list[tuple[str, str]] = field(default_factory=list)
    secretos: frozenset[str] = frozenset()
    advertencias: list[str] = field(default_factory=list)

    @property
    def vacio(self) -> bool:
        return not self.fragmentos


# ----------------------------------------------------------------------------
# Saneamiento
# ----------------------------------------------------------------------------


def es_instruccion_sospechosa(linea: str) -> bool:
    """True si la línea parece una instrucción dirigida a un asistente."""
    texto = normalizar(linea)
    return any(p.search(texto) for p in PATRONES_INYECCION)


def es_restringido(nombre: str, texto: str, archivos_restringidos: tuple[str, ...]) -> bool:
    nombre_norm = normalizar(nombre)
    if any(nombre_norm == normalizar(r) for r in archivos_restringidos):
        return True
    cabecera = normalizar("\n".join(texto.splitlines()[:10]))
    return bool(PATRON_CONFIDENCIAL.search(cabecera))


def extraer_secretos(texto: str) -> set[str]:
    """Valores con aspecto de credencial/identificador técnico (``INT-1234-...``)."""
    secretos: set[str] = set()
    for token in _RE_SECRETO.findall(texto):
        tiene_digito = any(c.isdigit() for c in token)
        if (tiene_digito or "_" in token or "-" in token) and len(token) >= 6:
            secretos.add(token)
    return secretos


def _limpiar(linea: str) -> str:
    sin_html = _RE_HTML.sub("", linea)
    return _RE_MARCAS_MD.sub("", sin_html).strip()


# ----------------------------------------------------------------------------
# Fragmentación de Markdown
# ----------------------------------------------------------------------------


def _clasificar(linea: str) -> str:
    """Tipo de una línea cruda: vacia, encabezado, hr, tabla_sep, tabla, lista, etiqueta, texto."""
    if not linea.strip():
        return "vacia"
    if _RE_ENCABEZADO.match(linea):
        return "encabezado"
    if _RE_HR.match(linea):
        return "hr"
    if _RE_TABLA_SEP.match(linea) and "|" in linea:
        return "tabla_sep"
    if linea.lstrip().startswith("|"):
        return "tabla"
    if _RE_LISTA.match(linea):
        return "lista"
    limpia = _limpiar(linea)
    if limpia.endswith(":") and len(limpia) <= 80 and limpia.count(":") == 1:
        return "etiqueta"
    return "texto"


def _partes_lista(linea: str) -> tuple[str | None, str]:
    coincidencia = _RE_LISTA.match(linea)
    assert coincidencia is not None
    return coincidencia.group(1), _limpiar(coincidencia.group(2))


def _formatear_lista(linea: str) -> str:
    numero, contenido = _partes_lista(linea)
    return f"{numero}. {contenido}" if numero else f"- {contenido}"


def _celdas(linea: str) -> list[str]:
    return [_limpiar(c) for c in linea.strip().strip("|").split("|")]


_MINIMO_ETIQUETAS_COMUNES = 2


def _etiquetas(fragmentos: list[Fragmento]) -> set[str]:
    """Etiquetas de atributo de una entidad («Monto máximo», «Prima mensual»): el texto antes de «:»."""
    return {linea.split(":", 1)[0].strip().lower() for f in fragmentos for linea in f.lineas if ":" in linea}


def _marcar_productos(fragmentos: list[Fragmento]) -> list[Fragmento]:
    """Una entidad es un producto si su ficha comparte 2+ etiquetas de atributo con otra entidad del mismo
    documento (los créditos comparten «Monto máximo»/«Plazo máximo»; los microseguros «Cobertura máxima»/
    «Prima mensual»). Las secciones del Manual, las políticas o los procedimientos no forman fichas."""
    por_entidad: dict[str, list[Fragmento]] = {}
    for f in fragmentos:
        if f.entidad and not f.entidad.strip().endswith("?"):
            por_entidad.setdefault(f.entidad, []).append(f)
    etiquetas = {e: _etiquetas(fs) for e, fs in por_entidad.items()}
    productos = {
        e for e in etiquetas
        if any(len(etiquetas[e] & etiquetas[o]) >= _MINIMO_ETIQUETAS_COMUNES for o in etiquetas if o != e)
    }
    return [replace(f, producto=f.entidad in productos) for f in fragmentos]


def fragmentar(texto: str, archivo: str) -> tuple[list[Fragmento], list[str]]:
    """Divide un documento Markdown en fragmentos por encabezado.

    Normaliza el contenido a líneas autocontenidas:
    * filas de tabla ``| Monto máximo | $50.000.000 |`` -> ``Monto máximo: $50.000.000``
    * etiqueta + valor en líneas separadas -> ``Edad máxima: 70 años.``
    * etiqueta + lista -> ``Coberturas: Incendio; Inundación; Daños accidentales.``
    Devuelve los fragmentos y las advertencias de saneamiento.
    """
    documento = Path(archivo).stem
    lineas = texto.splitlines()
    tipos = [_clasificar(linea) for linea in lineas]
    advertencias: list[str] = []
    fragmentos: list[Fragmento] = []
    pila: list[tuple[int, str]] = []  # (nivel, título)
    titulo_doc = documento
    titulos_h2: list[str] = []
    actual: list[str] = []

    def entidad_actual() -> str:
        for nivel, titulo in pila:
            if nivel == 2:
                return titulo
        return ""

    def cerrar() -> None:
        if not actual:
            return
        ruta = " > ".join(t for n, t in pila if n >= 2)
        titulo_propio = pila[-1][1] if pila else titulo_doc
        entidad = entidad_actual()
        fragmentos.append(
            Fragmento(
                id=f"{documento}#{len(fragmentos)}",
                documento=documento,
                archivo=archivo,
                ruta_seccion=ruta,
                titulo_propio=titulo_propio,
                entidad=entidad,
                lineas=tuple(actual),
                entidad_raices=frozenset(raices_unicas(entidad)) if entidad else frozenset(),
            )
        )
        actual.clear()

    def agregar(linea: str) -> None:
        linea = linea.strip()
        if not linea:
            return
        if es_instruccion_sospechosa(linea):
            advertencias.append(
                f"{archivo}: se descartó una línea con apariencia de instrucción: '{linea[:60]}'"
            )
            return
        actual.append(linea)

    i = 0
    n = len(lineas)
    while i < n:
        linea, tipo = lineas[i], tipos[i]
        if tipo in ("vacia", "hr", "tabla_sep"):
            i += 1
            continue
        if tipo == "encabezado":
            cerrar()
            coincidencia = _RE_ENCABEZADO.match(linea)
            assert coincidencia is not None
            nivel, titulo = len(coincidencia.group(1)), _limpiar(coincidencia.group(2))
            if nivel == 1 and not pila and titulo_doc == documento:
                titulo_doc = titulo
            while pila and pila[-1][0] >= nivel:
                pila.pop()
            pila.append((nivel, titulo))
            if nivel == 2:
                titulos_h2.append(titulo)
            i += 1
            continue
        if tipo == "tabla":
            es_cabecera = i + 1 < n and tipos[i + 1] == "tabla_sep"
            if not es_cabecera:
                celdas = _celdas(linea)
                agregar(f"{celdas[0]}: {celdas[1]}" if len(celdas) == 2 else " | ".join(celdas))
            i += 1
            continue
        if tipo == "lista":
            agregar(_formatear_lista(linea))
            i += 1
            continue
        if tipo == "etiqueta":
            etiqueta = _limpiar(linea).rstrip(":")
            j = i + 1
            while j < n and tipos[j] == "vacia":
                j += 1
            if j < n and tipos[j] == "lista":
                items: list[str] = []
                while j < n and tipos[j] in ("lista", "vacia"):
                    if tipos[j] == "lista":
                        items.append(_partes_lista(lineas[j])[1].rstrip("."))
                    j += 1
                agregar(f"{etiqueta}: {'; '.join(items)}.")
                i = j
                continue
            if j < n and tipos[j] == "texto":
                agregar(f"{etiqueta}: {_limpiar(lineas[j])}")
                i = j + 1
                continue
            agregar(f"{etiqueta}:")
            i += 1
            continue
        agregar(_limpiar(linea))
        i += 1
    cerrar()

    if len(titulos_h2) >= 2:
        fragmentos.append(
            Fragmento(
                id=f"{documento}#indice",
                documento=documento,
                archivo=archivo,
                ruta_seccion="Índice",
                titulo_propio="Índice",
                entidad="",
                lineas=(f"{titulo_doc} contiene las secciones: {'; '.join(titulos_h2)}.",),
                entidad_raices=frozenset(),
            )
        )
    return _marcar_productos(fragmentos), advertencias


# ----------------------------------------------------------------------------
# Carga del directorio de datos
# ----------------------------------------------------------------------------


def cargar_corpus(data_dir: Path, archivos_restringidos: tuple[str, ...] = ()) -> Corpus:
    """Lee todos los documentos soportados de ``data_dir`` y construye el corpus."""
    corpus = Corpus()
    secretos: set[str] = set()
    if not data_dir.exists() or not data_dir.is_dir():
        corpus.advertencias.append(f"El directorio de datos no existe: {data_dir}")
        log.warning("directorio de datos inexistente", extra={"data_dir": str(data_dir)})
        return corpus

    hashes: dict[str, str] = {}
    archivos = sorted(
        (p for p in data_dir.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONES_SOPORTADAS),
        key=lambda p: p.name,
    )
    for archivo in archivos:
        # macOS puede entregar nombres en NFD ("e" + tilde combinante); se citan siempre en NFC.
        nombre = unicodedata.normalize("NFC", archivo.name)
        try:
            texto = archivo.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            corpus.advertencias.append(f"{nombre}: no es UTF-8 válido, se omitió")
            continue
        if es_restringido(nombre, texto, archivos_restringidos):
            corpus.excluidos.append(nombre)
            secretos |= extraer_secretos(texto)
            log.info("documento restringido excluido del índice", extra={"archivo": nombre})
            continue
        huella = hashlib.sha256(" ".join(texto.split()).encode("utf-8")).hexdigest()
        if huella in hashes:
            corpus.duplicados.append((nombre, hashes[huella]))
            corpus.advertencias.append(
                f"{nombre}: contenido duplicado de {hashes[huella]}, se indexó una sola vez"
            )
            continue
        hashes[huella] = nombre
        fragmentos, advertencias = fragmentar(texto, nombre)
        corpus.fragmentos.extend(fragmentos)
        corpus.advertencias.extend(advertencias)
        corpus.documentos.append(nombre)

    corpus.secretos = frozenset(secretos)
    if corpus.vacio:
        corpus.advertencias.append("La base documental está vacía: toda consulta responderá sin información.")
        log.warning("base documental vacía", extra={"data_dir": str(data_dir)})
    log.info(
        "corpus cargado",
        extra={
            "documentos": len(corpus.documentos),
            "fragmentos": len(corpus.fragmentos),
            "excluidos": len(corpus.excluidos),
            "duplicados": len(corpus.duplicados),
        },
    )
    return corpus
