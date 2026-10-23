from __future__ import annotations

import difflib
import math
import re
from collections import Counter
from dataclasses import dataclass

from .corpus import Fragmento
from .entidades import MAX_RAICES_ENTIDAD, es_producto, es_titulo_de_pregunta
from .texto import (
    RAICES_GENERICAS,
    STOPWORDS,
    normalizar,
    palabras,
    raices_unicas,
    raiz,
    raiz_con_sinonimos,
    tokenizar,
)

# RF-13: palabras que introducen el nombre de un producto («crédito hipotecario», «microseguro de mascotas»).
TIPOS_DE_PRODUCTO = frozenset(
    {"credito", "creditos", "seguro", "seguros", "microseguro", "microseguros", "poliza", "polizas",
     "prestamo", "prestamos"}
)
_CONECTORES_DE_NOMBRE = frozenset({"de", "del", "para", "el", "la", "los", "las"})
# «¿Qué crédito financia…?»: tras un interrogativo sigue un verbo, no un nombre.
_INTERROGATIVOS = frozenset({"que", "cual", "cuales"})
# Adjetivos de listado: «¿cuáles son los créditos disponibles?» no nombra un producto.
_ADJETIVOS_DE_LISTADO = frozenset(
    {"disponible", "disponibles", "vigente", "vigentes", "existente", "existentes", "actual", "actuales",
     "nuevo", "nuevos", "ofrecido", "ofrecidos", "principal", "principales", "general", "generales"}
)
# Palabras de categoría: si son lo único conocido, la pregunta pide un listado, no un atributo inexistente.
_CATEGORIAS = frozenset({"credit", "microsegur", "product", "portafoli", "pregunt", "frecuent"})
_LONGITUD_MINIMA_CORRECCION = 5
_SIMILITUD_MINIMA_CORRECCION = 0.84
_RE_PALABRA_ORIGINAL = re.compile(r"\w+")


@dataclass(frozen=True)
class Resultado:
    fragmento: Fragmento
    puntaje: float
    terminos: frozenset[str]  # raíces de la pregunta presentes en el fragmento
    cobertura: float  # proporción de raíces útiles de la pregunta cubiertas por el fragmento
    consulta_util: frozenset[str] = frozenset()  # raíces de la pregunta que existen en el corpus


class IndiceBM25:
    """BM25 propio: el corpus es pequeño y así es determinista y sin dependencias."""

    def __init__(self, fragmentos: list[Fragmento], k1: float = 1.5, b: float = 0.75) -> None:
        self.fragmentos = list(fragmentos)
        self.k1, self.b = k1, b
        self._tf: list[Counter[str]] = [Counter(tokenizar(f.texto_indexable)) for f in self.fragmentos]
        self._dl: list[int] = [sum(c.values()) for c in self._tf]
        self._avgdl: float = (sum(self._dl) / len(self._dl)) if self._dl else 0.0
        df: Counter[str] = Counter()
        for conteo in self._tf:
            df.update(conteo.keys())
        total = len(self.fragmentos)
        self._idf: dict[str, float] = {
            t: math.log(1.0 + (total - n + 0.5) / (n + 0.5)) for t, n in df.items()
        }
        self._vocabulario: list[str] = sorted(
            {p for f in self.fragmentos for p in palabras(f.texto_indexable) if len(p) >= 4 and not p.isdigit()}
        )
        self._raices_documentos: frozenset[str] = frozenset().union(
            *(raices_unicas(f.documento) for f in self.fragmentos)
        )
        self._indices_documento: list[tuple[int, frozenset[str]]] = [
            (i, frozenset(raices_unicas(f.documento)))
            for i, f in enumerate(self.fragmentos)
            if f.ruta_seccion == "Índice"
        ]

    @property
    def vacio(self) -> bool:
        return not self.fragmentos

    def conoce(self, raiz: str) -> bool:
        return raiz in self._idf

    def nombra_algo_inexistente(self, pregunta: str) -> bool:
        """RF-13: la pregunta pide un producto o atributo inexistente («crédito hipotecario»)."""
        secuencia = palabras(pregunta)
        for i, palabra in enumerate(secuencia):
            if palabra not in TIPOS_DE_PRODUCTO or (i > 0 and secuencia[i - 1] in _INTERROGATIVOS):
                continue
            anterior = secuencia[i - 1] if i > 0 else ""
            if anterior and anterior not in STOPWORDS and self.conoce(raiz_con_sinonimos(anterior)):
                continue
            j = i + 1
            while j < len(secuencia) and secuencia[j] in _CONECTORES_DE_NOMBRE:
                j += 1
            # Tras «crédito/seguro…» viene una palabra desconocida: nombra un producto inexistente.
            if j < len(secuencia):
                siguiente = secuencia[j]
                if (
                    len(siguiente) > 1
                    and not siguiente.isdigit()
                    and siguiente not in STOPWORDS
                    and siguiente not in TIPOS_DE_PRODUCTO
                    and siguiente not in _ADJETIVOS_DE_LISTADO
                    and not self.conoce(raiz_con_sinonimos(siguiente))
                ):
                    return True
        # Solo se conoce el nombre de un documento y hay palabras desconocidas: atributo inexistente.
        raices = raices_unicas(pregunta)
        desconocidas = {r for r in raices if not self.conoce(r)}
        conocidas = raices - desconocidas
        return bool(
            desconocidas and conocidas - _CATEGORIAS and conocidas <= self._raices_documentos
        )

    def corregir(self, pregunta: str) -> str:
        """Corrige errores de tipeo contra el vocabulario del corpus («requicitos», «desenbolso»)."""
        def reemplazar(coincidencia: re.Match[str]) -> str:
            original = coincidencia.group(0)
            palabra = normalizar(original)
            if (
                len(palabra) < _LONGITUD_MINIMA_CORRECCION
                or palabra in STOPWORDS
                or raiz(palabra) in RAICES_GENERICAS
                or self.conoce(raiz_con_sinonimos(palabra))
            ):
                return original
            # Longitud ± 1 y sin prefijos: «prestan» no es «presentan» ni «toma» es «tomar».
            candidatas = [
                v for v in self._vocabulario
                if abs(len(v) - len(palabra)) <= 1 and not (v.startswith(palabra) or palabra.startswith(v))
            ]
            parecidas = difflib.get_close_matches(palabra, candidatas, n=1, cutoff=_SIMILITUD_MINIMA_CORRECCION)
            return parecidas[0] if parecidas else original

        return _RE_PALABRA_ORIGINAL.sub(reemplazar, pregunta)

    def _candidatos(self, consulta: set[str]) -> list[int]:
        """Si la pregunta nombra una entidad, quedan fuera los demás productos; los índices nunca compiten."""
        bloqueados: list[int] = []
        normales: list[int] = []
        for i, fragmento in enumerate(self.fragmentos):
            if fragmento.ruta_seccion == "Índice":
                continue
            normales.append(i)
            raices = fragmento.entidad_raices
            # Los títulos de preguntas frecuentes no son productos: no acaparan la búsqueda.
            if not raices or len(raices) > MAX_RAICES_ENTIDAD or es_titulo_de_pregunta(fragmento):
                continue
            coincidencias = len(raices & consulta)
            if coincidencias >= 2 and coincidencias >= len(raices) - 1:
                bloqueados.append(i)
        if not bloqueados:
            return normales
        # RF-04: se excluyen solo los otros productos; secciones generales y procedimientos siguen compitiendo.
        return bloqueados + [i for i in normales if i not in bloqueados and not es_producto(self.fragmentos[i])]

    def buscar(self, pregunta: str, top_k: int = 3) -> list[Resultado]:
        consulta = raices_unicas(pregunta)
        if not consulta or self.vacio:
            return []
        # Las palabras ausentes del corpus (saludos, ruido) no penalizan la cobertura.
        consulta_util = frozenset(t for t in consulta if t in self._idf) or frozenset(consulta)
        resultados: list[Resultado] = []
        for i in self._candidatos(consulta):
            tf, dl = self._tf[i], self._dl[i]
            puntaje = 0.0
            terminos: set[str] = set()
            for termino in consulta:
                frecuencia = tf.get(termino, 0)
                if not frecuencia:
                    continue
                terminos.add(termino)
                norma = frecuencia + self.k1 * (1 - self.b + self.b * dl / self._avgdl)
                puntaje += self._idf[termino] * frecuencia * (self.k1 + 1) / norma
            if puntaje > 0:
                resultados.append(
                    Resultado(
                        fragmento=self.fragmentos[i],
                        puntaje=puntaje,
                        terminos=frozenset(terminos),
                        cobertura=len(terminos) / len(consulta_util),
                        consulta_util=consulta_util,
                    )
                )
        resultados.sort(key=lambda r: (-r.puntaje, r.fragmento.id))
        resultados = self._priorizar_indice(consulta, resultados)
        return resultados[:top_k]

    def _priorizar_indice(self, consulta: set[str], resultados: list[Resultado]) -> list[Resultado]:
        """Si la pregunta solo nombra un documento («¿qué créditos existen?»), su Índice pasa primero."""
        mejor = resultados[0].puntaje if resultados else 1.0
        conocidas = {t for t in consulta if t in self._idf}
        for i, raices_titulo in self._indices_documento:
            if conocidas and conocidas <= raices_titulo:
                fragmento = self.fragmentos[i]
                resto = [r for r in resultados if r.fragmento.id != fragmento.id]
                return [Resultado(fragmento, mejor, frozenset(consulta), 1.0, frozenset(consulta)), *resto]
        return resultados
