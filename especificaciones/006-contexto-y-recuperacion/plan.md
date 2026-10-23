# Plan 006 — Contexto de conversación y recuperación de consultas por ID

## Arquitectura propuesta

```
 frontend (memoria de la conversación: últimas 3 preguntas, "Nueva conversación")
     │  POST /api/consultar {"pregunta", "contexto"?: [...]}
     ▼
 Orquestador.consultar(pregunta, contexto)
   1. validar_pregunta(pregunta)  +  validar cada elemento del contexto (RF-C6)
   2. evaluar_entrada(pregunta)   -  bloqueo (sin cambios)
   3. contexto.resolver_pregunta(pregunta, contexto_permitido, entidades_del_corpus)
        ├─ no es seguimiento o nombra su entidad - pregunta original
        ├─ seguimiento + referente en el contexto - "pregunta (Entidad)"
        └─ seguimiento sin referente           - Sin información (RF-C5)
   4. recuperar - enrutar - agente - filtrar salida   (con la pregunta efectiva)
   5. persistir la pregunta ORIGINAL; log con pregunta_efectiva y referente

 GET /api/consultas/{id} - RepositorioConsultas.obtener(id)   (ya existía)
```

## Componentes
| Componente | Responsabilidad |
|------------|-----------------|
| `orquestador/contexto.py` | `Entidad`, `entidades_del_corpus`, `es_seguimiento`, `entidades_nombradas`, `resolver_pregunta` (puro y determinista) |
| `herramientas/texto.py` | Comparativos «más bajo/menor» - mínimo, «más alto/mayor» - máximo (RF-C8) |
| `seguridad/guardrails.py` | `validar_contexto` (RF-C6) |
| `orquestador/orquestador.py` | Recibe `contexto`, resuelve la pregunta efectiva, persiste la original |
| `api/app.py` | Campo `contexto`; `GET /api/consultas/{id}` |
| `frontend` | `consultar(pregunta, contexto)`; estado de la conversación; botón «Nueva conversación» |

## Decisiones de arquitectura
- **ADR-16 Memoria en el cliente, no en el servidor.** El frontend envía las preguntas anteriores; el servidor sigue sin estado y el esquema de `consultas` no cambia (cambiarlo es decisión humana, AGENTS.md §5). Persistir conversaciones queda como mejora.
- **ADR-17 Se hereda la entidad, no el texto.** El referente se toma de los nombres de productos y secciones del corpus que la pregunta anterior nombraba; nunca se copia texto libre del contexto a la pregunta efectiva. Así el contexto no puede inyectar instrucciones ni términos arbitrarios.
- **ADR-18 Marcadores explícitos de seguimiento.** Detectar seguimiento por la forma («¿Y…?», «su», «ese») evita heredar contexto en preguntas nuevas («¿Cuál es el horario de atención?» tras una pregunta de crédito).
- **ADR-19 SQLite se mantiene.** Medido en la máquina de desarrollo con 10.000 consultas: guardar 0,22 ms y leer por ID 0,05 ms con SQLite, frente a 61,8 ms y 12,8 ms con un archivo JSON reescrito en cada consulta (que además se corrompe si el proceso cae a mitad de escritura). SQLite es una librería embebida en Python: no requiere servidor ni instalación.

## Estrategia de pruebas
| Nivel | Archivo | Cubre |
|-------|---------|-------|
| Unitarias | `tests/backend/test_contexto.py` | `es_seguimiento`, `entidades_nombradas`, `resolver_pregunta`, comparativos |
| Orquestador y API | `tests/backend/test_contexto.py` | escenarios Gherkin, contexto inválido/malicioso, persistencia de la pregunta original, LLM recibe la pregunta efectiva, `GET /api/consultas/{id}` |
| Regresión | `tests/backend/test_banco.py` (293 preguntas) | sin contexto, solo cambian preguntas de seguimiento (RF-C5) |
| Frontend | `tests/frontend/Conversacion.test.tsx` | envío del contexto, «Nueva conversación» |

## Trazabilidad
| RF | Pruebas |
|----|---------|
| RF-C1, RF-C3, RF-C4 | `test_contexto.py::test_seguimiento_*`, `test_pregunta_completa_ignora_el_contexto` |
| RF-C2 | `test_contexto.py::test_es_seguimiento` |
| RF-C5 | `test_contexto.py::test_seguimiento_sin_referente_no_adivina` |
| RF-C6 | `test_contexto.py::test_contexto_invalido`, `test_api_contexto_invalido_400`, `test_contexto_malicioso_se_ignora` |
| RF-C7 | `test_contexto.py::test_se_persiste_la_pregunta_original` |
| RF-C8 | `test_contexto.py::test_comparativos` |
| RF-C9 | `test_contexto.py::test_get_consulta_por_id*` |
| RF-C10 | `Conversacion.test.tsx` |
| RNF-C1 | `test_banco.py::test_el_banco_es_determinista`; `test_contexto.py::test_resolver_pregunta_hereda_la_entidad_mas_reciente` |
| RNF-C2 | la tabla `consultas` no cambia: `test_contexto.py::test_se_persiste_la_pregunta_original` usa el mismo repositorio |
| RNF-C3 | `test_contexto.py::test_contexto_malicioso_se_ignora`, `test_entidades_nombradas` (el referente es siempre un nombre del corpus) |
