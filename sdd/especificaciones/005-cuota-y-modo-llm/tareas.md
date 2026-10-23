# Tareas 005 — Cuota de la API gratuita y modo sin conexión

Orden de ejecución; prueba antes que implementación. `[x]` = completada.

## Fase A — Backend
- [x] T-301 Pruebas de `leer_cuota`: cabeceras completas, ausentes, mal formadas, duraciones (`2m59.56s`, `7.66s`, `1h0m0s`).
- [x] T-302 Pruebas: `ProveedorGroq` registra cuota y contador en respuesta exitosa y en 429 (y sigue degradando al extractivo).
- [x] T-303 Pruebas de `GET /api/llm` y `PUT /api/llm`: estado sin proveedor, con proveedor, desactivar, reactivar, 400 por tipo inválido y por proveedor no configurado, la clave nunca aparece.
- [x] T-304 Ejecutar y confirmar el fallo.
- [x] T-305 Implementar `CuotaLLM`, `leer_cuota`, registro en `ProveedorGroq`.
- [x] T-306 Implementar `Orquestador.estado_llm()` / `cambiar_modo_llm()` y los endpoints.

## Fase B — Frontend
- [x] T-307 Pruebas de `PanelLLM` (Vitest): sin proveedor, cuota desconocida, "Quedan X de Y", aviso < 10 %, desactivar/activar, fallo de la API.
- [x] T-308 Implementar `obtenerEstadoLlm`, `cambiarModoLlm` y `PanelLLM`; refrescar tras cada consulta.

## Fase C — Cierre
- [x] T-309 Suite completa (`pytest`, `npm test`, `npm run build`) y prueba en vivo con Groq.
- [x] T-310 README (endpoints, panel, limitaciones) y Cuestionario (monitoreo de cuota).

## Fase D — Revisión adversarial (10 hallazgos confirmados, 1 descartado)
- [x] T-314 `POST /api/consultar` síncrona (hilo aparte): una llamada lenta al LLM ya no bloquea `PUT /api/llm` (prueba con proveedor lento).
- [x] T-315 Contador y cuota seguros entre hilos; una cuota más vieja no reemplaza una más reciente.
- [x] T-316 Duraciones en µs/ns; `PUT /api/llm` con JSON inválido responde con un mensaje sobre `activo`.
- [x] T-317 El log de fallo del LLM registra solo tipo y código HTTP (la URL puede llevar credenciales); `httpx` en WARNING.
- [x] T-318 Frontend: una respuesta vieja de `GET /api/llm` no pisa el modo recién cambiado; el error de cambio de modo se borra al reintentar con éxito; recarga sin «60 min».
- [x] T-319 Contraste WCAG: badge «Exitosa» (5,08:1) y anillo de foco (≥ 4,28:1) en modo claro.

## Fase E — Rediseño del selector
- [x] T-320 El panel pasa a un selector compacto «Modo conexión (Groq)» / «Modo sin conexión» con pop-up explicativo al pasar a sin conexión (RF-L6 actualizado); `SelectorModo.test.tsx` reemplaza a `PanelLLM.test.tsx` con la misma cobertura más el pop-up.

## Pendientes / mejoras futuras
- [ ] T-311 Autenticación por rol para el botón de modo (producción).
- [ ] T-312 Persistir el modo elegido (requiere decidir dónde, sin editar `.env`).
- [ ] T-313 Pasar automáticamente a modo sin conexión cuando la cuota llegue a 0 hasta la hora de recarga.
- [x] T-321 Hallazgo F4: `ProveedorGroq` reutiliza un `ClienteHttpLLM` (pool y keep-alive) que se cierra al apagar el servicio; `ProveedorLLM` declara `modelo`, `total_llamadas`, `cuota` y `cerrar` (el orquestador ya no usa `getattr`); el prompt del sistema se renderiza al primer uso (`instrucciones_sistema()`).
