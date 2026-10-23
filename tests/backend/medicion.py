"""Mide el motor: aciertos, respuestas incorrectas, abstenciones y completitud de listas.

Uso, desde la raíz y con el .venv activado: python tests/backend/medicion.py [--embeddings] [--groq] [--detalle]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field, replace
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src" / "backend"))

from asistente.config import Configuracion  # noqa: E402
from asistente.dominio import ESTADO_BLOQUEADA, ESTADO_EXITOSA, ESTADO_SIN_INFO  # noqa: E402
from asistente.herramientas.texto import normalizar, raiz  # noqa: E402

CONJUNTOS = ("robustez.json", "generalizacion.json", "evaluacion.json")


_PALABRAS_FUNCIONALES = frozenset({"a", "al", "de", "del", "el", "la", "las", "los", "en", "y", "o", "un", "una"})


def _raices(texto: str) -> set[str]:
    # Sin quitar palabras con significado: «otros clientes» no es «el cliente».
    return {raiz(p) for p in re.findall(r"\w+", normalizar(texto)) if p not in _PALABRAS_FUNCIONALES}


def contiene(respuesta: str, esperado: str) -> bool:
    """Por raíces, igual para todos los modos: el LLM redacta «validar la documentación» por «validación documental»."""
    return _raices(esperado) <= _raices(respuesta)


def clasificar(caso: dict, estado: str, respuesta: str) -> str:
    """``acierto``, ``incorrecta`` o ``abstencion``. Una lista incompleta cuenta como incorrecta."""
    if caso.get("bloqueada"):
        return "acierto" if estado == ESTADO_BLOQUEADA else "incorrecta"
    if estado == ESTADO_BLOQUEADA:
        return "incorrecta"
    if caso.get("no_bloqueada"):
        return "acierto"
    if any(texto in respuesta for texto in caso.get("no_contiene", [])):
        return "incorrecta"
    if caso.get("sin_informacion"):
        return "acierto" if estado == ESTADO_SIN_INFO else "incorrecta"
    if estado == ESTADO_SIN_INFO:
        return "abstencion"
    completa = all(contiene(respuesta, t) for t in caso["contiene"])
    return "acierto" if estado == ESTADO_EXITOSA and completa else "incorrecta"


def completitud(caso: dict, respuesta: str) -> float | None:
    if not caso.get("lista"):
        return None
    return sum(contiene(respuesta, t) for t in caso["contiene"]) / len(caso["contiene"])


@dataclass
class Medicion:
    aciertos: int = 0
    incorrectas: int = 0
    abstenciones: int = 0
    listas: list[float] = field(default_factory=list)
    fallos: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.aciertos + self.incorrectas + self.abstenciones

    def resumen(self) -> str:
        listas = f" · listas completas {sum(x == 1 for x in self.listas)}/{len(self.listas)}" if self.listas else ""
        return (f"{self.aciertos}/{self.total} aciertos · {self.incorrectas} incorrectas · "
                f"{self.abstenciones} abstenciones{listas}")


def medir(orquestador, casos: list[dict], pausa: float = 0.0) -> Medicion:
    medicion = Medicion()
    for caso in casos:
        time.sleep(pausa)  # el plan gratuito de Groq limita los tokens por minuto
        r = orquestador.consultar(caso["pregunta"], contexto=caso.get("contexto"))
        tipo = clasificar(caso, r.estado, r.respuesta)
        if tipo == "acierto":
            medicion.aciertos += 1
        elif tipo == "incorrecta":
            medicion.incorrectas += 1
            medicion.fallos.append(f"{caso['id']} incorrecta")
        else:
            medicion.abstenciones += 1
            medicion.fallos.append(f"{caso['id']} abstención")
        if (fraccion := completitud(caso, r.respuesta)) is not None:
            medicion.listas.append(fraccion)
    return medicion


def cargar(nombre: str) -> list[dict]:
    return json.loads((Path(__file__).with_name(nombre)).read_text(encoding="utf-8"))["preguntas"]


def main() -> None:
    from asistente.api.app import _embebedor
    from asistente.generacion.llm import construir_proveedor
    from asistente.infraestructura.persistencia import RepositorioConsultas
    from asistente.orquestador import Orquestador
    from asistente.seguridad.ingesta import cargar_corpus_seguro

    parser = argparse.ArgumentParser()
    parser.add_argument("--embeddings", action="store_true", help="usa el modelo local (EMBEDDINGS=local)")
    parser.add_argument("--groq", action="store_true", help="usa Groq con GROQ_API_KEY del entorno")
    parser.add_argument("--detalle", action="store_true", help="lista los casos que fallan")
    parser.add_argument("--conjunto", choices=CONJUNTOS, help="mide solo ese conjunto")
    parser.add_argument("--pausa", type=float, default=0.0, help="segundos entre preguntas (Groq: 15)")
    args = parser.parse_args()

    cfg = Configuracion.desde_entorno()
    cfg = replace(cfg, embeddings="local" if args.embeddings else "none",
                  llm_provider="groq" if args.groq else "none")
    corpus = cargar_corpus_seguro(cfg.data_dir, cfg.archivos_restringidos)
    proveedor = construir_proveedor(cfg)
    orquestador = Orquestador(cfg, corpus, RepositorioConsultas(":memory:"), proveedor, embebedor=_embebedor(cfg))
    for nombre in [args.conjunto] if args.conjunto else CONJUNTOS:
        m = medir(orquestador, cargar(nombre), args.pausa)
        print(f"{nombre:22} {m.resumen()}")
        if args.detalle and m.fallos:
            print("   ", ", ".join(m.fallos))


if __name__ == "__main__":
    main()
