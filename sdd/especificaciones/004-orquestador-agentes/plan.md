# Plan 004 — Orquestador y agentes especializados

## Arquitectura propuesta

```
                         ┌─────────────────────── orquestador/ ───────────────────────┐
POST /api/consultar ──►  │ Orquestador.consultar()                                     │
 (api/)                  │  1. seguridad.validar_pregunta          (RF-06)             │
                         │  2. seguridad.evaluar_entrada ──► bloqueo (RF-O6)           │
                         │  3. herramientas.IndiceBM25.buscar                          │
                         │  4. Enrutador.elegir(resultados) ──┐    (RF-O2, RF-O3)      │
                         │  5. agente.responder(...)  ◄───────┘                        │
                         │  6. seguridad.filtrar_salida            (RF-S4)             │
                         │  7. infraestructura.RepositorioConsultas.guardar (RF-09)    │
                         └─────────────────────────────────────────────────────────────┘
                                         │
              ┌──────────────────────────┼───────────────────────────┐
        agentes/credito          agentes/microseguros          agentes/operativo      agentes/fuera_de_dominio
              └──────── AgenteDocumental (agentes/base.py) ───────────┘               (frase canónica, sin LLM)
                                         │
                       generacion/ (extractivo · llm · plantillas · prompts/*.j2)
```

Dependencias permitidas (de arriba hacia abajo): `api → orquestador → agentes → generacion → herramientas`; `seguridad`, `infraestructura`, `dominio` y `config` son transversales y no dependen de capas superiores.

## Componentes
| Paquete / módulo | Responsabilidad | Antes |
|------------------|-----------------|-------|
| `main.py` | Punto de entrada `asistente.main:app` (sin cambios para uvicorn) | `main.py` |
| `api/app.py` | FastAPI: rutas, CORS, manejo de errores, `x-request-id` | `main.py` |
| `orquestador/orquestador.py` | Flujo completo de una consulta (RF-O1) | `servicio.py` |
| `orquestador/enrutador.py` | Elección determinista del agente (RF-O2, RF-O3) | — |
| `agentes/base.py` | Protocolo `Agente` y `AgenteDocumental` (extractivo o LLM con *fallback*) | parte de `servicio.py` |
| `agentes/credito.py`, `microseguros.py`, `operativo.py` | Agentes de dominio: nombre y documentos que atienden | — |
| `agentes/fuera_de_dominio.py` | Frase canónica sin LLM (RF-O4) | — |
| `herramientas/texto.py`, `corpus.py`, `markdown.py`, `recuperacion.py` | Normalización, carga, fragmentación y búsqueda BM25 | raíz del paquete |
| `generacion/extractivo.py`, `llm.py`, `plantillas.py`, `prompts/` | Redacción de la respuesta | `motor.py`, `llm.py`, `plantillas.py` |
| `seguridad/guardrails.py`, `ingesta.py` | Validación, bloqueo por intención, filtro de salida; política de ingesta (restringidos, instrucciones embebidas) | `guardrails.py`, `corpus.py` |
| `infraestructura/persistencia.py`, `observabilidad.py` | SQLite y logs JSON | raíz del paquete |
| `dominio.py` | Estados, frase canónica, `Fuente`, `RespuestaGenerada` (modelos compartidos) | `motor.py` |
| `config.py` | Configuración desde el entorno | `config.py` |

## Decisiones de arquitectura
- **ADR-7 Agentes deterministas, no autónomos.** "Agente" aquí es un componente con una responsabilidad de dominio y una interfaz común (`nombre`, `responder`). El enrutamiento es por reglas porque la prueba exige determinismo, ejecución local sin red y trazabilidad; un LLM decidiendo la ruta añadiría costo, latencia, no determinismo y superficie de *prompt injection*. Un enrutador con LLM puede añadirse después como opción, igual que la redacción (RF-11).
- **ADR-8 La seguridad no es un agente.** Los guardrails son transversales y los ejecuta el orquestador antes y después de cualquier agente; ningún agente puede omitirlos.
- **ADR-9 El enrutamiento no filtra evidencia.** El agente elegido recibe todos los fragmentos recuperados; así una comparación o una pregunta que cruza documentos conserva el comportamiento de 001.
- **ADR-10 Sin estado nuevo para fuera de dominio.** La prueba técnica fija tres estados; "fuera de dominio" es un motivo de enrutamiento visible en logs, no un estado persistido.

## Estrategia de pruebas
| Nivel | Archivo | Cubre |
|-------|---------|-------|
| Enrutamiento y agentes | `tests/backend/test_agentes.py` | RF-O2..O7, RNF-O1 (ejemplos del esquema Gherkin, fuera de dominio sin LLM, documento sin agente, seguridad antes de agentes, log y salud) |
| Arquitectura | `tests/backend/test_arquitectura.py` | RNF-O3 (análisis de importaciones con `ast`) |
| Regresión | suite existente (`test_api`, `test_orquestador`, `test_motor`, `test_corpus`, `test_guardrails`, `test_prompts`) | RF-O5, RF-O8: solo cambian rutas de importación, nunca aserciones |

## Trazabilidad
| RF | Pruebas |
|----|---------|
| RF-O1, RF-O6 | `test_agentes.py::test_pregunta_bloqueada_no_llega_a_ningun_agente` |
| RF-O2 | `test_agentes.py::test_enrutamiento_por_dominio`, `test_documento_sin_agente_va_al_operativo` |
| RF-O3 | `test_agentes.py::test_fuera_de_dominio_responde_frase_canonica_sin_llm` (`sin_fragmentos`), `test_base_vacia_va_a_fuera_de_dominio` (`base_vacia`) |
| RF-O4 | `test_agentes.py::test_fuera_de_dominio_responde_frase_canonica_sin_llm` |
| RF-O5 | suite de regresión completa |
| RF-O8 | `test_api.py::test_consulta_valida` (conjunto exacto de campos) |
| RF-O7 | `test_agentes.py::test_log_incluye_agente_y_motivo`, `test_salud_lista_agentes` |
| RNF-O1 | `test_agentes.py::test_enrutamiento_es_determinista` |
| RNF-O3 | `test_arquitectura.py` (incluye `dominio.py` y `config.py`) |
