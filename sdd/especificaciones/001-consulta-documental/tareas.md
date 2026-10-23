# Tareas 001 — Consulta documental con citación de fuentes

Orden de ejecución. Cada tarea de implementación va precedida por su prueba (TDD). `[x]` = completada.

## Fase A — Base del proyecto
- [x] T-001 Crear estructura `src/backend/asistente`, `tests/backend`, `pyproject.toml` (pytest con `pythonpath=src/backend`), `requirements*.txt`.
- [x] T-002 `config.py`: dataclass inmutable `Configuracion` + `desde_entorno()` con valores por defecto locales (RNF-01).
- [x] T-003 `observabilidad.py`: formateador JSON y `configurar_logging()` (RNF-06).

## Fase B — Texto y corpus (RF-02, RF-07, RF-08)
- [x] T-004 Pruebas de `normalizar`, `raiz`, `tokenizar` (tildes, plurales, género, stopwords, sinónimos).
- [x] T-005 Implementar `texto.py` hasta poner T-004 en verde.
- [x] T-006 Pruebas de `fragmentar`: tablas → `clave: valor`, etiqueta + valor, etiqueta + lista, fragmento «Índice», ruta de sección y entidad.
- [x] T-007 Implementar `fragmentar()` en `corpus.py` (clasificador de líneas con *lookahead*).
- [x] T-008 Pruebas de `cargar_corpus`: duplicados por hash, directorio vacío/inexistente, archivos no soportados.
- [x] T-009 Implementar `cargar_corpus()` con deduplicación y advertencias.

## Fase C — Recuperación y motor (RF-03, RF-04, RF-05)
- [x] T-010 Pruebas de `IndiceBM25.buscar`: sección correcta primero, bloqueo por entidad, consulta sin términos, índice vacío.
- [x] T-011 Implementar BM25 propio (`k1=1.5`, `b=0.75`), cobertura sobre términos conocidos, `_candidatos` con bloqueo por entidad, `_priorizar_indice`.
- [x] T-012 Pruebas parametrizadas del motor extractivo con respuestas esperadas y frase canónica.
- [x] T-013 Implementar `seleccionar_lineas` (subsección nombrada → entidad sola → líneas por atributo → `None`) y `responder_extractivo` (mínimo dos términos coincidentes; segundo fragmento solo para otra entidad nombrada).
- [x] T-014 Prueba `test_no_responde_con_datos_de_otro_producto` y comparación entre productos; ajustar reglas hasta verde.

## Fase D — Persistencia y servicio (RF-09)
- [x] T-015 Pruebas de `RepositorioConsultas`: guardar, listar, estadísticas, estado inválido, creación del directorio.
- [x] T-016 Implementar repositorio SQLite (`sqlite3`, `check_same_thread=False`, bloqueo, índices).
- [x] T-017 Pruebas de `ServicioConsultas`: estados, persistencia, caracteres especiales, consulta extensa, base vacía, duplicados.
- [x] T-018 Implementar `ServicioConsultas.consultar()` con medición de latencia y logging.

## Fase E — API HTTP (RF-01, RF-06, RF-10)
- [x] T-019 Pruebas de contrato: 200 con campos, 400 con `{"error","codigo"}` para vacía/no JSON/no textual/larga/control, historial, estadísticas, salud, `x-request-id`.
- [x] T-020 Implementar `crear_app()`: rutas, CORS, manejadores de `ErrorValidacion`, `RequestValidationError` y `Exception`, ciclo de vida.
- [x] T-021 Prueba de humo manual con `uvicorn` + `curl` (documentada en README).

## Fase F — LLM opcional (RF-11)
- [x] T-022 Pruebas con proveedor falso: contexto solo con fragmentos, fallback ante excepción, frase canónica.
- [x] T-023 Implementar `llm.py` (cliente `httpx`), `construir_proveedor`, `responder_con_llm`.
- [x] T-029 Prueba `test_prompts.py`: plantillas en `prompts/`, frase canónica, formato de fragmentos, variable faltante.
- [x] T-030 Mover los prompts a `src/backend/asistente/prompts/*.j2` (Jinja2) con el cargador `plantillas.py` (ADR-6).

## Fase F2 — Groq y precisión (RF-11, RF-12)
- [x] T-031 Pruebas de `ProveedorGroq` sin red (`httpx.post` simulado): URL, cabecera, cuerpo compatible con OpenAI, `include_reasoning: false`, respuesta vacía, clave obligatoria, modelo por defecto y configuración desde el entorno.
- [x] T-032 Implementar `ProveedorGroq`, `GROQ_API_KEY`, `LLM_PROVIDER=groq` (`.env.example`, README).
- [x] T-033 Prueba con la paráfrasis real «¿Cuánto tiempo es válido para una PQR?» (respondía con datos de microseguros).
- [x] T-034 Implementar RF-12 (término distintivo). La revisión adversarial mostró que la primera versión rompía 17 respuestas correctas; se rediseñó (solo el encabezado del fragmento principal y solo para el respaldo) y se evaluó con 316 preguntas: solo cambian las 2 incorrectas. Pruebas de regresión con 6 de esas preguntas.
- [x] T-035 Groq: descartar respuestas incompletas (`finish_reason` distinto de `stop`); parámetros de razonamiento solo para `gpt-oss`.
- [x] T-036 Fuentes del LLM = secciones citadas en el texto («archivo › sección»), no todas las del archivo.
- [x] T-037 Filtro `dato`: quita caracteres invisibles de formato y neutraliza todo `<` (incluidas variantes Unicode).
- [ ] T-038 Enmascarar datos personales de la pregunta antes de enviarla a un proveedor externo (decisión humana).
- [x] T-039 RF-13 (hallazgo de la auditoría contra el PDF): pruebas con productos inexistentes («hipotecario», «Exequial Plus», «mascotas», «vivienda») y atributo inexistente («salario»), más pruebas de no regresión («¿qué crédito financia…?»).
- [x] T-040 Implementar `IndiceBM25.nombra_algo_inexistente` y ruta `inexistente` en el enrutador; banco de trabajo de 340 preguntas (el versionado tiene 293): solo cambian las 6 incorrectas.
- [x] T-041 El banco de regresión compara también el texto de la respuesta (antes solo estado y fuentes: 108 de 293 respuestas podían cambiar sin que fallara nada). Hallazgo B3 de la auditoría.
- [x] T-042 Motor (hallazgos B1, B2, B4–B9, B11 de la auditoría): vocabulario y corrección ortográfica (RF-14), secciones generales y comparaciones (RF-15), sin adivinar producto (RF-16), catálogo por agente (RF-O9). Evaluación 48,5 % → 83,5 %; 87 respuestas del banco revisadas una a una antes de regenerar la foto.

## Fase H — Robustez del servicio (RF-17, RF-18, RF-19; hallazgos C7, D2 y D3 de la auditoría)
- [x] T-043 Pruebas `test_robustez_api.py`: `x-request-id` validado y presente en logs y en el 500; ids con dígitos no ASCII → 400; `limite` inválido con mensaje propio; configuración fuera de rango rechazada nombrando la variable.
- [x] T-044 Implementar: `ContextVar` + fábrica de registros en `observabilidad.py`, validación en el middleware y en `GET /api/consultas/{id}`, `Configuracion.__post_init__` y lectura numérica con mensaje.

- [x] T-045 RF-20 (hallazgo D4): pruebas del parser (BOM, comparadores, etiquetas con horas, tablas de 3 columnas) e implementación en `corpus.py`; el banco de 293 preguntas no cambia.

- [x] T-046 RF-21 y hallazgos F3, F6, F10, F11, G5: citas de bloqueo resueltas contra el corpus (`CITAS_BLOQUEO` en `seguridad/`), `log_level` en `Configuracion`, endpoints con SQLite síncronos, esquema OpenAPI de `pregunta`, prueba de capas más estricta (`generacion` y `agentes` no importan `seguridad` ni `infraestructura`).

- [x] T-047 Hallazgo G7: los registradores de uvicorn se redirigen al manejador JSON de la raíz (un solo formato en stdout); verificado con uvicorn real.

## Fase G — Datos y documentación
- [x] T-024 Ampliar `Data/` con registros ficticios adicionales y `Preguntas Frecuentes.md` (sin tocar el archivo restringido).
- [x] T-025 Documentar instalación, ejecución y limitaciones en `README.md`.

## Pendientes / mejoras futuras (fuera de alcance)
- [ ] T-026 Caché en memoria de respuestas por pregunta normalizada (clave: raíces ordenadas).
- [ ] T-027 Recarga del corpus sin reiniciar (`POST /api/recargar` protegido).
- [x] T-028 Evaluación automática con preguntas y respuesta esperada: `tests/backend/evaluacion.json` (97 casos) + `test_evaluacion.py` con precisión mínima como trinquete (línea base 48,5 %).
