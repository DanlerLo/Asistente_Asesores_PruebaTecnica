from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ..herramientas.corpus import Corpus, cargar_corpus
from ..herramientas.texto import normalizar

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
        # RF-S11: paráfrasis dirigidas al asistente («Nota para el asistente: …», «Haz caso omiso de …»).
        r"\b(nota|instruccion|instrucciones|mensaje)\s+(para|al)\s+(el\s+|la\s+)?"
        r"(asistente|modelo|ia|bot|chatbot|agente)\b",
        r"\b(haz|has|hacer|hagan?)\s+caso\s+omiso\b",
        r"^(asistente|modelo|ia|bot|chatbot|agente)\s*:",
        r"\b(ignore|disregard)\s+(all\s+)?(previous|prior|above|earlier)\b",
    )
)
_RE_MARCA = re.compile(r"clasificacion\s*:\s*(confidencial|reservad[oa]|restringid[oa]|secret[oa])")
_RE_MENCION = re.compile(r"informacion\s+restringida")
_LINEAS_CABECERA = 10
# Etiqueta de credencial al inicio de la línea; el valor va detrás de «:» o en la línea siguiente.
_RE_ETIQUETA_CREDENCIAL = re.compile(
    r"^\W*(token|contrasena|password|api\s*key|clave\s+de\s+acceso|usuario\s+administrador|secreto)\b"
    r"[^:]{0,30}:\s*(.*)$"
)
_RE_SECRETO = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-]{4,}")


def es_instruccion_sospechosa(linea: str) -> bool:
    texto = normalizar(linea)
    return any(p.search(texto) for p in PATRONES_INYECCION)


def _es_valor_tecnico(valor: str) -> bool:
    """Un solo token de 6+ caracteres con dígitos, «-» o «_», no una frase."""
    valor = valor.strip().strip(".")
    return (
        bool(valor)
        and " " not in valor
        and len(valor) >= 6
        and any(c.isdigit() or c in "-_" for c in valor)
    )


def _tiene_credenciales(texto_normalizado: str) -> bool:
    lineas = [linea.strip() for linea in texto_normalizado.splitlines() if linea.strip()]
    for i, linea in enumerate(lineas):
        coincidencia = _RE_ETIQUETA_CREDENCIAL.match(linea)
        if not coincidencia:
            continue
        valor = coincidencia.group(2) or (lineas[i + 1] if i + 1 < len(lineas) else "")
        if _es_valor_tecnico(valor):
            return True
    return False


def motivo_restriccion(nombre: str, texto: str, archivos_restringidos: tuple[str, ...]) -> str | None:
    """Por qué un archivo no debe indexarse, o ``None`` si es público (RF-S12)."""
    nombre_norm = normalizar(nombre)
    if any(nombre_norm == normalizar(r) for r in archivos_restringidos):
        return "nombre en ARCHIVOS_RESTRINGIDOS"
    normalizado = normalizar(texto)
    if _RE_MARCA.search(normalizado):
        return "marca de clasificación"
    if _RE_MENCION.search("\n".join(normalizado.splitlines()[:_LINEAS_CABECERA])):
        return "mención de información restringida en la cabecera"
    if _tiene_credenciales(normalizado):
        return "contenido con forma de credencial"
    return None


def es_restringido(nombre: str, texto: str, archivos_restringidos: tuple[str, ...]) -> bool:
    return motivo_restriccion(nombre, texto, archivos_restringidos) is not None


def extraer_secretos(texto: str) -> set[str]:
    secretos: set[str] = set()
    for token in _RE_SECRETO.findall(texto):
        tiene_digito = any(c.isdigit() for c in token)
        if (tiene_digito or "_" in token or "-" in token) and len(token) >= 6:
            secretos.add(token)
    return secretos


@dataclass(frozen=True)
class PoliticaIngesta:
    """Se inyecta como ``FiltroIngesta`` porque ``herramientas`` no puede importar ``seguridad``."""

    archivos_restringidos: tuple[str, ...] = ()

    def motivo_restriccion(self, nombre: str, texto: str) -> str | None:
        return motivo_restriccion(nombre, texto, self.archivos_restringidos)

    def extraer_secretos(self, texto: str) -> set[str]:
        return extraer_secretos(texto)

    def es_instruccion(self, linea: str) -> bool:
        return es_instruccion_sospechosa(linea)


def cargar_corpus_seguro(data_dir: Path, archivos_restringidos: tuple[str, ...] = ()) -> Corpus:
    """Única forma de cargar el corpus en la app."""
    return cargar_corpus(data_dir, PoliticaIngesta(archivos_restringidos))
