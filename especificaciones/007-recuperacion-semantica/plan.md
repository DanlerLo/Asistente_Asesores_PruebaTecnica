# Plan 007 — Recuperación semántica local y más contexto para el LLM

## Arquitectura propuesta
```
pregunta ─► guardrails ─► recuperación híbrida ─────────────► enrutador ─► agente
                          ├─ BM25 (palabras, determinista)        │            │
                          └─ índice semántico (significado)       │            ├─ sin conexión: reglas léxicas → líneas con cita
                             líneas embebidas al arrancar         │            │  (la similitud no elige líneas)
                             en CPU, sin red                      │            └─ con Groq: contexto = BM25 + semántico
                                                                  │               + documento del agente (con tope)
                      si BM25 no encuentra nada y algo se parece ─┘
```
La recuperación es la R del RAG y tiene dos vías: BM25 encuentra lo que usa las palabras de los documentos y el índice semántico lo que dice lo mismo con otras palabras. El modelo se construye en la raíz de composición (`api/app.py`); si no hay modelo, todo funciona solo con BM25.

## Componentes
| Componente | Responsabilidad | Decisiones clave |
|------------|-----------------|------------------|
| `herramientas/semantica.py` | `Embebedor` (Protocol), `EmbebedorLocal` (`fastembed`), `IndiceSemantico` (una entrada por línea, similitud coseno), `ContextoSemantico` y `construir_embebedor` | Importación perezosa de `fastembed`: con `EMBEDDINGS=none` no se carga nada |
| `config.py` | `embeddings`, `embeddings_modelo`, `embeddings_cache`, `umbral_semantico`, `llm_max_fragmentos` | Validados al arrancar |
| `orquestador/orquestador.py` | Búsqueda híbrida y enrutamiento cuando BM25 no encuentra nada | Lo semántico nunca pasa por encima de un bloqueo, un producto inexistente ni un seguimiento sin referente |
| `agentes/base.py` | Contexto ampliado para el LLM | Mitad del tope para lo mejor de BM25, luego lo semántico, el documento del agente y el resto de BM25 |

## Decisiones de arquitectura
- **ADR-23 `fastembed` con un modelo multilingüe pequeño.** Corre en CPU con ONNX (sin PyTorch, ~150 MB de dependencias), descarga el modelo una sola vez (0,22 GB) y queda offline. `sentence-transformers` exige PyTorch (varios GB); un servicio de embeddings exige red y costo. `paraphrase-multilingual-MiniLM-L12-v2` entiende español y embebe las 108 líneas del corpus en menos de 1 s.
- **ADR-24 Embeber líneas, no fragmentos.** Las respuestas del modo extractivo son líneas; comparar la pregunta con cada línea permite responder la línea exacta y citar su sección.
- **ADR-25 La similitud trae evidencia; no elige la respuesta en modo sin conexión.** Se implementó y midió un respaldo que, cuando las reglas léxicas no respondían, devolvía la línea más parecida con umbral y margen. Con las 40 preguntas nuevas:

  | Umbral / margen | Aciertos | Respuestas equivocadas | Evaluación (97) |
  |---|---|---|---|
  | Sin respaldo | 19/40 | 4 | 97/97 |
  | 0,50 / 0,06 | 22/40 | 10 | 95/97 |
  | 0,60 / 0,06 | 21/40 | 8 | 96/97 |
  | 0,70 / 0,06 | 20/40 | 6 | 96/97 |

  Gana 1 a 3 aciertos a cambio de 2 a 6 respuestas equivocadas: el modelo reconoce el tema de una línea, no si la responde. En un banco, un dato equivocado es peor que «no tengo información», así que el respaldo se retiró. La similitud se usa para enrutar y para el contexto del LLM, que sí decide si los fragmentos responden.
- **ADR-26 Más contexto para Groq, con tope.** El corpus es pequeño: los fragmentos del documento del agente caben en el prompt. El tope evita agotar la cuota de tokens del plan gratuito.

## Estrategia de pruebas
| Nivel | Archivo | Cubre |
|-------|---------|-------|
| Unitarias | `tests/backend/test_semantica.py` | índice por líneas sin restringidos, embebedor de prueba determinista, configuración |
| Orquestador | `tests/backend/test_semantica.py` | el extractivo no responde por similitud; nunca rescata bloqueos, inexistentes ni seguimientos; enrutamiento cuando BM25 no encuentra nada; degradación si el modelo falla; contexto ampliado para el LLM |
| Generalización | `tests/backend/generalizacion.json` | 40 preguntas nuevas, escritas antes de la característica y nunca usadas para ajustar; se miden a mano con el modelo real y con Groq (resultados abajo) |
| Regresión | `test_banco.py`, `test_evaluacion.py` | ninguna respuesta empeora; la evaluación sigue en 97/97 |

## Resultados de generalización
Medidos con las 40 preguntas de `generalizacion.json`, que el sistema nunca vio y que no se usan para ajustar reglas. Un acierto exige todas las palabras con contenido del dato esperado (sin mayúsculas, tildes ni espacios especiales), porque el LLM redacta con sus palabras («entre 10 y 15 días» por «10 a 15 días»); las preguntas sin respuesta exigen la frase canónica exacta.

| Configuración | Aciertos | Respuestas equivocadas | «No tengo información» |
|---|---|---|---|
| Sin conexión (BM25 + reglas) | 19/40 (48 %) | 4 | 17 |
| Groq con el contexto anterior (solo BM25) | 33/40 (82 %) | 5 | 2 |
| **Groq + embeddings + contexto ampliado** | **38/40 (95 %)** | **0** | 2 |

Los embeddings y el contexto ampliado eliminan las respuestas equivocadas del modo conexión («¿Cuál de los créditos se puede pagar en más tiempo?» ahora responde *Agro Crece, 84 meses*). Las dos que quedan sin respuesta: «¿Cuánto paga Vida Protegida si el asegurado fallece?» y «¿Cuál microseguro sale más económico?».

## Trazabilidad
| RF | Pruebas |
|----|---------|
| RF-E1 | `test_semantica.py::test_embeddings_desactivados_por_defecto`, `test_configuracion_de_embeddings_invalida` |
| RF-E2 | `test_semantica.py::test_el_indice_tiene_una_entrada_por_linea`, `test_el_indice_no_contiene_lineas_restringidas` |
| RF-E3 | `test_semantica.py::test_sin_resultados_lexicos_enruta_por_similitud`, `test_con_groq_lo_parecido_llega_al_llm` |
| RF-E4 | `test_semantica.py::test_el_modo_extractivo_no_responde_por_similitud` |
| RF-E5 | `test_semantica.py::test_el_llm_recibe_contexto_ampliado_con_tope`, `test_con_groq_lo_parecido_llega_al_llm` |
| RF-E6 | `test_semantica.py::test_la_similitud_no_rescata_bloqueos_ni_inexistentes` |
| RF-E7 | `test_semantica.py::test_si_el_modelo_falla_sigue_con_recuperacion_lexica` |
| RNF-E1 | `requirements.txt` (`fastembed`, sin PyTorch) |
| RNF-E2 | todas las pruebas usan `EmbebedorDePrueba` |
| RNF-E3 | medido: modelo en caché + índice en 1,5 s |
| RNF-E4 | `test_banco.py::test_el_banco_coincide_con_la_foto` (con `EMBEDDINGS=none` no cambia ninguna respuesta) |
