# Tareas 006 — Contexto de conversación y recuperación de consultas por ID

Orden de ejecución; prueba antes que implementación. `[x]` = completada.

## Fase A — Backend
- [x] T-401 Pruebas unitarias: `es_seguimiento`, `entidades_nombradas`, `resolver_pregunta`, comparativos.
- [x] T-402 Pruebas de orquestador y API: escenarios Gherkin, contexto inválido y malicioso, pregunta original persistida, LLM con pregunta efectiva, `GET /api/consultas/{id}`.
- [x] T-403 Ejecutar y confirmar el fallo.
- [x] T-404 Implementar `orquestador/contexto.py`, comparativos en `texto.py`, `validar_contexto`.
- [x] T-405 Integrar en el orquestador y la API; endpoint por ID.
- [x] T-406 Banco de 316 preguntas sin contexto: solo cambian las de seguimiento.

## Fase B — Frontend
- [x] T-407 Pruebas (Vitest): el contexto se envía con las preguntas anteriores; «Nueva conversación» lo borra; la primera consulta envía solo `{"pregunta"}`.
- [x] T-408 Implementar memoria de conversación y botón.

## Fase C — Cierre
- [x] T-409 Suite completa y prueba en vivo; README, Cuestionario (persistencia y memoria).

## Pendientes / mejoras futuras
- [ ] T-410 Persistir conversaciones en el servidor (identificador de conversación; cambia el esquema: decisión humana).
- [ ] T-411 Heredar también el atributo («¿y el de Agro Crece?» tras «monto máximo del Impulso»).
