# Especificación 007 — Recuperación semántica local y más contexto para el LLM

Estado: implementada · Constitución: 1.4 · Principios aplicados: 1 (Seguridad por defecto), 2 (Calidad), 3 (TDD), 6 (Optimización de costos).

## Contexto
La recuperación es léxica (BM25 con sinónimos y frases del asesor). Responde bien las 97 preguntas de evaluación, pero esas reglas se ajustaron mirando esos casos. Con 40 preguntas nuevas, escritas antes de esta característica y que no se usan para ajustar nada (`tests/backend/generalizacion.json`), acierta 19 (48 %) y da 4 respuestas equivocadas: cuando la pregunta usa palabras que no están en los documentos ni en los sinónimos («¿qué riesgos cubre el seguro para negocios?»), no encuentra el fragmento. Con Groq activo pasa lo mismo: el LLM entiende la paráfrasis, pero solo ve lo que la recuperación le entregó.

## Objetivo
Que la recuperación del RAG sea híbrida, por palabras y por significado, sin servicios pagos ni red en ejecución, y que el LLM reciba el contexto suficiente para responder paráfrasis, sin perder la regla de no adivinar.

## Alcance
- Incluye: embeddings locales opcionales (`fastembed`, modelo multilingüe), búsqueda híbrida (BM25 + semántica), enrutamiento por similitud, contexto ampliado para Groq, medición de generalización.
- Excluye a propósito: que el modo extractivo responda con una línea elegida por similitud (se midió y aumentaba las respuestas equivocadas, ver ADR-25). Sí puede leer una sección completa cuando la similitud es clara (ADR-27).
- No incluye: base de datos vectorial, reordenamiento (*reranker*), embeddings de un servicio externo.

## Requerimientos funcionales
| ID | Requerimiento |
|----|---------------|
| RF-E1 | Al arrancar, `EMBEDDINGS` vale `local` por defecto: se usa un modelo multilingüe local (`EMBEDDINGS_MODELO`, por defecto `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`) que se descarga solo la primera vez en `EMBEDDINGS_CACHE` (por defecto `storage/modelos`) y después funciona sin red. Con `EMBEDDINGS=none` se usa solo BM25. Otro valor impide arrancar. |
| RF-E2 | Se embebe cada línea de los documentos indexados, con su sección como prefijo; los documentos restringidos nunca se embeben porque no están en el corpus. |
| RF-E3 | Búsqueda híbrida: los fragmentos más parecidos por significado se suman a los de BM25. Si BM25 no encuentra nada y la mejor similitud supera `UMBRAL_SEMANTICO`, la pregunta se enruta al agente de ese documento en vez de al de fuera de dominio. |
| RF-E4 | El modo extractivo nunca responde con una línea elegida por similitud. Si sus reglas léxicas no encuentran respuesta, la similitud puede elegir qué **sección** leer: se devuelve la sección literal y completa, con su cita, solo si su similitud supera `UMBRAL_LECTURA_SEMANTICA` (0,65) y le saca `MARGEN_LECTURA_SEMANTICA` (0,06) a la segunda. Si la pregunta nombra un producto, la sección debe ser de ese producto y tener todos los atributos de ficha pedidos («edad máxima»); si no, se responde la frase canónica. |
| RF-E5 | Con Groq activo, el LLM recibe hasta `LLM_MAX_FRAGMENTOS` fragmentos: los de BM25, los semánticos y los del documento del agente que atiende, sin repetir. |
| RF-E6 | La similitud nunca rescata preguntas bloqueadas, con producto inexistente (RF-13) o de seguimiento sin referente: no enruta ni llama al LLM. |
| RF-E7 | Si el modelo no se puede cargar (sin red en la primera descarga, librería ausente), se registra una advertencia y el servicio sigue con recuperación léxica. |

## Requerimientos no funcionales
| ID | Requerimiento |
|----|---------------|
| RNF-E1 | Sin costo ni red en ejecución: el modelo corre en CPU (ONNX, sin PyTorch) y todo se instala con `pip install -r requirements.txt`. |
| RNF-E2 | Las pruebas no descargan modelos: usan un embebedor de prueba determinista. |
| RNF-E3 | Embeber el corpus al arrancar toma menos de 2 s con el modelo en caché. |
| RNF-E4 | Ninguna respuesta del banco de 293 preguntas empeora; las que cambian se revisan a mano. |

## Riesgos
| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| Una sección parecida pero equivocada responde con seguridad | Respuesta falsa | Nunca una línea suelta; una sección solo con umbral y margen, y nunca la ficha de un producto nombrado que no tiene el dato (RF-E4); con LLM, el modelo decide si los fragmentos responden |
| La primera ejecución necesita red para descargar el modelo | El evaluador no puede usarlo sin internet | Degradación a léxico con una advertencia (RF-E7); `EMBEDDINGS=none` lo desactiva |
| Más contexto consume más cuota de Groq | Se agota antes el plan gratuito | Tope `LLM_MAX_FRAGMENTOS`; sin llamadas en bloqueos ni fuera de dominio |
| Mejorar solo las preguntas conocidas | Falsa sensación de calidad | Conjunto de generalización escrito antes y no usado para ajustar |

## Criterios de aceptación (Gherkin)
```gherkin
Característica: Recuperación semántica local

  Antecedentes:
    Dado que la base documental contiene los archivos de Data/
    Y que EMBEDDINGS vale "local"

  @RF-E3 @RF-E5
  Escenario: Paráfrasis sin palabras en común, con Groq
    Dado que el modo conexión (Groq) está activo
    Cuando envío la pregunta "¿Qué riesgos cubre el seguro para negocios?"
    Entonces el LLM recibe el fragmento "Negocio Seguro" con «Coberturas: Incendio; Inundación; Daños accidentales»

  @RF-E4
  Escenario: Con similitud clara se lee la sección completa
    Dado que el modo sin conexión está activo
    Cuando envío la pregunta "¿Cuál es la tasa del crédito para estudiantes?"
    Entonces la respuesta es la sección "Crédito Educativo Avanza > Condiciones" completa, con su cita
    Y contiene "15,6 %"

  @RF-E4
  Escenario: Un producto nombrado sin el dato no se rescata por parecido
    Dado que el modo sin conexión está activo
    Cuando envío la pregunta "¿Qué edad máxima tiene Negocio Seguro?"
    Entonces la respuesta es exactamente "No tengo información suficiente para responder."

  @RF-E6
  Escenario: Producto inexistente no se responde por parecido
    Cuando envío la pregunta "¿Cuál es la tasa del crédito de vivienda?"
    Entonces la respuesta es exactamente "No tengo información suficiente para responder."

  @RF-E2
  Escenario: Lo restringido no se embebe
    Cuando se construye el índice semántico
    Entonces ninguna línea indexada contiene un valor del documento restringido

  @RF-E5
  Escenario: Groq recibe más contexto
    Dado que el modo conexión (Groq) está activo
    Cuando envío una pregunta que atiende el agente de microseguros
    Entonces el LLM recibe los fragmentos de BM25, los semánticos y los del Portafolio de Microseguros
    Y nunca más de LLM_MAX_FRAGMENTOS

  @RF-E7
  Escenario: El modelo no está disponible
    Dado que el modelo no se puede cargar
    Cuando arranca el servicio
    Entonces se registra una advertencia
    Y las consultas se responden con recuperación léxica

  @RF-E1
  Escenario: Embeddings activados por defecto
    Dado que EMBEDDINGS no está definido
    Cuando arranca el servicio
    Entonces se carga el modelo local de embeddings

  @RF-E1
  Escenario: Embeddings desactivados a propósito
    Dado que EMBEDDINGS vale "none"
    Cuando arranca el servicio
    Entonces no se carga ningún modelo
```
