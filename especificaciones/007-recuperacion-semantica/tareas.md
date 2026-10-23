# Tareas 007 — Recuperación semántica local y más contexto para el LLM

Orden de ejecución; cada implementación va precedida por su prueba (TDD). `[x]` = completada.

## Fase A — Medición y viabilidad
- [x] T-601 Escribir 40 preguntas nuevas con respuesta esperada (`generalizacion.json`), sin repetir banco ni evaluación.
- [x] T-602 Medir la línea base sin embeddings: 19/40 (48 %), 4 respuestas equivocadas.
- [x] T-603 Probar `fastembed` con `paraphrase-multilingual-MiniLM-L12-v2` en un entorno aparte: descarga única de 0,22 GB, 108 líneas en 0,7 s.

## Fase B — Pruebas que fallan
- [x] T-604 `test_semantica.py`: índice por líneas, sin restringidos, configuración.
- [x] T-605 Pruebas del orquestador: nunca rescata bloqueos ni inexistentes, enrutamiento semántico, degradación, contexto ampliado del LLM.
- [x] T-606 Ejecutar y confirmar el fallo.

## Fase C — Implementación
- [x] T-607 Configuración: `EMBEDDINGS`, `EMBEDDINGS_MODELO`, `EMBEDDINGS_CACHE`, `UMBRAL_SEMANTICO`, `LLM_MAX_FRAGMENTOS`.
- [x] T-608 `herramientas/semantica.py`: `Embebedor`, `EmbebedorLocal`, `IndiceSemantico`, `construir_embebedor`.
- [x] T-609 Búsqueda híbrida y enrutamiento semántico en el orquestador.
- [x] T-610 Contexto ampliado del LLM en `AgenteDocumental`.
- [x] T-611 Construir el embebedor en `api/app.py` con degradación a léxico si falla.

## Fase D — Calibración y cierre
- [x] T-612 Implementar y medir un respaldo semántico del extractivo (umbral y margen) con banco, evaluación y las 40 preguntas nuevas.
- [x] T-613 Retirar ese respaldo: aumentaba las respuestas equivocadas (ADR-25); la prueba `test_el_modo_extractivo_no_responde_por_similitud` lo fija.
- [x] T-614 Medir la generalización con Groq: contexto de antes frente a contexto ampliado con embeddings; registrar resultados en el plan.
- [x] T-615 Documentar la recuperación híbrida como parte central de la arquitectura: README, plan 001 (ADR-1), `AGENTS.md`, `.env.example`, `requirements.txt` y Cuestionario.

## Fase E — Revisión del evaluador
- [x] T-616 Escribir `robustez.json`: las 6 preguntas que falló el evaluador y 29 nuevas, antes de cambiar el motor.
- [x] T-617 `medicion.py`: aciertos, incorrectas, abstenciones y completitud de listas por separado.
- [x] T-618 Pruebas: con similitud clara se lee la sección completa; umbral y margen; un producto nombrado sin el dato no se rescata (RF-E4).
- [x] T-619 `ContextoSemantico.seccion_clara`, `responder_con_seccion` y `Orquestador._leer_seccion`; medir las variantes de ADR-27 y adoptar la que no agrega incorrectas.
- [x] T-620 Embeddings activados por defecto al arrancar y fijados en `none` para la suite (RF-E1, ADR-28).
