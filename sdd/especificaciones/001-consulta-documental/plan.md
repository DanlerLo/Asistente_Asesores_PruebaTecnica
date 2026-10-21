# Plan 001 — Consulta documental con citación de fuentes

## Arquitectura propuesta

```
            ┌──────────────────────────── src/backend/asistente ────────────────────────────┐
HTTP        │ main.py (FastAPI)                                                               │
POST        │   └─► servicio.py ─► guardrails.validar_pregunta  (RF-06)                      │
/api/       │         │           guardrails.evaluar_entrada     (002)                       │
consultar   │         ├─► recuperacion.IndiceBM25.buscar          (RF-02..04)                │
            │         │       └─ corpus.Corpus (Data/*.md → Fragmento[])                     │
            │         ├─► motor.responder_extractivo  ──o── llm.responder_con_llm (RF-11)    │
            │         ├─► guardrails.filtrar_salida           (002)                           │
            │         └─► persistencia.RepositorioConsultas  (RF-09) ──► SQLite               │
            └───────────────────────────────────────────────────────────────────────────────┘
```

Flujo de una consulta: **validar → guardrail de entrada → recuperar → responder → guardrail de salida → persistir**. El servicio (`ServicioConsultas`) es independiente de HTTP para permitir pruebas unitarias sin levantar el servidor.

## Componentes
| Componente | Responsabilidad | Decisiones clave |
|------------|-----------------|------------------|
| `config.py` | Configuración inmutable desde variables de entorno | Valores por defecto seguros: sin LLM, `Data/`, SQLite en `storage/` |
| `texto.py` | Normalización en español: tildes, stopwords, raíces, sinónimos | Stemmer propio determinista (sin NLTK/spaCy) aplicado igual a documentos y preguntas |
| `corpus.py` | Carga, exclusión de restringidos, deduplicación, fragmentación por encabezados | Tablas → `clave: valor`; etiqueta + lista → una línea; fragmento «Índice» por documento |
| `recuperacion.py` | BM25 propio + bloqueo por entidad + priorización del índice | Cobertura calculada sobre términos que existen en el corpus |
| `motor.py` | Respuesta extractiva: elige las líneas que responden; compone texto con cita | Reglas explícitas y probadas (ver docstring de `seleccionar_lineas`) |
| `llm.py` | Proveedor LLM opcional detrás de la interfaz `ProveedorLLM` | Prompt cerrado a fragmentos; temperatura 0; fallback al extractivo |
| `persistencia.py` | SQLite vía `sqlite3` estándar | Tabla `consultas` con `CHECK` de estado, índices por fecha y estado |
| `main.py` | API, CORS, manejo de errores, request-id | Fábrica `crear_app()` para pruebas |
| `observabilidad.py` | Logs JSON | Un evento por consulta con estado/modo/latencia |

## Decisiones de arquitectura (ADR resumidos)
- **ADR-1 Recuperación léxica en lugar de embeddings.** El corpus es pequeño, en español y con vocabulario controlado; BM25 es determinista, explicable y no requiere modelos ni red. Evolución a RAG vectorial descrita en `docs/Cuestionario.md`.
- **ADR-2 Respuesta extractiva por defecto.** Garantiza por construcción "responder únicamente con información encontrada"; un LLM es opcional para redacción.
- **ADR-3 SQLite.** Cero configuración, archivo local, suficiente para el volumen de la prueba; el repositorio aísla el cambio futuro a PostgreSQL.
- **ADR-4 Sin frameworks adicionales** (ORM, rank_bm25, NLTK): menos superficie de ataque y de dependencia; el código propio está cubierto por pruebas.
- **ADR-5 Límite de 1000 caracteres por pregunta** (configurable): protege latencia y costo del LLM y cubre preguntas reales de un asesor.

## Estrategia de pruebas
| Nivel | Archivo | Cubre |
|-------|---------|-------|
| Unitarias de texto/corpus | `tests/backend/test_corpus.py` | normalización, stemming, tablas/etiquetas/listas, índice, exclusión de restringidos, duplicados, base vacía |
| Unitarias de recuperación/motor | `tests/backend/test_motor.py` | ranking, bloqueo por entidad, respuestas esperadas, frase canónica, comparación de productos |
| Servicio (flujo completo) | `tests/backend/test_servicio.py` | estados, persistencia, caracteres especiales, consulta extensa, duplicados, LLM falso y fallback |
| Contrato HTTP | `tests/backend/test_api.py` | códigos, cuerpos de error, historial, estadísticas, salud |

Ejecución: `python -m pytest` desde la raíz (sin red, < 1 s). Ciclo TDD: escribir el escenario Gherkin → prueba roja → implementar → verde → refactorizar.

## Trazabilidad
| RF | Pruebas |
|----|---------|
| RF-01 | `test_api.py::test_consulta_valida` |
| RF-02 | `test_corpus.py::test_fragmentar_convierte_tablas_etiquetas_y_listas`, `test_fragmentar_crea_indice_del_documento` |
| RF-03 | `test_motor.py::test_responde_con_la_linea_correcta_y_cita_la_fuente` |
| RF-04 | `test_motor.py::test_bm25_bloqueo_por_entidad...`, `test_no_responde_con_datos_de_otro_producto` |
| RF-05 | `test_motor.py::test_sin_evidencia_responde_la_frase_canonica`, `test_api.py::test_consulta_sin_informacion` |
| RF-06 | `test_guardrails.py` (validación), `test_api.py::test_pregunta_vacia/test_cuerpo_invalido/test_pregunta_demasiado_larga/test_caracteres_especiales` |
| RF-07 | `test_corpus.py::test_documentos_duplicados_se_indexan_una_sola_vez`, `test_servicio.py::test_documentos_duplicados_no_duplican_fuentes` |
| RF-08 | `test_corpus.py::test_base_documental_vacia_o_inexistente`, `test_servicio.py::test_base_documental_vacia` |
| RF-09 | `test_servicio.py::test_consulta_valida_es_exitosa_y_queda_registrada`, `test_repositorio_guarda_lista_y_calcula_estadisticas` |
| RF-10 | `test_api.py::test_historial_y_estadisticas`, `test_salud` |
| RF-11 | `test_servicio.py::test_llm_*` |
