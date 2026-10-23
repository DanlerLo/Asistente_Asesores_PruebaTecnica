# Plan 003 — Interfaz web para el asesor

## Arquitectura propuesta

```
src/frontend/
├── index.html
├── vite.config.ts        (proxy /api → backend; Vitest con jsdom; pruebas en tests/frontend)
└── src/
    ├── main.tsx          (montaje)
    ├── App.tsx           (estado: turnos de la conversación, texto, error, historial, modo del LLM)
    ├── api.ts            (consultar, obtenerHistorial, obtenerEstadoLlm, cambiarModoLlm, ErrorApi)
    ├── styles.css        (tokens de color claro/oscuro con la paleta del Banco W, sin framework)
    └── components/
        ├── Conversacion.tsx  ─► BurbujaAsistente.tsx ─► EstadoBadge + Fuentes + Especialidades
        ├── Compositor.tsx    (caja de texto del chat)
        ├── SelectorModo.tsx  (Modo conexión / Modo sin conexión, cuota y pop-up)
        └── Historial.tsx
```

`App` concentra el estado y delega la presentación a componentes sin estado. `api.ts` aísla `fetch` y convierte toda falla en `ErrorApi` con mensaje legible, de modo que la UI no conoce detalles HTTP.

## Componentes
| Componente | Responsabilidad |
|------------|-----------------|
| `api.ts` | Contrato tipado (`RespuestaConsulta`, `Fuente`, `Estado`), base URL configurable, errores uniformes |
| `App.tsx` | Validación previa (vacía, longitud), turnos de la conversación y su contexto, recarga del historial y del modo |
| `Conversacion` | Chat (`role="log"`): mensajes del asesor a la derecha, del asistente a la izquierda; burbuja «Procesando la consulta…»; guía inicial con ejemplos |
| `BurbujaAsistente` | Texto íntegro, badge, fuentes, especialidades (sin información), metadatos y hora |
| `Compositor` | Caja de texto con contador; Enter envía, Shift+Enter salto de línea; botón «Consultar» con estado de carga |
| `SelectorModo` | «Modo conexión (Groq)» / «Modo sin conexión» (`aria-pressed`), cuota en pequeño y pop-up del modo sin conexión |
| `EstadoBadge` | Mapeo estado → clase de color |
| `Fuentes` | Lista ordenada con archivo › sección y extracto; aviso de "Sin fuentes" |
| `Historial` | Últimas consultas; repetir con un clic |

## Decisiones
- **ADR-U1 Sin librería de componentes ni gestor de estado**: el flujo es lineal y `useState` basta; menos dependencias y menor tiempo de instalación para el evaluador.
- **ADR-U2 Proxy de Vite en desarrollo** (`/api` → `http://localhost:8000`): evita configurar CORS/URLs en local; `VITE_API_URL` permite apuntar a otro host.
- **ADR-U3 Pruebas en `tests/frontend/`** para respetar la estructura pedida; el workspace npm en la raíz permite que resuelvan `node_modules`.
- **ADR-U4 Respuesta en `<pre>` con `pre-wrap`**: conserva el formato del motor extractivo (listas y cita final) sin interpretar HTML.

## Estrategia de pruebas
| Archivo | Cubre |
|---------|-------|
| `tests/frontend/api.test.ts` | solicitud JSON, mapeo de errores HTTP y de red, historial |
| `tests/frontend/App.test.tsx` | formulario, validación sin llamada, estado de procesamiento, respuesta + badge + fuentes, sin información, error del backend, error de conexión, historial y repetición |
| `tests/frontend/Robustez.test.tsx` | respuesta inválida, error de pintado, historial bloqueado mientras se procesa, foco |
| `tests/frontend/SelectorModo.test.tsx` | selector de modo, cuota, pop-up de modo sin conexión, fallos de `/api/llm` |
| `tests/frontend/Conversacion.test.tsx` | contexto enviado al backend, «Nueva conversación» |

Ejecución: `npm test` en la raíz (Vitest + jsdom, sin backend). Verificación de tipos y build: `npm run build`.

## Trazabilidad
| RF | Pruebas |
|----|---------|
| RF-U1 | `muestra el formulario de consulta` |
| RF-U2 | `rechaza una pregunta vacía sin llamar al backend` |
| RF-U3, RF-U4, RF-U5 | `muestra el estado de procesamiento, la respuesta, el estado y las fuentes`, `muestra el estado "Sin información suficiente"…` |
| RF-U6 | `muestra el error devuelto por el backend`, `muestra un error de conexión…`, `api.test.ts` |
| RF-U7 | `muestra el historial y permite repetir una consulta` |
| RF-U8 | `vite.config.ts` (proxy) y `api.ts` (`VITE_API_URL`) |
| RF-U9 | `App.test.tsx`: `muestra el estado "Sin información suficiente"…` (frase canónica intacta + especialidades), `no muestra las especialidades cuando la respuesta es exitosa` |
| RF-U10 | `SelectorModo.test.tsx` (9 pruebas: modo activo y cuota, aviso < 10 %, pop-up sin conexión, sin proveedor, fallo de `/api/llm`, respuestas viejas) |
| RF-U11 | `App.test.tsx`: `muestra el intercambio como chat…`, `Shift+Enter agrega un salto de línea sin enviar`; `Conversacion.test.tsx` (memoria de conversación, especificación 006) |
| RF-U12 | `api.test.ts` (`api: robustez`), `Robustez.test.tsx` (respuesta inválida, límite de errores, historial deshabilitado, foco) |
| RF-U13 | `App.test.tsx`: `usa el límite de longitud que informa el backend (RF-U13)`; `test_api.py::test_salud` |
| RNF-U1 | `package.json` del frontend: solo React y React DOM como dependencias de ejecución |
| RNF-U2 | pruebas que localizan por `label` y `role` (`status`, `alert`, `log`); foco verificado en `Robustez.test.tsx` |
| RNF-U3 | todas las pruebas de `tests/frontend/` simulan `fetch`; no levantan backend |
| RNF-U4 | `App.test.tsx`: `muestra caracteres especiales como texto literal, sin interpretarlos como HTML` |
