from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from ..config import Configuracion
from ..dominio import (
    ESTADO_BLOQUEADA,
    ESTADO_SIN_INFO,
    Fuente,
    RespuestaGenerada,
    respuesta_bloqueada,
    respuesta_sin_informacion,
)
from ..generacion.extractivo import responder_con_seccion
from ..generacion.llm import ProveedorLLM
from ..herramientas.corpus import Corpus
from ..herramientas.entidades import nombra_entidad
from ..herramientas.recuperacion import IndiceBM25, Resultado
from ..herramientas.semantica import ContextoSemantico, Embebedor, IndiceSemantico
from ..herramientas.texto import RAICES_GENERICAS, raices_unicas
from ..infraestructura.persistencia import RegistroConsulta, RepositorioConsultas, ahora_iso
from ..seguridad.guardrails import (
    CITAS_BLOQUEO,
    ErrorValidacion,
    enmascarar,
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


def _citas_de_bloqueo(corpus: Corpus) -> list[Fuente]:
    citas: list[Fuente] = []
    for archivo, seccion in CITAS_BLOQUEO:
        fragmento = next((f for f in corpus.fragmentos if (f.archivo, f.ruta_seccion) == (archivo, seccion)), None)
        if fragmento is not None:
            citas.append(Fuente(fragmento.documento, fragmento.archivo, fragmento.ruta_seccion, 1.0))
    return citas


def _indice_semantico(corpus: Corpus, embebedor: Embebedor | None) -> IndiceSemantico | None:
    """RF-E7: si el modelo no carga, se sigue con recuperación léxica."""
    if embebedor is None or corpus.vacio:
        return None
    try:
        return IndiceSemantico(corpus.fragmentos, embebedor)
    except Exception as exc:  # noqa: BLE001 - cualquier fallo del modelo degrada a léxico
        log.warning("embeddings no disponibles, se usa recuperación léxica", extra={"error": type(exc).__name__})
        return None


def _raices_de_atributos(corpus: Corpus) -> frozenset[str]:
    """Etiquetas de ficha («Edad máxima», «Periodicidad de pago»): lo que un producto tiene o no tiene."""
    etiquetas = (linea.split(":", 1)[0] for f in corpus.fragmentos for linea in f.lineas if ":" in linea)
    return frozenset().union(*(raices_unicas(etiqueta) for etiqueta in etiquetas))


class Orquestador:
    def __init__(
        self,
        cfg: Configuracion,
        corpus: Corpus,
        repositorio: RepositorioConsultas,
        proveedor_llm: ProveedorLLM | None = None,
        enrutador: Enrutador | None = None,
        embebedor: Embebedor | None = None,
    ) -> None:
        self.cfg = cfg
        self.corpus = corpus
        self.indice = IndiceBM25(corpus.fragmentos)
        self.repositorio = repositorio
        self.proveedor_llm = proveedor_llm  # activo (None = modo sin conexión)
        self._proveedor_configurado = proveedor_llm  # el que una persona configuró en .env
        self.enrutador = enrutador or Enrutador()
        self.entidades = entidades_del_corpus(corpus.fragmentos)
        # Citas del bloqueo resueltas contra el corpus: sin esas secciones, no se citan archivos inexistentes.
        self.fuentes_bloqueo = _citas_de_bloqueo(corpus)
        self.semantico = _indice_semantico(corpus, embebedor)
        self.raices_de_atributos = _raices_de_atributos(corpus)

    def consultar(self, pregunta_cruda: object, contexto: object = None) -> ResultadoConsulta:
        """Lanza ``ErrorValidacion`` si la pregunta o el contexto no son válidos."""
        inicio = time.perf_counter()
        pregunta = validar_pregunta(pregunta_cruda, self.cfg.max_longitud_pregunta)
        anteriores = validar_contexto(contexto, self.cfg.max_longitud_pregunta)

        detalle = agente = motivo_ruta = referente = ""
        entrada = evaluar_entrada(pregunta)
        if not entrada.permitido:
            generada = respuesta_bloqueada(self.fuentes_bloqueo)
            detalle = f"entrada:{entrada.categoria}"
        else:
            # El contexto pasa por el mismo guardrail: una pregunta anterior bloqueable se ignora.
            permitidas = [p for p in anteriores if evaluar_entrada(p).permitido]
            corregida = pregunta if self.corpus.vacio else self.indice.corregir(pregunta)  # «requicitos»
            resolucion = resolver_pregunta(corregida, permitidas, self.entidades)
            referente = resolucion.referente
            if resolucion.sin_referente:  # «¿Y el plazo?» sin saber de qué producto: no adivinar
                generada = respuesta_sin_informacion()
                agente, motivo_ruta = self.enrutador.fuera_de_dominio.nombre, "seguimiento_sin_referente"
            else:
                generada, agente, motivo_ruta = self._delegar(resolucion.pregunta)
            # RF-S8: también las fuentes, porque el extracto llega crudo al frontend y al historial.
            textos = [generada.texto, *(f"{f.documento} {f.seccion} {f.extracto}" for f in generada.fuentes)]
            evaluaciones = (filtrar_salida(texto, self.corpus.secretos) for texto in textos)
            salida = next((evaluacion for evaluacion in evaluaciones if not evaluacion.permitido), None)
            if salida is not None:
                generada = respuesta_bloqueada(self.fuentes_bloqueo)
                detalle = f"salida:{salida.motivo}"

        latencia_ms = int((time.perf_counter() - inicio) * 1000)
        fuentes = [f.a_dict() for f in generada.fuentes]
        registro = RegistroConsulta(
            # RF-S13: el historial es compartido y sin autenticación; se guarda sin datos sensibles.
            pregunta=enmascarar(pregunta, self.corpus.secretos, bloqueada=generada.estado == ESTADO_BLOQUEADA),
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
                "referente": referente,  # nombre del corpus, nunca texto libre
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
        inexistente = not self.corpus.vacio and self.indice.nombra_algo_inexistente(pregunta)
        resultados = [] if self.corpus.vacio or inexistente else self.indice.buscar(pregunta, top_k=self.cfg.top_k)
        similares = self.semantico.similares(pregunta) if self.semantico and not inexistente else []
        semantico = ContextoSemantico(tuple(similares), self.cfg.umbral_semantico, self.cfg.llm_max_fragmentos)
        if not resultados and similares and similares[0].similitud >= self.cfg.umbral_semantico:
            # RF-E3: sin coincidencias léxicas, lo parecido por significado decide el agente.
            resultados = [Resultado(f, 0.0, frozenset(), 0.0) for f in semantico.fragmentos(self.cfg.top_k)]
        ruta = self.enrutador.elegir(resultados, base_vacia=self.corpus.vacio, inexistente=inexistente)
        generada = ruta.agente.responder(
            pregunta,
            resultados,
            umbral_cobertura=self.cfg.umbral_cobertura,
            proveedor_llm=self.proveedor_llm,
            fragmentos=self.corpus.fragmentos,
            semantico=semantico,
        )
        if generada.estado == ESTADO_SIN_INFO and generada.modo == "extractivo" and not inexistente:
            leida = self._leer_seccion(pregunta, semantico)
            if leida is not None:
                return leida
        return generada, ruta.agente.nombre, ruta.motivo

    def _leer_seccion(self, pregunta: str, semantico: ContextoSemantico) -> tuple[RespuestaGenerada, str, str] | None:
        """RF-E4 / ADR-27: sin respuesta léxica, la similitud puede elegir qué sección leer completa."""
        fragmento = semantico.seccion_clara(self.cfg.umbral_lectura_semantica, self.cfg.margen_lectura_semantica)
        if fragmento is None:
            return None
        raices = raices_unicas(pregunta)
        nombradas = [e for e in self.entidades if nombra_entidad(e.raices, raices)]
        if nombradas:
            # Con un producto nombrado, la sección debe ser suya y tener todo lo que se pide de él;
            # si no, mostrar su ficha parecería una respuesta («¿qué edad máxima tiene Negocio Seguro?»).
            pedidos = (raices & self.raices_de_atributos) - RAICES_GENERICAS
            pedidos -= frozenset().union(*(e.raices for e in nombradas))
            propia = any(e.nombre == fragmento.entidad for e in nombradas)
            if not propia or not pedidos <= raices_unicas(fragmento.texto_indexable):
                return None
        ruta = self.enrutador.elegir([Resultado(fragmento, 0.0, frozenset(), 0.0)])
        return responder_con_seccion(fragmento), ruta.agente.nombre, "lectura_semantica"

    def estado_llm(self) -> dict:
        configurado = self._proveedor_configurado
        cuota = configurado.cuota if configurado else None
        return {
            "proveedor": configurado.nombre if configurado else None,
            "modelo": configurado.modelo if configurado else None,
            "activo": self.proveedor_llm is not None,
            "modo": self.proveedor_llm.nombre if self.proveedor_llm else "extractivo",
            "llamadas": configurado.total_llamadas if configurado else 0,
            "cuota": cuota.a_dict() if cuota else None,
        }

    def cerrar(self) -> None:
        if self._proveedor_configurado is not None:
            self._proveedor_configurado.cerrar()

    def cambiar_modo_llm(self, activo: bool) -> dict:
        """Nunca activa un proveedor que una persona no haya configurado en ``.env`` (AGENTS.md §5)."""
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
            "embeddings": "local" if self.semantico else "none",
            "max_longitud_pregunta": self.cfg.max_longitud_pregunta,
        }
