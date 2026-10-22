# Tareas 003 — Interfaz web para el asesor

Orden de ejecución; prueba antes que implementación. `[x]` = completada.

- [x] T-201 Crear proyecto Vite + React + TypeScript en `src/frontend` (sin plantilla interactiva: `package.json`, `tsconfig.json`, `vite.config.ts`, `index.html`).
- [x] T-202 Configurar Vitest (jsdom, `@testing-library/jest-dom`, `dir` = `tests/frontend`) y workspace npm en la raíz.
- [x] T-203 Pruebas de `api.ts`: cuerpo JSON, `ErrorApi` para HTTP 4xx/5xx y para fallo de red, historial.
- [x] T-204 Implementar `api.ts` con tipos del contrato.
- [x] T-205 Pruebas de `App`: formulario, pregunta vacía sin llamada, estado de procesamiento y respuesta con fuentes.
- [x] T-206 Implementar `App.tsx`, `FormularioConsulta`, `Respuesta`, `EstadoBadge`, `Fuentes`.
- [x] T-207 Pruebas de errores (backend y conexión) y de "Sin información suficiente".
- [x] T-208 Pruebas de historial y repetición; implementar `Historial` y recarga tras cada consulta.
- [x] T-209 Estilos mínimos con variables (claro/oscuro), foco visible, `prefers-reduced-motion`.
- [x] T-210 Verificar `npm run build` (tsc + vite) y `npm test` en verde.
- [x] T-211 Documentar ejecución local en `README.md`.

## Mejoras futuras
- [ ] T-212 Copiar respuesta/cita al portapapeles con un clic.
- [ ] T-213 Filtro del historial por estado y búsqueda.
- [ ] T-214 Pruebas end-to-end (Playwright) contra el backend real.

## Fase extra — Orientación y modo del LLM (RF-U9, RF-U10)
- [x] T-215 Prueba + componente `Especialidades`: mensaje amigable solo con estado *Sin información suficiente*; la frase canónica no cambia.
- [x] T-216 Selector de modo integrado en `App` (ver especificación 005).
- [x] T-217 Pruebas de la interfaz tipo chat (RF-U11): mensajes del asesor y del asistente, Enter envía y Shift+Enter no, guía inicial; pruebas existentes adaptadas sin perder aserciones.
- [x] T-218 Implementar `Conversacion`, `BurbujaAsistente`, `Compositor` y estilos de chat; recorrido real en el navegador (claro y oscuro).
- [x] T-219 Identidad Banco W: logo en la cabecera (`src/assets/banco-w.png`, placa blanca en modo oscuro), naranja como color principal y turquesa como secundario; contraste WCAG AA verificado en texto, botones y foco; los estados conservan colores semánticos.


## Fase extra — Robustez (RF-U12, hallazgos E1–E4 y E6 de la auditoría)
- [x] T-220 Pruebas (`api.test.ts`, `Robustez.test.tsx`): tiempo agotado → `TIEMPO_AGOTADO`; 200 sin JSON o sin forma válida → `RESPUESTA_INVALIDA`; error de pintado con aviso; historial deshabilitado mientras se procesa sin pisar el borrador; foco de vuelta a la caja de texto.
- [x] T-221 Implementar: `AbortController` de 45 s y validación de forma en `api.ts`, componente `LimiteErrores` (en `main.tsx` y alrededor de la conversación), `Historial` con `deshabilitado` y foco en `Compositor`.
