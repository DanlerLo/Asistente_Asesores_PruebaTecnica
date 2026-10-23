# Tareas 001 — Consulta documental con citación de fuentes

Orden de ejecución; cada implementación va precedida por su prueba (TDD). `[x]` = completada.

## Fase A — Base del proyecto
- [x] T-001 Crear `src/backend/asistente`, `tests/backend`, `pyproject.toml` (pytest con `pythonpath=src/backend`) y `requirements*.txt`.
- [x] T-002 `config.py`: dataclass inmutable `Configuracion` y `desde_entorno()` con valores por defecto locales (RNF-01).
- [x] T-003 `observabilidad.py`: formateador JSON y `configurar_logging()` (RNF-06).

## Fase B — Texto y corpus (RF-02, RF-07, RF-08)
- [x] T-004 Pruebas de `normalizar`, `raiz` y `tokenizar`: tildes, plurales, género, stopwords y sinónimos.
- [x] T-005 Implementar `texto.py` hasta poner T-004 en verde.
- [x] T-006 Pruebas de `fragmentar`: tablas → `clave: valor`, etiqueta + valor, etiqueta + lista, fragmento «Índice», ruta de sección y entidad.
- [x] T-007 Implementar `fragmentar()` con un clasificador de líneas con *lookahead*.
- [x] T-008 Pruebas de `cargar_corpus`: duplicados por hash, directorio vacío o inexistente, archivos no soportados, nombres en NFD (macOS).
- [x] T-009 Implementar `cargar_corpus()` con deduplicación, advertencias y normalización de nombres a NFC.

## Fase C — Recuperación y motor (RF-03, RF-04, RF-05)
- [x] T-010 Pruebas de `IndiceBM25.buscar`: sección correcta primero, bloqueo por entidad, consulta sin términos, índice vacío.
- [x] T-011 Implementar BM25 propio (`k1=1.5`, `b=0.75`), cobertura sobre términos conocidos, bloqueo por entidad y prioridad del índice.
- [x] T-012 Pruebas parametrizadas del motor extractivo con respuestas esperadas y frase canónica.
- [x] T-013 Implementar `seleccionar_lineas` (subsección nombrada → entidad sola → líneas por atributo → `None`) y `responder_extractivo`.
- [x] T-014 Pruebas de no responder con datos de otro producto y de comparación entre productos; ajustar reglas hasta verde.

## Fase D — Persistencia y flujo de la consulta (RF-09)
- [x] T-015 Pruebas de `RepositorioConsultas`: guardar, listar, estadísticas, estado inválido, creación del directorio.
- [x] T-016 Implementar el repositorio SQLite (`sqlite3`, candado, índices por fecha y estado).
- [x] T-017 Pruebas del flujo de consulta: estados, persistencia, caracteres especiales, consulta extensa, base vacía, duplicados.
- [x] T-018 Implementar el flujo con medición de latencia y log por consulta.

## Fase E — API HTTP (RF-01, RF-06, RF-10)
- [x] T-019 Pruebas de contrato: 200 con campos, 400 con `{"error", "codigo"}` para vacía, no JSON, no textual, larga y control; historial, estadísticas, salud.
- [x] T-020 Implementar `crear_app()`: rutas, CORS, manejadores de errores y ciclo de vida.
- [x] T-021 Prueba de humo con `uvicorn` y `curl`, documentada en el README.

## Fase F — Datos y documentación inicial
- [x] T-022 Ampliar `Data/` con registros ficticios y `Preguntas Frecuentes.md`, sin tocar el archivo restringido.
- [x] T-023 Documentar instalación, ejecución y limitaciones en `README.md`.

## Fase G — LLM opcional (RF-11)
- [x] T-024 Pruebas con proveedor falso: contexto solo con fragmentos, *fallback* ante excepción, frase canónica.
- [x] T-025 Implementar `llm.py`: `construir_proveedor` y `responder_con_llm`.
- [x] T-026 Prueba `test_prompts.py`: plantillas en `prompts/`, frase canónica, formato de fragmentos, variable faltante.
- [x] T-027 Pasar los prompts a plantillas Jinja2 en `generacion/prompts/` con el cargador `plantillas.py` (ADR-6).
- [x] T-028 Pruebas de `ProveedorGroq` sin red: URL, cabecera, cuerpo compatible con OpenAI, `include_reasoning: false`, clave obligatoria, modelo por defecto.
- [x] T-029 Implementar `ProveedorGroq` y su configuración (`LLM_PROVIDER=groq`, `GROQ_API_KEY`, `.env.example`).
- [x] T-030 Descartar respuestas incompletas (`finish_reason` distinto de `stop`) y enviar los parámetros de razonamiento solo a `gpt-oss`.
- [x] T-031 Devolver como fuentes solo las secciones que el texto del LLM cita.
- [x] T-032 Filtro `dato`: quitar caracteres invisibles y neutralizar `<` en los valores del prompt.
- [x] T-033 Dejar Groq como único proveedor y validar los valores de `LLM_PROVIDER`.

## Fase H — Precisión del motor (RF-12 a RF-16)
- [x] T-034 Prueba con la paráfrasis «¿Cuánto tiempo es válido para una PQR?», que respondía con datos de microseguros.
- [x] T-035 Implementar el término distintivo (RF-12). La primera versión rompía 17 respuestas correctas del banco y se descartó; la final solo cambia las 2 incorrectas.
- [x] T-036 Pruebas de productos y atributos inexistentes («hipotecario», «Exequial Plus», «salario») con pruebas de no regresión.
- [x] T-037 Implementar `nombra_algo_inexistente` y la ruta `inexistente` del enrutador (RF-13).
- [x] T-038 Hacer que el banco de regresión compare también el texto de la respuesta, no solo estado y fuentes.
- [x] T-039 Crear el conjunto de evaluación (97 preguntas con respuesta esperada) con una precisión mínima que solo puede subir.
- [x] T-040 Vocabulario del asesor: sinónimos y corrección ortográfica contra el corpus (RF-14).
- [x] T-041 Secciones generales con producto nombrado y comparaciones entre productos (RF-15).
- [x] T-042 Sin producto nombrado, no elegir uno al azar: regla de ambigüedad y catálogo por agente (RF-16, RF-O9).
- [x] T-043 Revisar a mano las 87 respuestas del banco que cambiaron antes de actualizar la foto (precisión 48,5 % → 83,5 %).

## Fase H2 — Respuestas equivocadas y frases del asesor (RF-22)
- [x] T-044 Clasificar los 16 fallos de la evaluación: 8 respuestas equivocadas (una línea real que no contesta) y 8 «sin información» con el dato disponible.
- [x] T-045 Pruebas en `test_motor.py` con las frases del asesor, la pregunta frecuente completa, el título de pregunta frecuente a medias y la subsección corta; confirmar que fallan con el motor anterior.
- [x] T-046 Frases del asesor → término del documento (monto, prima, plazo, desembolso, periodicidad, horario, costo del estudio) y palabras de relleno («banco», «sigue», «sirve»).
- [x] T-047 Preguntas frecuentes: la contenida completa responde primero; un título nunca se nombra a medias.
- [x] T-048 Subsección corta de un producto nombrado responde entera; «cliente» como contexto y no como atributo.
- [x] T-049 Revisar a mano las 35 respuestas del banco que cambiaron y descartar las reglas que movían respuestas correctas (participios, «codeudor» global); precisión 83,5 % → 100 %.

## Fase I — Robustez del servicio (RF-17 a RF-21)
- [x] T-050 Pruebas de `x-request-id`: valor válido respetado, inválido reemplazado, presente en los logs y en el 500.
- [x] T-051 Implementar el `ContextVar`, la fábrica de registros y la validación en el middleware.
- [x] T-052 Pruebas e implementación: ids con dígitos no ASCII → 400 y `limite` inválido con mensaje propio (RF-18).
- [x] T-053 Pruebas e implementación: configuración fuera de rango rechazada nombrando la variable (RF-19).
- [x] T-054 Pruebas e implementación del parser: BOM, comparadores `<`/`>`, etiquetas con horas y tablas de 3 columnas (RF-20).
- [x] T-055 Citar en el bloqueo solo las políticas que existen en el corpus (RF-21).
- [x] T-056 `log_level` en `Configuracion`, esquema OpenAPI de `pregunta` y endpoints con SQLite síncronos.
- [x] T-057 Logs de uvicorn en el mismo formato JSON.

## Fase J — Calidad y entrega
- [x] T-058 ruff, mypy y cobertura en el CI; `requires-python` en `pyproject.toml`.
- [x] T-059 Prueba de latencia p95 del modo extractivo sobre el banco (RNF-02).
- [x] T-060 `LLM_PROVIDER` vacío, desconocido o `groq` sin clave arranca en modo sin conexión con una advertencia, en vez de impedir el arranque (RF-11).
