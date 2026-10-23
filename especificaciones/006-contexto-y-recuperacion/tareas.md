# Tareas 006 — Contexto de conversación y recuperación de consultas por ID

Orden de ejecución; cada implementación va precedida por su prueba (TDD). `[x]` = completada.

## Fase A — Backend
- [x] T-501 Pruebas unitarias: `es_seguimiento`, `entidades_nombradas`, `resolver_pregunta` y comparativos («más bajo» - mínimo).
- [x] T-502 Pruebas del orquestador y de la API: escenarios Gherkin, contexto inválido y malicioso, pregunta persistida, LLM con la pregunta efectiva, `GET /api/consultas/{id}`.
- [x] T-503 Ejecutar y confirmar el fallo.
- [x] T-504 Implementar `orquestador/contexto.py`, los comparativos en `texto.py` y `validar_contexto`.
- [x] T-505 Integrar el contexto en el orquestador y en la API; agregar el endpoint por ID.
- [x] T-506 Correr el banco de 293 preguntas sin contexto: solo cambian las de seguimiento.

## Fase B — Frontend
- [x] T-507 Pruebas: el contexto lleva las preguntas anteriores, «Nueva conversación» lo borra y la primera consulta envía solo `{"pregunta"}`.
- [x] T-508 Implementar la memoria de conversación y el botón «Nueva conversación».

## Fase C — Cierre
- [x] T-509 Suite completa y prueba en vivo; README y Cuestionario (persistencia y memoria).
