"""Orquestador: conduce el flujo completo de una consulta (RF-O1).

    validar -> guardrail de entrada -> recuperar -> enrutar -> agente responde
            -> guardrail de salida -> persistir

La seguridad no se delega: los guardrails se aplican aquí, antes y después de
cualquier agente. Es independiente de HTTP para poder probarlo de forma unitaria.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from ..config import Configuracion
from ..dominio import RespuestaGenerada, respuesta_bloqueada, respuesta_sin_informacion
from ..generacion.llm import ProveedorLLM
from ..herramientas.corpus import Corpus
from ..herramientas.recuperacion import IndiceBM25
from ..infraestructura.persistencia import RegistroConsulta, RepositorioConsultas, ahora_iso
from ..seguridad.guardrails import (
    ErrorValidacion,
    evaluar_entrada,
    filtrar_salida,
    validar_contexto,
    validar_pregunta,
)
from .contexto import entidades_del_corpus, resolver_pregunta
from .enrutador import Enrutador

log = logging.getLogger("asistente.orquestador")


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
    agente: str = field(default="", repr=False)  # vacío si un guardrail bloqueó la entrada
    motivo_ruta: str = field(default="", repr=False)

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


class Orquestador:
    def __init__(
        self,
        cfg: Configuracion,
        corpus: Corpus,
        repositorio: RepositorioConsultas,
        proveedor_llm: ProveedorLLM | None = None,
        enrutador: Enrutador | None = None,
    ) -> None:
        self.cfg = cfg
        self.corpus = corpus
        self.indice = IndiceBM25(corpus.fragmentos)
        self.repositorio = repositorio
        self.proveedor_llm = proveedor_llm  # activo (None = modo sin conexión)
        self._proveedor_configurado = proveedor_llm  # el que una persona configuró en .env
        self.enrutador = enrutador or Enrutador()
        self.entidades = entidades_del_corpus(corpus.fragmentos)

    def consultar(self, pregunta_cruda: object, contexto: object = None) -> ResultadoConsulta:
        """Atiende una pregunta. Lanza ``ErrorValidacion`` si la entrada o el contexto no son válidos.

        ``contexto``: preguntas anteriores de la conversación (opcional, especificación 006).
        """
        inicio = time.perf_counter()
        pregunta = validar_pregunta(pregunta_cruda, self.cfg.max_longitud_pregunta)
        anteriores = validar_contexto(contexto, self.cfg.max_longitud_pregunta)

        detalle = agente = motivo_ruta = referente = ""
        entrada = evaluar_entrada(pregunta)
        if not entrada.permitido:
            generada = respuesta_bloqueada()
            detalle = f"entrada:{entrada.categoria}"
        else:
            # El contexto pasa por el mismo guardrail: una pregunta anterior bloqueable se ignora.
            permitidas = [p for p in anteriores if evaluar_entrada(p).permitido]
            resolucion = resolver_pregunta(pregunta, permitidas, self.entidades)
            referente = resolucion.referente
            if resolucion.sin_referente:  # «¿Y el plazo?» sin saber de qué producto: no adivinar
                generada = respuesta_sin_informacion()
                agente, motivo_ruta = self.enrutador.fuera_de_dominio.nombre, "seguimiento_sin_referente"
            else:
                generada, agente, motivo_ruta = self._delegar(resolucion.pregunta)
            # RF-S8: también las fuentes; con LLM el texto puede no repetir el dato, pero el extracto lleva el
            # fragmento crudo al frontend y al historial.
            textos = [generada.texto, *(f"{f.documento} {f.seccion} {f.extracto}" for f in generada.fuentes)]
            evaluaciones = (filtrar_salida(texto, self.corpus.secretos) for texto in textos)
            salida = next((evaluacion for evaluacion in evaluaciones if not evaluacion.permitido), None)
            if salida is not None:
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
                "agente": agente,
                "motivo_ruta": motivo_ruta,
                "latencia_ms": latencia_ms,
                "n_fuentes": len(fuentes),
                "seguridad": detalle,
                "referente": referente,  # entidad heredada del contexto (nombre del corpus, nunca texto libre)
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
            agente=agente,
            motivo_ruta=motivo_ruta,
        )

    def _delegar(self, pregunta: str) -> tuple[RespuestaGenerada, str, str]:
        """Recupera evidencia, elige el agente y le delega la respuesta."""
        inexistente = not self.corpus.vacio and self.indice.nombra_algo_inexistente(pregunta)
        resultados = [] if self.corpus.vacio or inexistente else self.indice.buscar(pregunta, top_k=self.cfg.top_k)
        ruta = self.enrutador.elegir(resultados, base_vacia=self.corpus.vacio, inexistente=inexistente)
        generada = ruta.agente.responder(
            pregunta,
            resultados,
            umbral_cobertura=self.cfg.umbral_cobertura,
            proveedor_llm=self.proveedor_llm,
        )
        return generada, ruta.agente.nombre, ruta.motivo

    def estado_llm(self) -> dict:
        """Proveedor configurado, si está activo, llamadas desde el arranque y última cuota conocida."""
        configurado = self._proveedor_configurado
        cuota = getattr(configurado, "cuota", None)
        return {
            "proveedor": configurado.nombre if configurado else None,
            "modelo": getattr(configurado, "modelo", None),
            "activo": self.proveedor_llm is not None,
            "modo": self.proveedor_llm.nombre if self.proveedor_llm else "extractivo",
            "llamadas": getattr(configurado, "total_llamadas", 0),
            "cuota": cuota.a_dict() if cuota else None,
        }

    def cambiar_modo_llm(self, activo: bool) -> dict:
        """Desactiva el LLM (modo sin conexión) o reactiva el proveedor configurado en ``.env``.

        Nunca activa un proveedor que una persona no haya configurado (AGENTS.md §5).
        """
        if activo and self._proveedor_configurado is None:
            raise ErrorValidacion(
                "LLM_NO_CONFIGURADO", "No hay un proveedor LLM configurado (LLM_PROVIDER en .env)."
            )
        self.proveedor_llm = self._proveedor_configurado if activo else None
        log.info("modo LLM cambiado", extra={"activo": activo})
        return self.estado_llm()

    def estado_sistema(self) -> dict:
        return {
            "documentos": len(self.corpus.documentos),
            "fragmentos": len(self.corpus.fragmentos),
            "documentos_excluidos": len(self.corpus.excluidos),
            "documentos_duplicados": len(self.corpus.duplicados),
            "advertencias": list(self.corpus.advertencias),
            "modo": self.proveedor_llm.nombre if self.proveedor_llm else "extractivo",
            "agentes": self.enrutador.agentes,
        }
