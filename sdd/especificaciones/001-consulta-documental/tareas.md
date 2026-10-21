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

## Fase G — Datos y documentación
- [x] T-024 Ampliar `Data/` con registros ficticios adicionales y `Preguntas Frecuentes.md` (sin tocar el archivo restringido).
- [x] T-025 Documentar instalación, ejecución y limitaciones en `README.md`.

## Pendientes / mejoras futuras (fuera de alcance)
- [ ] T-026 Caché en memoria de respuestas por pregunta normalizada (clave: raíces ordenadas).
- [ ] T-027 Recarga del corpus sin reiniciar (`POST /api/recargar` protegido).
- [ ] T-028 Evaluación automática con un conjunto de preguntas/respuestas esperadas (`tests/backend/evaluacion.yaml`).
