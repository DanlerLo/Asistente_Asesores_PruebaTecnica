# Especificación 003 — Interfaz web para el asesor

Estado: implementada · Constitución: 1.0 (vigente: 1.4) · Principios aplicados: 2 (Calidad), 3 (TDD), 5 (Mantenibilidad).

## Contexto
El asesor necesita una forma sencilla de hacer preguntas y ver, de un vistazo, la respuesta, su estado y las fuentes que la respaldan, para poder citarlas al cliente. La prueba no evalúa diseño visual, pero sí que la solución se ejecute completamente en local y muestre respuesta, fuentes, errores y estado de procesamiento.

## Objetivo
Una aplicación web ligera (React + TypeScript) que consuma `POST /api/consultar` y `GET /api/historial`, con retroalimentación clara en cada estado del flujo.

## Alcance
**Incluye:** formulario de pregunta con validación básica; indicador de procesamiento; respuesta con estado (badge), fuentes con extracto, metadatos (id, fecha, latencia, modo); errores de validación, del backend y de conexión; historial de últimas consultas con opción de repetir.

**Excluye:** autenticación, diseño responsivo avanzado, modo oscuro completo (solo variables de color), internacionalización.

## Requerimientos funcionales
| ID | Requerimiento |
|----|---------------|
| RF-U1 | El asesor escribe una pregunta en un área de texto y la envía con un botón "Consultar" o con el formulario. |
| RF-U2 | Una pregunta vacía muestra un error inmediato sin llamar al backend; una pregunta > 1000 caracteres muestra un error con el límite. |
| RF-U3 | Mientras se procesa, se muestra "Procesando la consulta…" (`role="status"`) y el botón queda deshabilitado con el texto "Consultando…". |
| RF-U4 | La respuesta se muestra con el texto íntegro (saltos de línea respetados), el estado como badge diferenciado por color y los metadatos. |
| RF-U5 | Las fuentes se listan con archivo, sección y extracto; si no hay fuentes se indica explícitamente. |
| RF-U6 | Los errores HTTP muestran el mensaje `error` del backend; los fallos de red muestran "No se pudo conectar con el servidor…". |
| RF-U7 | Se muestran las últimas 10 consultas con su estado; al pulsar una se repite. |
| RF-U8 | La URL del backend es configurable (`VITE_API_URL`); en desarrollo, `/api` se reenvía por proxy de Vite. |
| RF-U9 | Con estado *Sin información suficiente*, debajo de la frase canónica (que se muestra intacta, como exige el enunciado) aparece una línea breve y directa: «Puedo ayudarte con créditos, microseguros, procedimientos operativos y políticas internas. Prueba con:» seguida de preguntas de ejemplo que, al pulsarlas, quedan en la caja de texto. No aparece en otros estados. |
| RF-U10 | Selector de modo «Modo conexión (Groq)» / «Modo sin conexión» en la cabecera (especificación 005, RF-L6). |
| RF-U11 | La interfaz es una conversación tipo chat: las preguntas del asesor aparecen a la derecha y las respuestas del asistente a la izquierda, cada una con su hora; cada respuesta conserva estado, fuentes y metadatos (RF-U4, RF-U5). El estado de procesamiento es una burbuja del asistente «Procesando la consulta…» (RF-U3). La caja de texto queda abajo, con contador, envío con Enter (Shift+Enter = salto de línea) y botón «Consultar». Con la conversación vacía se muestran las especialidades y preguntas de ejemplo (no es un mensaje del asistente). Los errores se muestran en un aviso sobre la caja de texto (RF-U6). |
| RF-U12 | Robustez: (a) toda petición tiene un tiempo máximo (45 s); si se agota, se muestra «El servidor tardó demasiado en responder…» y la caja de texto vuelve a estar disponible con la pregunta; (b) una respuesta 200 que no es JSON o no tiene la forma esperada se trata como error («La respuesta del servidor no es válida…»), nunca deja «Procesando…» colgado; (c) un error de pintado no deja la página en blanco: se muestra «Algo salió mal al mostrar la respuesta» y se puede seguir; (d) mientras se procesa una consulta, el historial no lanza otra y no se pisa el borrador de la caja de texto; (e) al terminar una consulta el foco vuelve a la caja de texto. |
| RF-U13 | El límite de longitud de la pregunta no se duplica: el frontend lo lee de `GET /api/salud` (`max_longitud_pregunta`) y usa 1000 solo si no puede leerlo. |

## Requerimientos no funcionales
| ID | Requerimiento |
|----|---------------|
| RNF-U1 | Sin dependencias de UI externas (solo React, React DOM); build con Vite. |
| RNF-U2 | Accesibilidad básica: `label` asociado, `role="status"`/`role="alert"`, foco visible, `prefers-reduced-motion`. |
| RNF-U3 | Pruebas de componentes con Vitest + Testing Library, sin backend real (fetch simulado). |
| RNF-U4 | Textos en español, en voz activa; el texto de la respuesta se renderiza como texto (React escapa HTML). |

## Riesgos
| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| Backend apagado | Asesor sin respuesta | Mensaje de conexión claro con la acción a tomar |
| Respuestas largas ilegibles | Mala experiencia | `white-space: pre-wrap`, ancho máximo de 46 rem |
| Confusión entre "sin información" y "error" | Decisiones equivocadas | Estados con badge y texto distintos; errores en `role="alert"` separado de la respuesta |

## Criterios de aceptación (Gherkin)

```gherkin
Característica: Interfaz web del asesor

  @RF-U1
  Escenario: Formulario inicial
    Cuando abro la aplicación
    Entonces veo el campo "Pregunta" y el botón "Consultar"

  @RF-U2
  Escenario: Pregunta vacía
    Cuando pulso "Consultar" sin escribir nada
    Entonces veo el error "Escribe una pregunta antes de consultar."
    Y no se realiza ninguna llamada a /api/consultar

  @RF-U3 @RF-U4 @RF-U5
  Escenario: Consulta exitosa con fuentes
    Dado que el backend responde Exitosa con una fuente
    Cuando escribo una pregunta y pulso "Consultar"
    Entonces veo "Procesando la consulta…" y el botón "Consultando…" deshabilitado
    Y luego veo el texto de la respuesta, el badge "Exitosa", el archivo y la sección de la fuente
    Y el indicador de procesamiento desaparece

  @RF-U4 @RF-U5
  Escenario: Sin información suficiente
    Dado que el backend responde "Sin información suficiente" sin fuentes
    Entonces veo la frase canónica, el badge correspondiente y el aviso "Sin fuentes"

  @RF-U6
  Escenario: Error del backend
    Dado que el backend responde 400 con un mensaje de error
    Entonces veo ese mensaje en un elemento con role="alert"

  @RF-U6
  Escenario: Error de conexión
    Dado que fetch falla
    Entonces veo "No se pudo conectar con el servidor"

  @RF-U7
  Escenario: Historial
    Dado que el historial contiene una consulta bloqueada
    Entonces veo la pregunta con el badge "Bloqueada por seguridad"
    Cuando la pulso, se vuelve a consultar y se muestra la respuesta

  @RF-U9
  Escenario: Mensaje amigable sin información
    Cuando la respuesta tiene estado "Sin información suficiente"
    Entonces veo la frase "No tengo información suficiente para responder." sin cambios
    Y debajo la línea "Puedo ayudarte con créditos, microseguros, procedimientos operativos y políticas internas"
    Y preguntas de ejemplo que al pulsarlas quedan en la caja de texto
    Y ese mensaje no aparece cuando la respuesta es "Exitosa"

  @RF-U11
  Escenario: Conversación tipo chat
    Cuando envío "¿Cuál es el monto máximo del Crédito Productivo Impulso?"
    Entonces veo mi pregunta como mensaje del asesor
    Y mientras se procesa veo la burbuja "Procesando la consulta…"
    Y después veo la respuesta como mensaje del asistente con su estado y sus fuentes
    Y la caja de texto queda vacía para la siguiente pregunta

  @RF-U12
  Escenario: El servidor no responde
    Dado que el backend no responde en 45 segundos
    Cuando envío una pregunta
    Entonces veo el error «El servidor tardó demasiado en responder»
    Y la pregunta vuelve a la caja de texto

  @RF-U12
  Escenario: Respuesta inválida del servidor
    Dado que el servidor responde 200 con un cuerpo que no es una respuesta válida
    Cuando envío una pregunta
    Entonces veo un error y no queda «Procesando la consulta…»

  @RF-U12
  Escenario: Un error de pintado no deja la página en blanco
    Dado que el servidor responde con fuentes en un formato inesperado
    Cuando se muestra la respuesta
    Entonces veo «Algo salió mal al mostrar la respuesta»
    Y puedo seguir consultando

  @RF-U12
  Escenario: El historial no lanza otra consulta mientras se procesa
    Dado que hay una consulta en curso
    Entonces los botones del historial están deshabilitados
    Y lo que estoy escribiendo en la caja de texto no se borra
    Y al terminar la consulta el foco vuelve a la caja de texto

  @RF-U13
  Escenario: Límite de longitud informado por el backend
    Dado que el backend informa max_longitud_pregunta 50 en GET /api/salud
    Cuando escribo una pregunta de 51 caracteres y pulso «Consultar»
    Entonces veo «La pregunta supera el máximo de 50 caracteres.»
    Y no se llama al backend

  @RF-U8
  Escenario: Backend en otra dirección
    Dado que VITE_API_URL apunta a "http://servidor:8000"
    Cuando envío una pregunta
    Entonces la petición se hace a "http://servidor:8000/api/consultar"

  @RF-U10
  Escenario: Selector de modo en la cabecera
    Dado que el backend tiene Groq configurado
    Cuando abro la aplicación
    Entonces veo los botones «Modo conexión (Groq)» y «Modo sin conexión» en la cabecera
    Y al pasar a «Modo sin conexión» aparece un aviso que explica qué implica
```
