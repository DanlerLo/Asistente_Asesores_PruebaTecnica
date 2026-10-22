# Plan 005 — Cuota de la API gratuita y modo sin conexión

## Arquitectura propuesta

```
 frontend                                   backend
 ┌──────────────────────┐   GET /api/llm   ┌──────────────────────────────────────────────┐
 │ SelectorModo         │ ───────────────► │ api/app.py                                   │
 │  "Quedan X de Y"     │   PUT /api/llm   │   └─► Orquestador.estado_llm()               │
 │  [Desactivar/Activar]│ ───────────────► │       Orquestador.cambiar_modo_llm(activo)   │
 └──────────────────────┘                  │         proveedor_llm = configurado | None   │
                                           │ generacion/llm.py                            │
                                           │   ProveedorGroq.completar()                  │
                                           │     └─ registra CuotaLLM de las cabeceras    │
                                           │        (también en 429) + contador llamadas  │
                                           └──────────────────────────────────────────────┘
```

## Componentes
| Componente | Responsabilidad |
|------------|-----------------|
| `generacion/llm.py::CuotaLLM` | Datos de cuota (solicitudes/día, tokens/minuto, segundos hasta la recarga, última actualización) |
| `generacion/llm.py::leer_cuota` | Convierte las cabeceras `x-ratelimit-*` en `CuotaLLM`; tolera ausentes y mal formadas; interpreta duraciones tipo `2m59.56s` |
| `ProveedorGroq` | Registra `cuota` y `llamadas` en cada respuesta (antes de `raise_for_status`) |
| `orquestador/orquestador.py` | Guarda el proveedor configurado; `estado_llm()` y `cambiar_modo_llm()` |
| `api/app.py` | `GET /api/llm`, `PUT /api/llm` (400 `SOLICITUD_INVALIDA`, 400 `LLM_NO_CONFIGURADO`) |
| `frontend/src/components/SelectorModo.tsx` | Botones «Modo conexión (Groq)» / «Modo sin conexión», cuota y pop-up; `api.ts::obtenerEstadoLlm`, `cambiarModoLlm` |

## Decisiones de arquitectura
- **ADR-13 Cuota desde cabeceras, sin llamadas extra.** Groq no expone un endpoint de uso; leer las cabeceras de las llamadas que ya ocurren cuesta cero solicitudes. Consecuencia: antes de la primera consulta la cuota es desconocida y se dice así.
- **ADR-14 Modo en memoria; `.env` manda al arrancar.** Cambiar el modo no reescribe `.env` (un archivo con secretos no debe editarlo la aplicación). Reactivar solo reutiliza el proveedor que una persona configuró: la decisión de enviar datos a un servicio externo sigue siendo humana (AGENTS.md §5).
- **ADR-15 Endpoints nuevos en lugar de campos nuevos en `/api/consultar`.** El contrato de RF-01 queda intacto; el frontend consulta `GET /api/llm` después de cada consulta.

## Estrategia de pruebas
| Nivel | Archivo | Cubre |
|-------|---------|-------|
| Unitarias | `tests/backend/test_cuota_llm.py` | `leer_cuota` (valores, ausentes, mal formados, duraciones), registro en éxito y en 429, contador |
| Servicio y API | `tests/backend/test_cuota_llm.py` | `GET/PUT /api/llm`, desactivar ⇒ sin llamadas al LLM, reactivar, errores 400, sin clave en la respuesta |
| Frontend | `tests/frontend/SelectorModo.test.tsx` | sin proveedor, cuota desconocida, "Quedan X de Y", aviso < 10 %, botón desactivar/activar, fallo de `GET /api/llm` |

## Trazabilidad
| RF | Pruebas |
|----|---------|
| RF-L1, RF-L2 | `test_cuota_llm.py::test_leer_cuota_*`, `test_groq_registra_cuota_*` |
| RF-L3 | `test_cuota_llm.py::test_get_llm_*` |
| RF-L4 | `test_cuota_llm.py::test_desactivar_evita_llamadas_al_llm_y_reactivar_las_restaura`, `test_put_llm_desactiva_y_reactiva` |
| RF-L5 | `test_cuota_llm.py::test_put_llm_*_400` |
| RF-L6 | `SelectorModo.test.tsx` |
| RF-L7 | `test_api.py::test_consulta_valida` (conjunto exacto de campos) |
| RNF-L2 | `test_cuota_llm.py::test_get_llm_no_expone_la_clave` |
