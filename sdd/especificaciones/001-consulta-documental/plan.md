# Plan 001 — Consulta documental con citación de fuentes

## Arquitectura propuesta

```
            ┌──────────────────────────── src/backend/asistente ─────────────────────────────────┐
HTTP        │ api/app.py (FastAPI)                                                                 │
POST        │   └─► orquestador/ ─► seguridad.validar_pregunta / evaluar_entrada  (RF-06, 002)    │
/api/       │         ├─► herramientas.IndiceBM25.buscar                 (RF-02..04, RF-13)       │
consultar   │         │       └─ herramientas.corpus (Data/*.md → Fragmento[])                    │
            │         ├─► enrutador ─► agentes/ ─► generacion.extractivo ──o── generacion.llm     │
            │         │                              (RF-03, RF-05, RF-12)       (RF-11)          │
            │         ├─► seguridad.filtrar_salida                       (002)                    │
            │         └─► infraestructura.RepositorioConsultas           (RF-09) ──► SQLite       │
            └────────────────────────────────────────────────────────────────────────────────────┘
```

Flujo de una consulta: **validar → guardrail de entrada → recuperar → responder → guardrail de salida → persistir**. El orquestador (antes `ServicioConsultas`) es independiente de HTTP para permitir pruebas unitarias sin levantar el servidor.

> Desde la característica 004 el servicio es el `Orquestador` (`orquestador/`), que delega la respuesta en agentes por dominio, y los módulos viven en carpetas por capa. Ver `sdd/especificaciones/004-orquestador-agentes/plan.md`.

## Componentes
| Componente | Responsabilidad | Decisiones clave |
|------------|-----------------|------------------|
| `config.py` | Configuración inmutable desde variables de entorno | Valores por defecto seguros: sin LLM, `Data/`, SQLite en `storage/` |
| `herramientas/texto.py` | Normalización en español: tildes, stopwords, raíces, sinónimos | Stemmer propio determinista (sin NLTK/spaCy) aplicado igual a documentos y preguntas |
| `herramientas/corpus.py` | Carga, exclusión de restringidos, deduplicación, fragmentación por encabezados | Tablas → `clave: valor`; etiqueta + lista → una línea; fragmento «Índice» por documento |
| `herramientas/recuperacion.py` | BM25 propio + bloqueo por entidad + priorización del índice | Cobertura calculada sobre términos que existen en el corpus |
| `generacion/extractivo.py` (antes `motor.py`) | Respuesta extractiva: elige las líneas que responden; compone texto con cita | Reglas explícitas y probadas (ver docstring de `seleccionar_lineas`) |
| `generacion/llm.py` | Proveedor Groq opcional | Prompt cerrado a fragmentos; temperatura 0; fallback al extractivo |
| `generacion/plantillas.py` + `generacion/prompts/*.j2` | Prompts del LLM como plantillas Jinja2 | Sin autoescape (texto plano), `StrictUndefined` |
| `infraestructura/persistencia.py` | SQLite vía `sqlite3` estándar | Tabla `consultas` con `CHECK` de estado, índices por fecha y estado |
| `api/app.py` + `main.py` | API, CORS, manejo de errores, request-id | Fábrica `crear_app()` para pruebas; `main.py` es el punto de entrada |
| `infraestructura/observabilidad.py` | Logs JSON | Un evento por consulta con estado/modo/latencia |

## Decisiones de arquitectura (ADR resumidos)
- **ADR-1 Recuperación léxica en lugar de embeddings.** El corpus es pequeño, en español y con vocabulario controlado; BM25 es determinista, explicable y no requiere modelos ni red. Evolución a RAG vectorial descrita en `docs/Cuestionario.md`.
- **ADR-2 Respuesta extractiva por defecto.** Garantiza por construcción "responder únicamente con información encontrada"; un LLM es opcional para redacción.
- **ADR-3 SQLite.** Cero configuración, archivo local, suficiente para el volumen de la prueba; el repositorio aísla el cambio futuro a PostgreSQL.
- **ADR-4 Sin frameworks adicionales** (ORM, rank_bm25, NLTK): menos superficie de ataque y de dependencia; el código propio está cubierto por pruebas.
- **ADR-5 Límite de 1000 caracteres por pregunta** (configurable): protege latencia y costo del LLM y cubre preguntas reales de un asesor.
- **ADR-6 Prompts en plantillas Jinja2** (`src/backend/asistente/generacion/prompts/*.j2`): separa el texto de los prompts del código, permite revisarlos y versionarlos sin tocar Python y deja explícitas sus variables. Jinja2 es una dependencia madura, pura en Python y sin red; se usa sin autoescape (los prompts no son HTML) y con `StrictUndefined` para que una variable faltante falle en lugar de producir un prompt incompleto. Los valores insertados no se reinterpretan como plantilla.
- **ADR-11 Groq como LLM gratuito por defecto** (cuando se activa uno): el enunciado no admite herramientas pagas; GroqCloud ofrece plan gratuito y API compatible con OpenAI (un `httpx.post`, sin SDK nuevo). Modelo por defecto `openai/gpt-oss-20b` (producción vigente; los Llama 3.x se retiraron del plan gratuito el 16/08/2026), `include_reasoning: false`, `reasoning_effort: low`, temperatura 0. Sigue siendo opcional: `LLM_PROVIDER=none` por defecto.
- **ADR-12 Término distintivo en el respaldo (RF-12):** la coincidencia léxica podía caer a un fragmento de otro tema que comparte palabras comunes («válido» ≈ «Validación documental») cuando el fragmento principal («Gestión de PQR») no respondía. Se exige que ese respaldo mencione al menos un término del encabezado del fragmento principal. Una primera versión que exigía términos de *todos* los encabezados recuperados rompía 17 respuestas correctas (preguntas frecuentes generales que no repiten el nombre del producto); se detectó en revisión adversarial y se descartó. Evaluación con 316 preguntas: la versión final solo cambia las 2 respuestas incorrectas de la PQR.

## Estrategia de pruebas
| Nivel | Archivo | Cubre |
|-------|---------|-------|
| Unitarias de texto/corpus | `tests/backend/test_corpus.py` | normalización, stemming, tablas/etiquetas/listas, índice, exclusión de restringidos, duplicados, base vacía |
| Unitarias de recuperación/motor | `tests/backend/test_motor.py` | ranking, bloqueo por entidad, respuestas esperadas, frase canónica, comparación de productos |
| Plantillas de prompts | `tests/backend/test_prompts.py` | carpeta `prompts/`, frase canónica, formato de fragmentos, variable faltante |
| Orquestador (flujo completo) | `tests/backend/test_orquestador.py` | estados, persistencia, caracteres especiales, consulta extensa, duplicados, LLM falso y fallback |
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
| RF-07 | `test_corpus.py::test_documentos_duplicados_se_indexan_una_sola_vez`, `test_orquestador.py::test_documentos_duplicados_no_duplican_fuentes` |
| RF-08 | `test_corpus.py::test_base_documental_vacia_o_inexistente`, `test_orquestador.py::test_base_documental_vacia` |
| RF-09 | `test_orquestador.py::test_consulta_valida_es_exitosa_y_queda_registrada`, `test_repositorio_guarda_lista_y_calcula_estadisticas` |
| RF-10 | `test_api.py::test_historial_y_estadisticas`, `test_salud` |
| RF-11 | `test_orquestador.py::test_llm_*`, `test_prompts.py`, `test_proveedores_llm.py` |
| RF-12 | `test_motor.py::test_parafrasis_no_responde_con_datos_de_otro_tema`, `test_rf12_no_descarta_respuestas_generales` |
| RF-13 | `test_motor.py::test_producto_o_atributo_inexistente_no_responde_con_otro`, `test_palabras_desconocidas_que_no_nombran_producto_siguen_respondiendo` |
