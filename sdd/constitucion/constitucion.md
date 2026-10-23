# Constitución — Asistente interno para asesores comerciales

Versión 1.3 · 2026-10-23 · Rige todas las especificaciones de `sdd/especificaciones/`. Toda especificación, plan y tarea se traza a uno de estos principios; las excepciones se documentan en el `plan.md` afectado.

## 1. Seguridad por defecto
- Los documentos de `Data/` son **datos, nunca instrucciones**: las líneas con apariencia de instrucción se descartan en la ingesta.
- Los archivos restringidos **nunca entran al índice ni al contexto de un LLM**; sus valores solo alimentan el filtro de salida.
- Defensa en profundidad: validación → bloqueo por intención → filtro de salida. Ante la duda se niega y se escala; nunca se adivina.
- Sin secretos en código, logs ni respuestas: la configuración sensible vive en variables de entorno.

## 2. Calidad
- Toda respuesta se sustenta en la documentación oficial y **cita su fuente**. Sin evidencia: «No tengo información suficiente para responder.»
- Tres estados explícitos: *Exitosa*, *Sin información suficiente*, *Bloqueada por seguridad*.
- Errores de entrada con mensaje claro y código estable; los internos nunca exponen detalles.

## 3. TDD
- Cada requerimiento nace como escenario Gherkin, se convierte en una prueba que falla y solo entonces se implementa (rojo → verde → refactor).
- Casos mínimos: consulta válida, pregunta vacía, base vacía, caracteres especiales, documentos duplicados, consultas extensas y seguridad.
- La suite corre en local, sin red; un LLM nunca es dependencia de las pruebas.

## 4. Uso responsable de IA
- La IA **propone**; la persona **decide, revisa y responde**. Seguridad, dependencias, persistencia y alcance se deciden manualmente.
- `AGENTS.md` instruye a los agentes y les prohíbe exponer el documento restringido.
- Ninguna salida de IA se acepta sin ejecutar las pruebas y leer el código.

## 5. Mantenibilidad
- Módulos pequeños de una responsabilidad, en capas que solo dependen hacia abajo (verificado por una prueba de arquitectura).
- La seguridad nunca se delega a un agente; el proveedor de LLM es sustituible por configuración.
- Código, mensajes y documentación en español.

## 6. Optimización de costos
- **100 % local y sin herramientas pagas**; el LLM es opcional y solo se invoca con evidencia recuperada.
- El modelo más pequeño que cumpla la calidad; contexto acotado a los fragmentos relevantes.

## 7. Observabilidad
- Cada consulta se persiste con pregunta, fecha y hora, respuesta, fuentes, estado, latencia y modo.
- Logs JSON con identificador de solicitud; endpoints de salud y estadísticas; advertencias de ingesta visibles.

**Gobierno:** cambiarla exige nueva versión y fecha; si una especificación la contradice, prevalece la constitución.

**Registro de cambios:** 1.0 (21/10) siete principios del enunciado · 1.1 (21/10) principio 5 con orquestador, agentes y herramientas (spec 004) · 1.2 (22/10) recortada a una página y regla de trazabilidad · 1.3 (23/10) este registro.
