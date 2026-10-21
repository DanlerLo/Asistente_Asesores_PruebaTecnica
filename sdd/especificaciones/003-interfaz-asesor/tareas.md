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
