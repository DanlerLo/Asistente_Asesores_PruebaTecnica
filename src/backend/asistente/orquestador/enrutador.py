from __future__ import annotations

from dataclasses import dataclass

from ..agentes import (
    AGENTE_CREDITO,
    AGENTE_FUERA_DE_DOMINIO,
    AGENTE_MICROSEGUROS,
    AGENTE_OPERATIVO,
    Agente,
    AgenteDocumental,
)
from ..herramientas.recuperacion import Resultado

# Registro de especialistas: agregar un agente de dominio es agregar una línea aquí.
ESPECIALISTAS: tuple[AgenteDocumental, ...] = (AGENTE_CREDITO, AGENTE_MICROSEGUROS, AGENTE_OPERATIVO)


@dataclass(frozen=True)
class Ruta:
    agente: Agente
    motivo: str


class Enrutador:
    def __init__(
        self,
        especialistas: tuple[AgenteDocumental, ...] = ESPECIALISTAS,
        por_defecto: Agente = AGENTE_OPERATIVO,
        fuera_de_dominio: Agente = AGENTE_FUERA_DE_DOMINIO,
    ) -> None:
        self.especialistas = especialistas
        self.por_defecto = por_defecto
        self.fuera_de_dominio = fuera_de_dominio

    @property
    def agentes(self) -> list[str]:
        nombres = [a.nombre for a in (*self.especialistas, self.por_defecto, self.fuera_de_dominio)]
        return list(dict.fromkeys(nombres))

    def elegir(self, resultados: list[Resultado], base_vacia: bool = False, inexistente: bool = False) -> Ruta:
        if base_vacia:
            return Ruta(self.fuera_de_dominio, "base_vacia")
        if inexistente:
            return Ruta(self.fuera_de_dominio, "inexistente")
        if not resultados:
            return Ruta(self.fuera_de_dominio, "sin_fragmentos")
        archivo = resultados[0].fragmento.archivo
        for agente in self.especialistas:
            if agente.atiende(archivo):
                return Ruta(agente, f"documento:{archivo}")
        return Ruta(self.por_defecto, f"por_defecto:{archivo}")
