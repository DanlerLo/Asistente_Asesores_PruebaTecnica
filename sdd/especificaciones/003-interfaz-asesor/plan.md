# Plan 003 — Interfaz web para el asesor

## Arquitectura propuesta

```
src/frontend/
├── index.html
├── vite.config.ts        (proxy /api → backend; Vitest con jsdom; pruebas en tests/frontend)
└── src/
    ├── main.tsx          (montaje)
    ├── App.tsx           (estado: procesando, resultado, error, historial)
    ├── api.ts            (consultar, obtenerHistorial, ErrorApi)
    ├── styles.css        (tokens de color claro/oscuro, sin framework)
    └── components/
        ├── FormularioConsulta.tsx
        ├── Respuesta.tsx  ─► EstadoBadge.tsx + Fuentes.tsx
        └── Historial.tsx
```

`App` concentra el estado y delega la presentación a componentes sin estado. `api.ts` aísla `fetch` y convierte toda falla en `ErrorApi` con mensaje legible, de modo que la UI no conoce detalles HTTP.

## Componentes
| Componente | Responsabilidad |
|------------|-----------------|
| `api.ts` | Contrato tipado (`RespuestaConsulta`, `Fuente`, `Estado`), base URL configurable, errores uniformes |
| `App.tsx` | Validación previa (vacía, longitud), orquestación de la consulta, recarga del historial |
| `FormularioConsulta` | Área de texto, contador, ejemplos, botón con estado de carga |
| `Respuesta` | Texto íntegro, badge, fuentes, metadatos |
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
