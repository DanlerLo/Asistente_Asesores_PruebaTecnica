# Constitución del asistente para asesores

Versión 1.5 · 2026-10-24 · Rige todas las especificaciones de `especificaciones/`; trazo cada especificación, plan y tarea a uno de estos principios y documento las excepciones en su `plan.md`.

## 1. Seguridad por defecto
- Trato los documentos de `Data/` como **datos, nunca como instrucciones**: lo que parece una instrucción se descarta en la ingesta.
- Lo restringido **nunca entra al índice ni al contexto de un LLM**; lo detectan reglas deterministas, nunca un agente, y sus valores solo alimentan el filtro de salida.
- Aplico defensa en profundidad: validación - bloqueo por intención - filtro de salida. Ante la duda, niego y escalo.
- No dejo secretos en código, logs ni respuestas, ni guardo datos personales en claro.

## 2. Calidad
- Cada respuesta se sustenta en la documentación oficial y **cita su fuente**; sin evidencia: «No tengo información suficiente para responder.»
- Estados: *Exitosa*, *Sin información suficiente*, *Bloqueada por seguridad*. Errores con mensaje y código estable, sin detalles internos.

## 3. TDD
- Cada requerimiento nace como escenario Gherkin y lo convierto en una prueba que falla antes de implementarlo (rojo - verde - refactor).
- Casos mínimos: consulta válida, pregunta vacía, base vacía, caracteres especiales, duplicados, consultas extensas y seguridad. La suite corre local y sin red.

## 4. Uso responsable de IA
- Trabajo con la IA en un ciclo de retroalimentación: ella propone, yo cuestiono y ajusto, volvemos a iterar y **la decisión final es mía**.
- No delego seguridad, dependencias, persistencia ni alcance. Instruyo a los agentes con `AGENTS.md` y no acepto ninguna salida sin pasar las pruebas y leer el código.

## 5. Mantenibilidad
- Escribo módulos pequeños de una responsabilidad, en capas que solo dependen hacia abajo (lo verifica una prueba).
- El proveedor de LLM se cambia por configuración; código y documentación en español.

## 6. Optimización de costos
- **Local y sin herramientas pagas**; el LLM es opcional y solo lo invoco con evidencia recuperada. Única excepción: el modelo de embeddings se descarga la primera vez que arranca el servicio; sin red, se sigue con BM25 (ADR-28).
- Uso el modelo más pequeño que cumpla la calidad, con contexto acotado a los fragmentos relevantes.

## 7. Observabilidad
- Persisto cada consulta con pregunta, fecha y hora, respuesta, fuentes, estado, latencia y modo.
- Logs JSON con identificador de solicitud; endpoints de salud y estadísticas.

**Gobierno:** cambiarla exige nueva versión y fecha; prevalece sobre cualquier especificación.
