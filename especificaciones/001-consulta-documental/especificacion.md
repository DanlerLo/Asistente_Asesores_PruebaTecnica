# Especificación 001 — Consulta documental con citación de fuentes

Estado: implementada · Constitución: 1.0 (vigente: 1.5) · Principios aplicados: 2 (Calidad), 3 (TDD), 5, 6, 7.

## Contexto
Los asesores comerciales atienden clientes en oficina y por teléfono y necesitan respuestas rápidas y confiables sobre productos de crédito, microseguros, procedimientos operativos y políticas internas. Hoy consultan documentos Markdown dispersos (`Data/`). La Política de Transparencia exige que toda respuesta esté sustentada en documentación oficial y la Política de Citas exige que los asistentes digitales indiquen la fuente utilizada.

## Objetivo
Exponer un servicio `POST /api/consultar` que reciba una pregunta en lenguaje natural, la responda **únicamente** con información encontrada en la base documental, cite las fuentes usadas y registre la consulta con su estado.

## Alcance
**Incluye:** carga y fragmentación de `Data/*.md`; recuperación léxica; respuesta extractiva determinista; capa LLM opcional; persistencia de consultas; endpoints auxiliares de historial, estadísticas y salud.

**Excluye:** autenticación de usuarios, gestión de documentos vía API, embeddings/RAG vectorial (ver `docs/Cuestionario.md`), interfaz (característica 003), reglas de seguridad (característica 002).

## Requerimientos funcionales
| ID | Requerimiento |
|----|---------------|
| RF-01 | `POST /api/consultar` acepta `{"pregunta": string}` y responde `{"respuesta", "fuentes", "estado", "id", "fecha_hora", "latencia_ms", "modo"}`. |
| RF-02 | La base documental se carga desde `DATA_DIR` al iniciar; cada documento se divide en fragmentos por encabezado, normalizando tablas (`Monto máximo: $50.000.000`), etiquetas y listas. |
| RF-03 | La respuesta se construye solo con líneas de los fragmentos recuperados; nunca se genera un dato que no esté en el documento. |
| RF-04 | Si la pregunta nombra un producto o sección, la respuesta proviene exclusivamente de esa entidad (no se responde con datos de otro producto). |
| RF-05 | Sin evidencia suficiente, la respuesta es exactamente «No tengo información suficiente para responder.», con `fuentes: []` y estado *Sin información suficiente*. |
| RF-06 | Entradas inválidas (vacía, no textual, > `MAX_LONGITUD_PREGUNTA`, caracteres de control) devuelven HTTP 400 con `{"error", "codigo"}` y no se registran como consultas. |
| RF-07 | Documentos con contenido idéntico se indexan una sola vez; la fuente no se duplica. |
| RF-08 | Con la base documental vacía o inexistente el servicio arranca, registra una advertencia y responde RF-05 a toda pregunta. |
| RF-09 | Cada consulta atendida se persiste con pregunta, fecha y hora (UTC ISO 8601), respuesta, fuentes (JSON), estado, latencia y modo. |
| RF-10 | `GET /api/historial`, `GET /api/estadisticas` y `GET /api/salud` exponen las consultas recientes, conteos por estado/latencias y el estado del corpus. |
| RF-11 | Con `LLM_PROVIDER=groq` (único proveedor) y `GROQ_API_KEY` configurada, el LLM redacta la respuesta a partir de los fragmentos recuperados; ante cualquier fallo (red, cuota, respuesta vacía) se degrada al motor extractivo. El modo por defecto sigue siendo `none` (sin red). Si `LLM_PROVIDER` está vacío, tiene un valor desconocido o es `groq` sin clave, el backend arranca en modo sin conexión y registra una advertencia que nombra la variable. |
| RF-12 | Si el fragmento mejor puntuado trata lo que nombra la pregunta (p. ej. «Gestión de PQR») pero no responde el atributo pedido, el motor extractivo no recurre a otro fragmento que no mencione ninguno de los términos de esa sección (los títulos con forma de pregunta y las palabras de categoría no cuentan). La regla nunca descarta el fragmento principal. Ante la duda responde RF-05. |
| RF-13 | Si la pregunta nombra un producto que no existe en la base («crédito hipotecario», «Seguro Exequial Plus», «microseguro de mascotas») o pide un atributo inexistente de un documento («salario del asesor»), responde RF-05 en lugar de contestar con datos de otro producto. Se detecta con el vocabulario indexado: una palabra desconocida justo después de «crédito/seguro/microseguro/póliza/préstamo» (salvo tras «qué/cuál», donde sigue un verbo), o preguntas cuyas únicas palabras conocidas son el nombre de un documento. |
| RF-14 | El vocabulario del asesor se traduce al de los documentos en preguntas y documentos por igual («cubre/incluye/ampara» - cobertura, «cuesta/vale/mensualidad» - prima, «carencia» - gracia, «queja/petición» - PQR, «papeles» - requisitos, «más bajo/menor» - mínimo, «más alto/largo» - máximo…); los errores de tipeo leves se corrigen contra el vocabulario del corpus (misma longitud ± 1, similitud ≥ 0,84, nunca conjugaciones ni palabras de categoría). |
| RF-15 | Si la pregunta nombra un producto, quedan fuera los demás productos (RF-04), pero las secciones generales, procedimientos y preguntas frecuentes siguen respondiendo («¿qué exclusiones tiene Vida Protegida?» - Exclusiones generales). Una comparación conserva los dos productos nombrados; dos subsecciones del mismo producto se responden juntas si la segunda aporta lo pedido. |
| RF-16 | Sin producto nombrado, el motor no elige uno al azar: si otro producto responde lo mismo, no responde con ninguno (el agente de dominio lista por producto, RF-O9). Una pregunta frecuente solo responde si su título comparte 2+ términos con la pregunta, y con un único término útil solo responde la sección que ese término nombra (no «abonos a capital» para «la capital de Francia»). |
| RF-17 | Cada respuesta lleva `x-request-id`: se respeta el recibido si cumple `[A-Za-z0-9._-]{1,64}`; si no, se genera uno. Todos los logs emitidos al atender la solicitud incluyen `request_id`, también los errores 500. |
| RF-18 | `GET /api/consultas/{id}` acepta solo dígitos ASCII (`²` o `٣` - 400 `ID_INVALIDO`, nunca 500); `GET /api/historial?limite=` fuera de 1..200 o no numérico - 400 `SOLICITUD_INVALIDA` con un mensaje que nombra el parámetro. |
| RF-19 | Una configuración fuera de rango (`TOP_K` < 1, `MAX_LONGITUD_PREGUNTA` < 1, `UMBRAL_COBERTURA` fuera de (0, 1], `LLM_TIMEOUT_SEGUNDOS` ≤ 0 o un valor no numérico) impide arrancar con un mensaje que nombra la variable. |
| RF-20 | El parser de Markdown tolera BOM al inicio del archivo, conserva los comparadores `<`/`>` (solo elimina etiquetas HTML reales), reconoce etiquetas que contienen «:» («Atención en oficinas (8:00 a 17:00):») y, en tablas de 3 o más columnas, nombra cada valor con su cabecera («Impulso: Plazo mínimo: 6 meses; Plazo máximo: 36 meses»). |
| RF-21 | Una consulta bloqueada cita las políticas que respaldan el bloqueo (*Manual › Información Sensible*, *Políticas › Escalamiento*) **solo si existen en el corpus**; si no, `fuentes` es `[]` y el texto no cita archivos. `LOG_LEVEL` es parte de la configuración validada. El esquema OpenAPI documenta `pregunta` como texto obligatorio. |
| RF-22 | Frases del asesor y preguntas frecuentes: (a) frases coloquiales se traducen al término del documento («hasta cuánta plata prestan» - monto máximo, «cuánto hay que pagar al mes» - prima, «tiempo para pagar» - plazo, «entregan el dinero» - desembolso, «cada cuánto» - periodicidad, días de la semana - horario); (b) «cliente» es contexto del asesor, no un atributo pedido; (c) una pregunta frecuente cuyo título completo está en la pregunta responde primero y entera, y un título de pregunta frecuente nunca se considera nombrado a medias; (d) una subsección corta (≤ 3 líneas) de un producto nombrado responde entera si menciona lo pedido. |
| RF-23 | Una sección que es una lista (requisitos, pasos, canales, coberturas) se responde completa: si alguno de sus elementos responde la pregunta, se devuelven todos. Solo las tablas de atributos (monto, plazo, tasa) se filtran por línea. |

## Requerimientos no funcionales
| ID | Requerimiento |
|----|---------------|
| RNF-01 | Ejecución local sin servicios pagos. En el modo por defecto, la única conexión es la descarga del modelo de embeddings la primera vez que arranca (sin red, se usa solo BM25). |
| RNF-02 | Latencia p95 < 100 ms en modo extractivo con el corpus de ejemplo (≈ 50 fragmentos). |
| RNF-03 | Determinismo: misma pregunta y mismo corpus ⇒ misma respuesta (modo extractivo). |
| RNF-04 | Suite de pruebas ejecutable sin red en < 5 s. |
| RNF-05 | Todo mensaje visible para el asesor en español. |
| RNF-06 | Logs estructurados JSON con `request_id`, estado, modo y latencia. |

## Riesgos
| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| Emparejamiento léxico falla con sinónimos o preguntas muy coloquiales | Respuestas *Sin información* innecesarias | Stemming en español, mapa de sinónimos, capa LLM opcional, FAQ en `Data/` |
| Responder con datos de un producto distinto al preguntado | Información incorrecta al cliente | Bloqueo por entidad (RF-04) + selección de líneas por atributo + prueba `test_no_responde_con_datos_de_otro_producto` |
| Falsos positivos por una sola palabra común ("capital") | Respuesta irrelevante | Mínimo dos términos coincidentes en preguntas de dos o más términos |
| Documentos mal formateados | Fragmentos pobres | Normalizador tolerante (tablas, etiquetas, listas) y advertencias de ingesta en `/api/salud` |
| LLM inventa datos | Respuesta no trazable | Prompt restringido a fragmentos, temperatura 0, filtro de salida, fallback extractivo |
| Coincidencia léxica con otro tema («válido» ≈ «Validación documental») | Dato de otro producto o procedimiento | RF-12: término distintivo obligatorio + prueba con la paráfrasis real |
| Proveedor externo (Groq) recibe datos | Exposición de información | Se envían fragmentos de documentos públicos (el restringido nunca entra al índice) **y la pregunta del asesor tal cual**: el asesor no debe escribir datos personales del cliente; desactivado por defecto; la clave vive en `.env` (en `.gitignore`). Enmascarar datos personales antes de enviar es una mejora pendiente que requiere decisión humana |

## Criterios de aceptación (Gherkin)

```gherkin
Característica: Consulta documental con citación de fuentes

  Antecedentes:
    Dado que la base documental contiene los archivos de Data/

  @RF-01 @RF-02 @RF-03
  Escenario: Consulta válida con respuesta exitosa
    Cuando envío POST /api/consultar con la pregunta "¿Cuál es el monto máximo del Crédito Productivo Impulso?"
    Entonces el código HTTP es 200
    Y el estado es "Exitosa"
    Y la respuesta contiene "$50.000.000"
    Y la respuesta menciona la fuente "Productos de Crédito.md"
    Y fuentes[0].seccion es "Crédito Productivo Impulso > Condiciones"

  @RF-05
  Escenario: Pregunta sin información en los documentos
    Cuando envío la pregunta "¿Cuál es la capital de Francia?"
    Entonces el estado es "Sin información suficiente"
    Y la respuesta es exactamente "No tengo información suficiente para responder."
    Y la lista de fuentes está vacía

  @RF-04 @RF-05
  Escenario: Atributo inexistente para el producto nombrado
    Cuando envío la pregunta "¿Cuál es el periodo de gracia del Crédito Productivo Impulso?"
    Entonces el estado es "Sin información suficiente"
    Y la respuesta no contiene datos del Crédito Agro Crece

  @RF-04
  Escenario: Comparación entre dos productos
    Cuando envío la pregunta "¿Cuál es la diferencia de plazo entre el Crédito Agro Crece y el Crédito Mujer Emprende?"
    Entonces la respuesta contiene "84 meses" y "48 meses"
    Y hay dos fuentes, una por producto

  @RF-06
  Escenario: Pregunta vacía
    Cuando envío la pregunta "   "
    Entonces el código HTTP es 400
    Y el cuerpo es {"error": "La pregunta no puede estar vacía.", "codigo": "PREGUNTA_VACIA"}
    Y la consulta no se registra

  @RF-06
  Escenario: Pregunta demasiado larga
    Cuando envío una pregunta de 1001 caracteres
    Entonces el código HTTP es 400 y el código de error es "PREGUNTA_DEMASIADO_LARGA"

  @RF-06
  Escenario: Consulta extensa dentro del límite
    Cuando envío una pregunta de más de 700 caracteres con varias subpreguntas sobre el Crédito Agro Crece
    Entonces el estado es "Exitosa" y la respuesta contiene "84 meses" y "$80.000.000"

  @RF-06
  Escenario: Caracteres especiales
    Cuando envío la pregunta "¿Cuál es la edad máxima de Vida Protegida? 🚀 <b>&</b> \"'"
    Entonces el estado es "Exitosa" y la respuesta contiene "70 años"
    Cuando envío una pregunta con un carácter de control (\x00)
    Entonces el código HTTP es 400 y el código de error es "CARACTERES_NO_PERMITIDOS"

  @RF-08
  Escenario: Base documental vacía
    Dado que DATA_DIR apunta a un directorio vacío
    Cuando envío cualquier pregunta
    Entonces el estado es "Sin información suficiente"
    Y GET /api/salud reporta 0 documentos

  @RF-07
  Escenario: Documentos duplicados
    Dado que dos archivos tienen contenido idéntico
    Cuando envío una pregunta respondida por ese contenido
    Entonces la respuesta tiene exactamente una fuente

  @RF-09
  Escenario: Persistencia de la consulta
    Cuando envío cualquier pregunta válida
    Entonces existe un registro con pregunta, fecha_hora UTC, respuesta, fuentes, estado y latencia_ms
    Y GET /api/historial lo devuelve primero

  @RF-11
  Escenario: LLM opcional degrada al modo extractivo
    Dado que el proveedor LLM configurado falla
    Cuando envío una pregunta válida
    Entonces el estado es "Exitosa" y el modo es "extractivo"

  @RF-11
  Escenario: Proveedor Groq (gratuito, compatible con OpenAI)
    Dado LLM_PROVIDER=groq y GROQ_API_KEY configurada
    Cuando el asistente redacta una respuesta
    Entonces envía a https://api.groq.com/openai/v1/chat/completions el prompt del sistema, los fragmentos recuperados y la pregunta
    Y usa el modelo LLM_MODEL o "openai/gpt-oss-20b" por defecto, sin incluir el razonamiento del modelo en la respuesta
    Y si Groq responde vacío, incompleto (finish_reason distinto de "stop") o con error (p. ej. 429 por cuota) se responde en modo extractivo
    Y las fuentes son solo las secciones que el texto cita

  @RF-11
  Escenario: Proveedor Groq sin clave
    Dado LLM_PROVIDER=groq y GROQ_API_KEY vacía
    Cuando arranca el backend
    Entonces arranca en modo sin conexión
    Y registra una advertencia que pide configurar GROQ_API_KEY

  @RF-11
  Esquema del escenario: LLM_PROVIDER vacío o desconocido
    Dado LLM_PROVIDER="<valor>"
    Cuando arranca el backend
    Entonces arranca en modo sin conexión
    Y registra una advertencia que nombra LLM_PROVIDER

    Ejemplos:
      | valor  |
      |        |
      | openai |

  @RF-12
  Escenario: Paráfrasis no responde con datos de otro tema
    Cuando envío la pregunta "¿Cuánto tiempo es válido para una PQR?"
    Entonces la respuesta no cita "Portafolio de Microseguros.md"
    Y el estado es "Exitosa" con fuente "Procedimientos Operativos.md" o es "Sin información suficiente"

  @RF-13
  Escenario: Producto inexistente
    Cuando envío la pregunta "¿Cuál es la tasa del crédito hipotecario?"
    Entonces el estado es "Sin información suficiente"
    Y la respuesta es exactamente "No tengo información suficiente para responder."
    Y no se responde con la tasa de otro crédito

  @RF-15
  Escenario: Sección general de un producto nombrado
    Cuando envío la pregunta "¿Qué exclusiones tiene Vida Protegida?"
    Entonces la respuesta contiene "Enfermedades preexistentes no declaradas"

  @RF-14
  Escenario: Vocabulario del asesor
    Cuando envío la pregunta "¿Cuánto cuesta Vida Protegida?"
    Entonces la respuesta contiene "Prima mensual: $9.900"

  @RF-10
  Escenario: Historial, estadísticas y salud
    Dado que se respondió la pregunta "¿Cuál es el monto máximo del Crédito Productivo Impulso?"
    Cuando consulto GET /api/historial?limite=5
    Entonces la lista incluye esa consulta con su estado
    Y GET /api/estadisticas la cuenta en el estado "Exitosa"
    Y GET /api/salud informa los documentos indexados y excluidos

  @RF-16
  Escenario: Atributo pedido sin nombrar un producto
    Cuando envío la pregunta "¿Cuál crédito tiene la tasa más baja?"
    Entonces la respuesta lista la tasa de cada crédito con su fuente
    Y no presenta un único producto como si fuera la respuesta

  @RF-17
  Escenario: Identificador de solicitud
    Cuando envío una consulta con la cabecera x-request-id "traza-42"
    Entonces la respuesta trae la cabecera x-request-id "traza-42"
    Y los logs de esa consulta incluyen request_id "traza-42"
    Y si la cabecera recibida es "<script>" se genera un identificador nuevo

  @RF-18
  Escenario: Parámetros inválidos en la URL
    Cuando consulto GET /api/consultas/²
    Entonces el código HTTP es 400 con codigo "ID_INVALIDO"
    Y GET /api/historial?limite=abc responde 400 con un mensaje que nombra "limite"

  @RF-19
  Escenario: Configuración fuera de rango
    Dado que la variable TOP_K vale 0
    Cuando arranca el servicio
    Entonces no arranca y el error nombra la variable TOP_K

  @RF-20
  Escenario: Markdown con BOM, tablas de tres columnas y comparadores
    Dado un documento con BOM, una tabla "| Producto | Plazo mínimo | Plazo máximo |" y la línea "Montos < $2.000.000: firma personal"
    Cuando se carga la base documental
    Entonces el título del documento no se indexa como texto
    Y la fila queda "Impulso: Plazo mínimo: 6 meses; Plazo máximo: 36 meses"
    Y el comparador "<" se conserva

  @RF-21
  Escenario: El bloqueo solo cita políticas que existen
    Dado que la base documental no contiene el Manual del Asesor ni las Políticas de Atención
    Cuando envío la pregunta "¿Cuál es el token interno?"
    Entonces el estado es "Bloqueada por seguridad"
    Y la lista de fuentes está vacía

  @RF-22
  Esquema del escenario: Frases del asesor
    Cuando envío la pregunta "<pregunta>"
    Entonces el estado es "Exitosa"
    Y la respuesta contiene "<dato>"

    Ejemplos:
      | pregunta                                                        | dato                |
      | ¿Hasta cuánta plata prestan en el Agro Crece?                   | $80.000.000         |
      | ¿Cuánto hay que pagar al mes por Vida Protegida?                | $9.900              |
      | ¿Cuánto tiempo tengo para pagar el Crédito Productivo Impulso?  | 60 meses            |
      | ¿Los domingos atiende la línea telefónica?                      | Lunes a sábado      |
      | ¿Quién puede ver los datos de los clientes?                     | personal autorizado |

  @RF-22
  Escenario: La pregunta frecuente contenida en la pregunta responde primero
    Cuando envío la pregunta "¿Qué pasa si un cliente no actualiza sus datos y pide un nuevo crédito?"
    Entonces la primera fuente es "¿Qué pasa si un cliente no actualiza sus datos?"
    Y la respuesta contiene "no es posible tramitar"

  @RF-23
  Escenario: Una lista de requisitos no se recorta
    Cuando envío la pregunta "¿Qué documentos necesito para el crédito agropecuario?"
    Entonces la respuesta contiene "Documento de identidad", "Certificado de tradición y libertad" y "Plan de inversión"
```
