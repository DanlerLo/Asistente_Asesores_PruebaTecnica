# Tareas 003 — Interfaz web para el asesor

Orden de ejecución; cada implementación va precedida por su prueba (TDD). `[x]` = completada.

## Fase A — Base
- [x] T-201 Crear el proyecto Vite + React + TypeScript en `src/frontend` (`package.json`, `tsconfig.json`, `vite.config.ts`, `index.html`).
- [x] T-202 Configurar Vitest (jsdom, `@testing-library/jest-dom`, pruebas en `tests/frontend`) y el workspace npm en la raíz.

## Fase B — Consulta, respuesta y errores (RF-U1 a RF-U8)
- [x] T-203 Pruebas de `api.ts`: cuerpo JSON, `ErrorApi` para HTTP 4xx/5xx y para fallo de red, historial.
- [x] T-204 Implementar `api.ts` con los tipos del contrato.
- [x] T-205 Pruebas de `App`: formulario, pregunta vacía sin llamada, estado de procesamiento, respuesta con fuentes.
- [x] T-206 Implementar `App.tsx`, `EstadoBadge` y `Fuentes`.
- [x] T-207 Pruebas de error del backend, error de conexión y «Sin información suficiente».
- [x] T-208 Pruebas e implementación del historial con repetición de consultas.

## Fase C — Estilo y verificación
- [x] T-209 Estilos con variables (claro y oscuro), foco visible y `prefers-reduced-motion`.
- [x] T-210 Verificar `npm run build` (tsc + vite) y `npm test` en verde.
- [x] T-211 Documentar la ejecución local en `README.md`.

## Fase D — Orientación y chat (RF-U9 a RF-U11)
- [x] T-212 Prueba e implementación de `Especialidades`: mensaje de orientación solo con *Sin información suficiente*, sin cambiar la frase canónica.
- [x] T-213 Integrar el selector de modo en la cabecera (especificación 005).
- [x] T-214 Pruebas de la interfaz tipo chat: mensajes del asesor y del asistente, Enter envía y Shift+Enter no, guía inicial.
- [x] T-215 Implementar `Conversacion`, `BurbujaAsistente` y `Compositor`; recorrido real en el navegador en modo claro y oscuro.
- [x] T-216 Paleta del banco con contraste WCAG AA verificado en texto, botones y foco; los estados conservan colores semánticos.

## Fase E — Robustez (RF-U12, RF-U13)
- [x] T-217 Pruebas de `api.ts`: tiempo agotado - `TIEMPO_AGOTADO`; 200 sin JSON o sin forma válida - `RESPUESTA_INVALIDA`.
- [x] T-218 Implementar el `AbortController` de 45 s y la validación de la forma de la respuesta.
- [x] T-219 Pruebas: error de pintado con aviso, historial deshabilitado mientras se procesa sin pisar el borrador, foco de vuelta a la caja de texto.
- [x] T-220 Implementar `LimiteErrores`, el historial deshabilitado y el foco en `Compositor`.
- [x] T-221 Leer el límite de longitud de `GET /api/salud` en lugar de duplicarlo (RF-U13).
