from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from .texto import raices_unicas

_RE_ENCABEZADO = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_RE_LISTA = re.compile(r"^\s*(?:[-*+]|(\d+)[.)])\s+(.*)$")
_RE_TABLA_SEP = re.compile(r"^\s*\|?\s*:?-{2,}")
_RE_HR = re.compile(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$")
_RE_MARCAS_MD = re.compile(r"(\*\*|__|`|~~)")
# Solo etiquetas HTML reales: «< $2.000.000 … >» es un comparador y no debe borrarse.
_RE_HTML = re.compile(r"</?[A-Za-z][A-Za-z0-9-]*(?:\s[^<>]*)?/?>")
_MINIMO_ETIQUETAS_COMUNES = 2


@dataclass(frozen=True)
class Fragmento:
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


# --- Líneas ---


def _limpiar(linea: str) -> str:
    sin_html = _RE_HTML.sub("", linea)
    return _RE_MARCAS_MD.sub("", sin_html).strip()


def _clasificar(linea: str) -> str:
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
    # «Atención en oficinas (8:00 a 17:00):» también es etiqueta: termina en «:» y no es una oración.
    if limpia.endswith(":") and len(limpia) <= 80 and ". " not in limpia:
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


# --- Productos ---


def _etiquetas(fragmentos: list[Fragmento]) -> set[str]:
    """Texto antes de «:» en cada línea («Monto máximo», «Prima mensual»)."""
    return {linea.split(":", 1)[0].strip().lower() for f in fragmentos for linea in f.lineas if ":" in linea}


def _marcar_productos(fragmentos: list[Fragmento]) -> list[Fragmento]:
    """Una entidad es producto si comparte 2+ etiquetas de atributo con otra entidad del documento."""
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


# --- Fragmentación ---


class _Fragmentador:
    """Cada ``_procesar_*`` consume una o más líneas y devuelve el índice de la siguiente."""

    def __init__(self, texto: str, archivo: str, es_instruccion: Callable[[str], bool]) -> None:
        self.archivo = archivo
        self.documento = Path(archivo).stem
        self.lineas = texto.splitlines()
        self.tipos = [_clasificar(linea) for linea in self.lineas]
        self.es_instruccion = es_instruccion
        self.fragmentos: list[Fragmento] = []
        self.advertencias: list[str] = []
        self.pila: list[tuple[int, str]] = []  # (nivel, título) de los encabezados abiertos
        self.titulo_doc = self.documento
        self.titulos_h2: list[str] = []
        self.actual: list[str] = []  # líneas del fragmento en construcción
        self.cabecera: list[str] = []  # celdas de la última cabecera de tabla

    def ejecutar(self) -> tuple[list[Fragmento], list[str]]:
        procesar = {
            "encabezado": self._procesar_encabezado,
            "tabla": self._procesar_tabla,
            "lista": self._procesar_lista,
            "etiqueta": self._procesar_etiqueta,
            "texto": self._procesar_texto,
        }
        i = 0
        while i < len(self.lineas):
            tipo = self.tipos[i]
            i = procesar[tipo](i) if tipo in procesar else i + 1  # vacía, hr y separador de tabla se saltan
        self._cerrar()
        self._agregar_indice()
        return _marcar_productos(self.fragmentos), self.advertencias

    # --- construcción de fragmentos -------------------------------------------------------------------

    def _entidad_actual(self) -> str:
        return next((titulo for nivel, titulo in self.pila if nivel == 2), "")

    def _cerrar(self) -> None:
        if not self.actual:
            return
        entidad = self._entidad_actual()
        self.fragmentos.append(
            Fragmento(
                id=f"{self.documento}#{len(self.fragmentos)}",
                documento=self.documento,
                archivo=self.archivo,
                ruta_seccion=" > ".join(t for n, t in self.pila if n >= 2),
                titulo_propio=self.pila[-1][1] if self.pila else self.titulo_doc,
                entidad=entidad,
                lineas=tuple(self.actual),
                entidad_raices=frozenset(raices_unicas(entidad)) if entidad else frozenset(),
            )
        )
        self.actual.clear()

    def _agregar(self, linea: str, i: int) -> None:
        linea = linea.strip()
        if not linea:
            return
        if self.es_instruccion(linea):
            # RF-S10: nunca el texto: podría tener un valor sensible y sale por /api/salud.
            self.advertencias.append(
                f"{self.archivo}, línea {i + 1}: se descartó una línea con apariencia de instrucción"
            )
            return
        self.actual.append(linea)

    def _agregar_indice(self) -> None:
        if len(self.titulos_h2) < 2:
            return
        self.fragmentos.append(
            Fragmento(
                id=f"{self.documento}#indice",
                documento=self.documento,
                archivo=self.archivo,
                ruta_seccion="Índice",
                titulo_propio="Índice",
                entidad="",
                lineas=(f"{self.titulo_doc} contiene las secciones: {'; '.join(self.titulos_h2)}.",),
                entidad_raices=frozenset(),
            )
        )

    # --- un método por tipo de línea ------------------------------------------------------------------

    def _procesar_encabezado(self, i: int) -> int:
        self._cerrar()
        coincidencia = _RE_ENCABEZADO.match(self.lineas[i])
        assert coincidencia is not None
        nivel, titulo = len(coincidencia.group(1)), _limpiar(coincidencia.group(2))
        if nivel == 1 and not self.pila and self.titulo_doc == self.documento:
            self.titulo_doc = titulo
        while self.pila and self.pila[-1][0] >= nivel:
            self.pila.pop()
        if self.es_instruccion(titulo):
            # RF-S11: un encabezado malicioso viajaría en la cita y en el prompt.
            self.advertencias.append(
                f"{self.archivo}, línea {i + 1}: se reemplazó un encabezado con apariencia de instrucción"
            )
            titulo = "Sección sin título"
        self.pila.append((nivel, titulo))
        if nivel == 2:
            self.titulos_h2.append(titulo)
        return i + 1

    def _procesar_tabla(self, i: int) -> int:
        celdas = _celdas(self.lineas[i])
        if i + 1 < len(self.lineas) and self.tipos[i + 1] == "tabla_sep":
            self.cabecera = celdas
        elif len(celdas) == 2:
            self._agregar(f"{celdas[0]}: {celdas[1]}", i)
        elif len(celdas) > 2 and len(self.cabecera) == len(celdas):
            # Con 3+ columnas la cabecera da el nombre de cada valor: «Impulso: Plazo mínimo: 6 meses; …».
            pares = "; ".join(f"{h}: {v}" for h, v in zip(self.cabecera[1:], celdas[1:], strict=True))
            self._agregar(f"{celdas[0]}: {pares}", i)
        else:
            self._agregar(" | ".join(celdas), i)
        return i + 1

    def _procesar_lista(self, i: int) -> int:
        self._agregar(_formatear_lista(self.lineas[i]), i)
        return i + 1

    def _procesar_etiqueta(self, i: int) -> int:
        """Une una etiqueta («Coberturas:») con la lista o la línea de texto que la sigue."""
        etiqueta = _limpiar(self.lineas[i]).rstrip(":")
        j = i + 1
        while j < len(self.lineas) and self.tipos[j] == "vacia":
            j += 1
        siguiente = self.tipos[j] if j < len(self.lineas) else ""
        if siguiente == "lista":
            items: list[str] = []
            while j < len(self.lineas) and self.tipos[j] in ("lista", "vacia"):
                if self.tipos[j] == "lista":
                    items.append(_partes_lista(self.lineas[j])[1].rstrip("."))
                j += 1
            self._agregar(f"{etiqueta}: {'; '.join(items)}.", i)
            return j
        if siguiente == "texto":
            self._agregar(f"{etiqueta}: {_limpiar(self.lineas[j])}", i)
            return j + 1
        self._agregar(f"{etiqueta}:", i)
        return i + 1

    def _procesar_texto(self, i: int) -> int:
        self._agregar(_limpiar(self.lineas[i]), i)
        return i + 1


def fragmentar(
    texto: str, archivo: str, es_instruccion: Callable[[str], bool]
) -> tuple[list[Fragmento], list[str]]:
    """Un fragmento por encabezado; descarta las líneas que ``es_instruccion`` marca como inyección."""
    return _Fragmentador(texto, archivo, es_instruccion).ejecutar()
