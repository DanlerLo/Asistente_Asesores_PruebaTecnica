from __future__ import annotations

import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

DIRECTORIO_PROMPTS = Path(__file__).parent / "prompts"

# Neutralizar todo «<» impide que un documento cierre el bloque de datos (``</fragmentos>``) del prompt.
_MENOR_QUE = str.maketrans({"<": "‹", "\uff1c": "‹", "\ufe64": "‹"})


def neutralizar_delimitadores(valor: object) -> str:
    """Quita caracteres invisibles (Unicode Cf), con los que se disfraza una etiqueta, y neutraliza ``<``."""
    visible = "".join(c for c in str(valor) if unicodedata.category(c) != "Cf")
    return visible.translate(_MENOR_QUE)


@lru_cache(maxsize=1)
def _entorno() -> Environment:
    entorno = Environment(
        loader=FileSystemLoader(DIRECTORIO_PROMPTS),
        autoescape=False,  # texto plano: escapar alteraría montos y símbolos
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    entorno.filters["dato"] = neutralizar_delimitadores
    return entorno


def renderizar(nombre: str, **variables: Any) -> str:
    return _entorno().get_template(nombre).render(**variables)
