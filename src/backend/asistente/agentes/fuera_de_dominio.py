from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ..dominio import RespuestaGenerada, respuesta_sin_informacion
from ..generacion.llm import ProveedorLLM
from ..herramientas.corpus import Fragmento
from ..herramientas.recuperacion import Resultado
from ..herramientas.semantica import ContextoSemantico


@dataclass(frozen=True)
class AgenteFueraDeDominio:
    nombre: str = "fuera_de_dominio"

    def responder(
        self,
        pregunta: str,
        resultados: list[Resultado],
        *,
        umbral_cobertura: float,
        proveedor_llm: ProveedorLLM | None = None,
        fragmentos: Sequence[Fragmento] = (),
        semantico: ContextoSemantico | None = None,
    ) -> RespuestaGenerada:
        return respuesta_sin_informacion()


AGENTE_FUERA_DE_DOMINIO = AgenteFueraDeDominio()
