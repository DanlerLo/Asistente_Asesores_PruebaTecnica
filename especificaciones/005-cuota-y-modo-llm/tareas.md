# Tareas 005 — Cuota de la API gratuita y modo sin conexión

Orden de ejecución; cada implementación va precedida por su prueba (TDD). `[x]` = completada.

## Fase A — Backend
- [x] T-401 Pruebas de `leer_cuota`: cabeceras completas, ausentes y mal formadas; duraciones (`2m59.56s`, `7.66s`, `1h0m0s`).
- [x] T-402 Pruebas: `ProveedorGroq` registra cuota y contador en la respuesta exitosa y en el 429, y sigue degradando al extractivo.
- [x] T-403 Pruebas de `GET /api/llm` y `PUT /api/llm`: sin proveedor, con proveedor, desactivar, reactivar, 400 por tipo inválido y sin proveedor; la clave nunca aparece.
- [x] T-404 Ejecutar y confirmar el fallo.
- [x] T-405 Implementar `CuotaLLM`, `leer_cuota` y el registro en `ProveedorGroq`.
- [x] T-406 Implementar `estado_llm()` y `cambiar_modo_llm()` en el orquestador y los endpoints.

## Fase B — Frontend
- [x] T-407 Pruebas del panel del LLM: sin proveedor, cuota desconocida, «Quedan X de Y», aviso < 10 %, desactivar y activar, fallo de la API.
- [x] T-408 Implementar `obtenerEstadoLlm`, `cambiarModoLlm` y el panel; refrescar tras cada consulta.

## Fase C — Cierre
- [x] T-409 Suite completa y prueba en vivo con Groq.
- [x] T-410 README (endpoints, panel, limitaciones) y Cuestionario (monitoreo de cuota).

## Fase D — Revisión independiente
- [x] T-411 `POST /api/consultar` síncrona: una llamada lenta al LLM no bloquea `PUT /api/llm` (prueba con proveedor lento).
- [x] T-412 Contador y cuota seguros entre hilos; una cuota más vieja no reemplaza una más reciente.
- [x] T-413 Duraciones en µs y ns; `PUT /api/llm` con JSON inválido responde con un mensaje sobre `activo`.
- [x] T-414 El log de fallo del LLM registra solo tipo y código HTTP, porque la URL puede llevar credenciales.
- [x] T-415 Frontend: una respuesta vieja de `GET /api/llm` no pisa el modo recién cambiado; el error se borra al reintentar.
- [x] T-416 Contraste WCAG del badge «Exitosa» y del anillo de foco en modo claro.

## Fase E — Selector de modo y cliente HTTP
- [x] T-417 Reemplazar el panel por un selector compacto «Modo conexión (Groq)» / «Modo sin conexión» con aviso al pasar a sin conexión (RF-L6).
- [x] T-418 `ProveedorGroq` reutiliza un cliente HTTP con pool que se cierra al apagar; `ProveedorLLM` declara `modelo`, `total_llamadas`, `cuota` y `cerrar`; el prompt del sistema se renderiza al primer uso.
