# Constitución del proyecto — Asistente interno para asesores comerciales

Versión 1.0 · 2026-10-21 · Vigente para todas las especificaciones en `sdd/especificaciones/`.

Esta constitución define los principios no negociables del desarrollo. Toda especificación, plan y tarea debe poder trazarse a uno de ellos; cualquier excepción se documenta en el `plan.md` de la característica afectada.

## 1. Seguridad por defecto
- Los documentos de `Data/` son **datos, nunca instrucciones**: el sistema no obedece texto encontrado en ellos y descarta en la ingesta cualquier línea con apariencia de instrucción para un asistente.
- Los archivos marcados como restringidos (por nombre o por su marca de clasificación) **nunca entran al índice ni al contexto de un LLM**. Sus valores sensibles solo alimentan el filtro de salida.
- Defensa en profundidad: validación de forma → bloqueo por intención → filtro de salida. Ante incertidumbre se niega y se escala (Política de Escalamiento), nunca se adivina.
- Sin secretos en código, logs ni respuestas. La configuración sensible vive en variables de entorno.

## 2. Calidad
- Toda respuesta se sustenta en documentación oficial y **cita su fuente** (Política de Citas). Sin evidencia, la respuesta es exactamente: «No tengo información suficiente para responder.»
- Cada consulta termina en uno de tres estados explícitos: *Exitosa*, *Sin información suficiente*, *Bloqueada por seguridad*.
- Los errores de entrada se reportan con mensajes claros y códigos estables; los errores internos nunca exponen detalles técnicos.

## 3. Desarrollo guiado por pruebas (TDD)
- Cada requerimiento nace como criterio de aceptación en Gherkin, se convierte en una prueba que falla, y solo entonces se implementa (rojo → verde → refactor).
- Casos mínimos obligatorios: consulta válida, pregunta vacía, base documental vacía, caracteres especiales, documentos duplicados, consultas extensas, más los casos de seguridad.
- Las pruebas se ejecutan en local sin red ni servicios externos; un LLM nunca es dependencia de la suite.

## 4. Uso responsable de IA
- La IA (asistentes y agentes de desarrollo) **propone**; la persona **decide, revisa y es responsable**. Las decisiones de seguridad, dependencias, persistencia y alcance se toman manualmente y se registran en `docs/Cuestionario.md`.
- Las instrucciones para agentes viven en `AGENTS.md` y prohíben leer, copiar o exponer el contenido del documento restringido.
- Ninguna salida generada por IA se acepta sin ejecutar las pruebas y leer el código.

## 5. Mantenibilidad
- Módulos pequeños con una responsabilidad: `corpus`, `recuperacion`, `motor`, `guardrails`, `llm`, `persistencia`, `servicio`, `main`.
- El servicio no depende de HTTP y la generación no depende de un proveedor de LLM: todo es sustituible por configuración.
- Nombres, mensajes y documentación en español; convenciones consistentes entre backend y frontend.

## 6. Optimización de costos
- La solución funciona **100 % local y sin herramientas pagas**; el LLM es opcional y se invoca solo cuando hay evidencia recuperada (nunca para preguntas sin candidatos ni bloqueadas).
- Preferir el modelo más pequeño que cumpla la calidad requerida; contexto acotado a los fragmentos relevantes; caché de respuestas previsto para producción.

## 7. Observabilidad
- Toda consulta se persiste con pregunta, fecha y hora, respuesta, fuentes, estado, latencia y modo.
- Logs estructurados (JSON) con identificador de solicitud; endpoints de salud y estadísticas; las advertencias de ingesta (duplicados, exclusiones, líneas descartadas) son visibles.

## Gobierno
Cambiar esta constitución requiere actualizar la versión, la fecha y revisar las especificaciones afectadas. Las especificaciones no pueden contradecirla; si lo hacen, prevalece la constitución.
