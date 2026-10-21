"""Servicio de consultas: orquesta el flujo completo de una pregunta.

    validar -> guardrail de entrada -> recuperar -> responder -> guardrail de salida -> persistir

Es independiente de HTTP para poder probarlo de forma unitaria.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from .config import Configuracion
from .corpus import Corpus
from .guardrails import evaluar_entrada, filtrar_salida, validar_pregunta
from .llm import ProveedorLLM, responder_con_llm
from .motor import (
    ESTADO_BLOQUEADA,
    RespuestaGenerada,
    responder_extractivo,
    respuesta_bloqueada,
    respuesta_sin_informacion,
)
from .persistencia import RegistroConsulta, RepositorioConsultas, ahora_iso
from .recuperacion import IndiceBM25

log = logging.getLogger("asistente.servicio")


@dataclass
class ResultadoConsulta:
    id: int
    pregunta: str
    respuesta: str
    fuentes: list[dict]
    estado: str
    fecha_hora: str
    latencia_ms: int
    modo: str
    detalle_seguridad: str = field(default="", repr=False)

    def a_dict(self) -> dict:
        return {
            "id": self.id,
            "respuesta": self.respuesta,
            "fuentes": self.fuentes,
            "estado": self.estado,
            "fecha_hora": self.fecha_hora,
            "latencia_ms": self.latencia_ms,
            "modo": self.modo,
        }


class ServicioConsultas:
    def __init__(
        self,
        cfg: Configuracion,
        corpus: Corpus,
        repositorio: RepositorioConsultas,
        proveedor_llm: ProveedorLLM | None = None,
    ) -> None:
        self.cfg = cfg
        self.corpus = corpus
        self.indice = IndiceBM25(corpus.fragmentos)
        self.repositorio = repositorio
        self.proveedor_llm = proveedor_llm

    def consultar(self, pregunta_cruda: object) -> ResultadoConsulta:
        """Atiende una pregunta. Lanza ``ErrorValidacion`` si la entrada no es válida."""
        inicio = time.perf_counter()
        pregunta = validar_pregunta(pregunta_cruda, self.cfg.max_longitud_pregunta)

        detalle = ""
        entrada = evaluar_entrada(pregunta)
        if not entrada.permitido:
            generada = respuesta_bloqueada()
            detalle = f"entrada:{entrada.categoria}"
        else:
            generada = self._generar(pregunta)
            salida = filtrar_salida(generada.texto, self.corpus.secretos)
            if not salida.permitido:
                generada = respuesta_bloqueada()
                detalle = f"salida:{salida.motivo}"

        latencia_ms = int((time.perf_counter() - inicio) * 1000)
        fuentes = [f.a_dict() for f in generada.fuentes]
        registro = RegistroConsulta(
            pregunta=pregunta,
            respuesta=generada.texto,
            fuentes=fuentes,
            estado=generada.estado,
            latencia_ms=latencia_ms,
            modo=generada.modo,
            fecha_hora=ahora_iso(),
        )
        id_consulta = self.repositorio.guardar(registro)
        log.info(
            "consulta atendida",
            extra={
                "id": id_consulta,
                "estado": generada.estado,
                "modo": generada.modo,
                "latencia_ms": latencia_ms,
                "n_fuentes": len(fuentes),
                "seguridad": detalle,
                "longitud_pregunta": len(pregunta),
            },
        )
        return ResultadoConsulta(
            id=id_consulta,
            pregunta=pregunta,
            respuesta=generada.texto,
            fuentes=fuentes,
            estado=generada.estado,
            fecha_hora=registro.fecha_hora,
            latencia_ms=latencia_ms,
            modo=generada.modo,
            detalle_seguridad=detalle,
        )

    def _generar(self, pregunta: str) -> RespuestaGenerada:
        if self.corpus.vacio:
            return respuesta_sin_informacion()
        resultados = self.indice.buscar(pregunta, top_k=self.cfg.top_k)
        if not resultados:
            return respuesta_sin_informacion()
        if self.proveedor_llm is not None:
            generada = responder_con_llm(pregunta, resultados, self.proveedor_llm)
            if generada is not None:
                return generada
        return responder_extractivo(pregunta, resultados, self.cfg.umbral_cobertura)

    def estado_sistema(self) -> dict:
        return {
            "documentos": len(self.corpus.documentos),
            "fragmentos": len(self.corpus.fragmentos),
            "documentos_excluidos": len(self.corpus.excluidos),
            "documentos_duplicados": len(self.corpus.duplicados),
            "advertencias": list(self.corpus.advertencias),
            "modo": self.proveedor_llm.nombre if self.proveedor_llm else "extractivo",
        }


__all__ = ["ServicioConsultas", "ResultadoConsulta", "ESTADO_BLOQUEADA"]
