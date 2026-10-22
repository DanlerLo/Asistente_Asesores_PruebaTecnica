"""Carga y renderizado de los prompts del LLM desde ``prompts/*.j2`` (Jinja2).

* ``autoescape`` desactivado: los prompts son texto plano, no HTML; escapar
  alteraría montos y símbolos de los fragmentos.
* ``StrictUndefined``: una variable faltante es un error, nunca texto vacío.
* Los valores insertados no se reinterpretan como plantilla, así que un
  ``{{ ... }}`` dentro de un documento llega al modelo como dato literal.
* El filtro ``dato`` impide que un documento o una pregunta cierren el bloque
  de datos (``</fragmentos>``, ``</pregunta>``) o inyecten un fragmento falso:
  elimina los caracteres invisibles de formato (con los que se disfraza una
  etiqueta) y convierte todo ``<`` (y sus variantes Unicode) en ``‹``. El resto
  del texto (montos, ``$``, ``&``, tildes) se conserva tal cual.
"""
from __future__ import annotations

import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

DIRECTORIO_PROMPTS = Path(__file__).parent / "prompts"

# "<" y sus variantes de ancho completo / forma pequeña: ninguna puede abrir una etiqueta.
_MENOR_QUE = str.maketrans({"<": "‹", "\uff1c": "‹", "\ufe64": "‹"})


def neutralizar_delimitadores(valor: object) -> str:
    """Quita caracteres invisibles de formato (categoría Unicode Cf) y neutraliza todo ``<``."""
    visible = "".join(c for c in str(valor) if unicodedata.category(c) != "Cf")
    return visible.translate(_MENOR_QUE)


@lru_cache(maxsize=1)
def _entorno() -> Environment:
    entorno = Environment(
        loader=FileSystemLoader(DIRECTORIO_PROMPTS),
        autoescape=False,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    entorno.filters["dato"] = neutralizar_delimitadores
    return entorno


def renderizar(nombre: str, **variables: Any) -> str:
    """Renderiza ``prompts/<nombre>`` con las variables dadas."""
    return _entorno().get_template(nombre).render(**variables)
