# Cuestionario

> Las secciones marcadas con ✎ describen la experiencia personal del candidato: fueron redactadas a partir de la sesión de trabajo real y deben revisarse y completarse con cualquier herramienta o actividad adicional antes de la entrega.

## 1. Uso de IA

### Herramientas utilizadas ✎
- **Claude (claude.ai)** como asistente principal de ingeniería: diseño de la solución, generación de código, pruebas, documentación SDD y este cuestionario, en una sesión conversacional con ejecución de código y pruebas en un entorno aislado.
- **pytest, Vitest, TypeScript** como validadores objetivos de todo lo generado (la suite completa se ejecutó tras cada cambio).
- Sin herramientas pagas: el LLM no es dependencia de la solución; toda la ejecución es local.
- ✎ Añadir aquí si se usaron otras herramientas (Claude Code, Copilot, Cursor, etc.).

### Qué actividades se delegaron a la IA
- Redacción inicial de la constitución, especificaciones (requerimientos, riesgos, escenarios Gherkin), planes y listas de tareas, a partir de las decisiones tomadas por la persona.
- Implementación del backend (fragmentación de Markdown, BM25, motor extractivo, guardrails, persistencia, API) y del frontend, siguiendo un ciclo rojo → verde: escribir pruebas, ejecutarlas, corregir.
- Ampliación de los datos de ejemplo con registros ficticios coherentes (productos, microseguros, procedimientos, preguntas frecuentes).
- Depuración iterativa del motor con un banco de preguntas de control, que empezó con ~30 preguntas y hoy está versionado con 293 (`tests/backend/banco_preguntas.txt`, ejecutado por `tests/backend/test_banco.py` contra una foto de respuestas esperadas): la IA proponía reglas y las validaba contra las pruebas y el banco antes y después de cada cambio.
- Redacción de README, AGENTS.md y borrador de este cuestionario.

### Qué actividades se realizaron manualmente ✎
- Lectura del enunciado y de los archivos de datos; identificación de la trampa de seguridad en `Información restringida.md` y de las reglas de negocio implícitas en las políticas (citación obligatoria, frase canónica, escalamiento).
- Decisiones de alcance y de arquitectura: stack (Python/FastAPI + React/TypeScript), ejecución 100 % local con LLM opcional, SQLite, recuperación léxica extractiva en lugar de embeddings, estructura de carpetas (`sdd/`), seis características (001–006) en lugar de las dos del ejemplo.
- Revisión del código y de las pruebas generadas; verificación manual del servidor real con `curl` y de la interfaz; revisión de que ningún valor del archivo restringido aparece en código, pruebas o respuestas.
- Decisión de qué sugerencias aceptar o rechazar (siguiente sección) y de cuándo detener la iteración del motor (26/28 → 31/32 → 32/32 en la primera versión del banco de control; después, comparación antes/después sobre el banco versionado, que reveló y evitó regresiones como la primera versión de la regla RF-12).
- ✎ Completar con la configuración del repositorio en GitHub, commits y cualquier ajuste posterior.

### Qué sugerencias de la IA se rechazaron ✎
- **Un umbral de cobertura alto (0,5) como criterio principal de "sin información".** Producía falsos negativos en preguntas largas; se reemplazó por reglas explicables (mínimo dos términos coincidentes, selección de líneas por atributos, bloqueo por entidad) y el umbral quedó como piso de seguridad en 0,3.
- **Añadir un segundo fragmento a la respuesta siempre que su puntaje fuera cercano.** Generaba respuestas ruidosas con datos de otros productos; se restringió a entidades que la pregunta nombra explícitamente (comparaciones).
- **Un rastro de autoría "generado por IA" en los commits y un único commit masivo.** Se prefirió un historial de commits por característica, escrito por la persona.
- ✎ Añadir otras sugerencias rechazadas durante la revisión.

### Cómo se validaron las respuestas de la IA
1. **Pruebas automatizadas como oráculo:** la suite de backend (pytest) y la de frontend (Vitest), escritas antes o junto con el código; ningún cambio se aceptó con la suite en rojo.
2. **Banco de preguntas de control** (32 preguntas reales de asesor con la respuesta esperada) ejecutado contra el servicio tras cada ajuste del motor, para detectar regresiones que las pruebas unitarias no cubren.
3. **Pruebas negativas de seguridad:** verificación de que los valores del documento restringido no aparecen en el índice, en el contexto enviado a un LLM, ni en ninguna respuesta; se leen del archivo en tiempo de prueba para no copiarlos al código.
4. **Revisión de código** módulo por módulo, con especial atención a `seguridad/guardrails.py`, `herramientas/corpus.py` y `generacion/extractivo.py`.
5. **Ejecución real:** servidor levantado con `uvicorn`, consultas con `curl`, build del frontend y verificación de tipos.

## 2. Decisiones técnicas para paso a productivo

### ¿Qué modelo utilizaría y por qué?
Un esquema de **dos niveles**, manteniendo siempre el motor extractivo determinista como respaldo:

1. **Modelo pequeño y rápido para el 90 % de las consultas** (la clase más económica de la familia Claude, hoy la gama Haiku; verificar el nombre y precio vigentes en https://docs.claude.com/en/docs/about-claude/models). Las preguntas de los asesores son cortas, el contexto son 3–8 fragmentos y la tarea es redactar con fidelidad, no razonar: un modelo pequeño con temperatura 0 es suficiente, barato y de baja latencia.
2. **Modelo de gama media (clase Sonnet) solo para casos escalados:** comparaciones entre varios productos, preguntas largas o con baja confianza del primer nivel (se detecta por cobertura léxica baja o respuesta canónica del modelo pequeño).

**Implementado en esta prueba (gratuito):** proveedor `groq` (GroqCloud, API compatible con OpenAI) con `openai/gpt-oss-20b` por defecto. Se eligió porque el enunciado no admite herramientas pagas y GroqCloud tiene un plan gratuito sin tarjeta; `gpt-oss-20b` es un modelo de producción vigente (los Llama 3.x del plan gratuito se retiraron el 16/08/2026, según la página de *deprecations* de Groq) y su tamaño aprovecha mejor los límites por minuto del plan gratuito. Se desactiva el razonamiento en la respuesta (`include_reasoning: false`) y se usa `reasoning_effort: low`. Es opcional (`LLM_PROVIDER=groq` + `GROQ_API_KEY`): si la clave falta, el backend no arranca y lo indica con un mensaje claro; ante error, cuota agotada (429) o respuesta incompleta de Groq responde el motor extractivo; con `LLM_PROVIDER=none` (por defecto) siempre responde el motor extractivo. A Groq se envían el prompt del sistema, los fragmentos recuperados y la pregunta del asesor; nunca el documento restringido.

Alternativa si hay restricción de residencia de datos: un modelo abierto servido en la infraestructura propia (vía vLLM), aceptando mayor costo operativo y menor calidad. En todos los casos el modelo **solo redacta a partir de fragmentos recuperados** y su salida pasa por el filtro de secretos; nunca responde "de memoria".

### ¿Cómo optimizaría costos?
- **No llamar al LLM cuando no aporta:** hoy no se llama en preguntas bloqueadas ni fuera de dominio (sin fragmentos candidatos). Como mejora para producción, responder también en modo extractivo (costo cero) las preguntas con respuesta exacta de tabla (`Monto máximo: …`), que en el corpus actual serían la mayoría, y llamar al LLM solo cuando el extractivo no encuentra respuesta.
- **Caché de respuestas** por pregunta normalizada (raíces ordenadas) y por versión del corpus, con TTL y invalidación al recargar documentos.
- **Contexto mínimo:** solo los fragmentos relevantes (no documentos completos), `max_tokens` acotado, prompt del sistema estable para aprovechar caché de prompt del proveedor cuando exista.
- **Modelo pequeño por defecto y escalamiento selectivo** (sección anterior); presupuesto mensual con alertas.
- **Procesamiento por lotes** para tareas no interactivas (evaluación de calidad, reindexación).

### ¿Cómo mitigaría Prompt Injection?
Lo implementado hoy, reforzado para producción:
1. **Separación de datos e instrucciones:** los documentos se envían dentro de etiquetas `<fragmentos>` y el prompt del sistema declara que son datos; las líneas con apariencia de instrucción se eliminan en la ingesta y se registran.
2. **Lo restringido no existe para el modelo:** los documentos confidenciales no se indexan; aunque un ataque "convenza" al modelo, no hay nada que revelar.
3. **Guardrail de entrada** por intención (incluye patrones de inyección en español e inglés) y **guardrail de salida** con lista de denegación derivada de los documentos restringidos + patrones de credencial.
4. **Sin herramientas ni acciones:** el modelo no tiene *tool use* ni acceso a sistemas; su único efecto es texto, que además se filtra.
5. En producción: clasificador de intención como segunda opinión, banco de ataques (red team) en CI, límites de tasa por usuario, y revisión humana de bloqueos frecuentes para ajustar reglas.

### ¿Qué guardrails implementaría?
| Capa | Hoy | Producción |
|------|-----|------------|
| Entrada | tipo, vacía, longitud, caracteres de control; 6 categorías de bloqueo | + autenticación, autorización por rol, rate limiting, detección de PII en la pregunta |
| Conocimiento | exclusión de documentos restringidos; saneamiento de instrucciones; deduplicación | + clasificación de documentos en la ingesta, control de versiones del corpus, aprobación de cambios |
| Generación | solo fragmentos recuperados; temperatura 0; frase canónica; fallback extractivo | + verificación de que cada afirmación aparece en los fragmentos (*grounding check*), límite de tokens, timeout |
| Salida | lista de denegación + patrones de credencial; citación obligatoria | + detección de PII, moderación, marca de agua de respuestas generadas |
| Operación | estados persistidos; logs JSON con categoría de bloqueo | + alertas por tasa de bloqueos, auditoría, retención y borrado conforme a política |

### ¿Cómo monitorearía calidad?
- **Métricas automáticas:** distribución de estados (exitosa / sin información / bloqueada), latencia p50/p95, tasa de fallback del LLM, cobertura léxica promedio, porcentaje de respuestas con fuente.
- **Conjunto de evaluación versionado** (preguntas con respuesta y fuente esperadas) ejecutado en CI y tras cada cambio de corpus: exactitud, citación correcta, falsos "sin información", fugas (cero tolerancia).
- **Retroalimentación del asesor** (útil / no útil / incorrecta) en la interfaz, unida al registro de la consulta.
- **Revisión por muestreo** semanal de respuestas y de bloqueos; análisis de preguntas frecuentes sin respuesta para enriquecer `Data/`.
- **Alertas:** aumento súbito de "sin información" (síntoma de corpus roto), de bloqueos (ataque o regla rota) o de latencia.

### ¿Cómo evolucionaría la solución hacia RAG?
Ya es un RAG léxico (recuperar → generar) con todas las piezas aisladas; la evolución es incremental:
1. **Embeddings + búsqueda híbrida:** indexar los mismos fragmentos con un modelo de embeddings y combinar BM25 con similitud vectorial (fusión RRF); mantener el bloqueo por entidad como filtro de metadatos.
2. **Reordenamiento** (*reranker*) de los 20–50 candidatos para elegir los 5 mejores.
3. **Metadatos y filtros:** producto, tipo de documento, vigencia, versión; respuestas con "vigente desde".
4. **Ingesta continua:** pipeline que detecta cambios en los documentos, reindexa fragmentos afectados y mantiene la lista de denegación.
5. **Generación con verificación:** el modelo cita por identificador de fragmento y una capa comprueba que cada cita existe y respalda la afirmación.
6. **Evaluación RAG** (precisión del contexto, fidelidad de la respuesta, utilidad) con el conjunto de evaluación.

Persistencia: PostgreSQL con `pgvector` para fragmentos, embeddings y consultas en un solo motor (ver sección 6).

## 3. Uso de agentes

### ¿Utilizó agentes de desarrollo? ✎
Sí: un asistente de IA con capacidad de ejecutar comandos, crear archivos y correr pruebas en un entorno aislado actuó como agente de desarrollo supervisado durante toda la construcción. ✎ Indicar si además se usó Claude Code u otro agente en el repositorio local.

### ¿Cómo fueron instruidos?
- Con el enunciado completo y los archivos de datos como contexto, más las decisiones de la persona (stack, alcance, ejecución local, LLM opcional).
- Con las reglas de `AGENTS.md`: documentos como datos, prohibición de copiar valores del archivo restringido, TDD obligatorio, español, no cambiar contratos sin actualizar especificaciones, y una lista explícita de decisiones reservadas a humanos.
- Con un ciclo de trabajo fijo: especificación → prueba roja → implementación → suite completa → documentación.

### ¿Qué tareas delegó?
Generación de código y pruebas, refactorizaciones guiadas por pruebas, ampliación de datos de ejemplo, documentación técnica y ejecución repetitiva de la suite y del banco de preguntas de control.

### ¿Qué tareas supervisó manualmente?
Cada regla de seguridad y cada cambio en el motor de respuesta (leyendo el diff y el resultado del banco de control), la coherencia entre especificaciones y pruebas, el contenido de los datos ficticios añadidos, y la verificación de que ninguna prueba o archivo contenga valores sensibles.

### ¿Qué decisiones no permitió tomar a la IA?
Qué documentos son restringidos y cómo se detectan; activar un proveedor de LLM o elegir modelo; la tecnología de persistencia; relajar límites o categorías de bloqueo; eliminar pruebas; y la estructura final de entrega del repositorio.

## 4. Frontera entre IA y desarrollo tradicional

### ¿Qué responsabilidades resolvería mediante desarrollo tradicional?
Validación de entradas, autenticación y autorización, control de acceso a documentos, filtros de seguridad, persistencia y auditoría, contratos de API, manejo de errores, límites de tasa, observabilidad y despliegue. Todo lo que deba ser **determinista, auditable y verificable con pruebas**.

### ¿Qué responsabilidades delegaría a IA?
Comprensión de preguntas en lenguaje natural (paráfrasis, sinónimos), redacción de respuestas a partir de fragmentos verificados, clasificación de intención como señal adicional, sugerencia de preguntas relacionadas, resumen de documentos nuevos para revisión humana, y, en desarrollo, generación de código y pruebas bajo supervisión.

### ¿Qué responsabilidades nunca permitiría ejecutar a una IA?
Decidir qué información es confidencial o a quién se le puede mostrar; aprobar créditos, calcular condiciones o emitir compromisos con clientes; modificar documentos oficiales o la base de datos; ejecutar acciones sobre sistemas (desembolsos, actualización de datos); desactivar guardrails o pruebas; y responder sin fuente verificable.

### ¿Cómo mantendría separadas estas responsabilidades?
- **Arquitectura:** el LLM es un componente opcional detrás de una interfaz (`ProveedorLLM`) que solo recibe fragmentos y devuelve texto; la validación, el filtrado, la persistencia y la autorización son código tradicional que rodea al modelo (patrón *sandwich*: código → modelo → código).
- **Orquestador determinista:** el orquestador (`orquestador/`) aplica los guardrails y elige por reglas qué agente responde (crédito, microseguros, operativo o fuera de dominio). Ningún LLM decide la ruta ni qué herramienta usar, y la seguridad nunca se delega a un agente; las capas solo dependen hacia abajo y una prueba de arquitectura lo verifica (especificación 004).
- **Contratos verificables:** la salida del modelo pasa siempre por el filtro de secretos (si lo infringe, la consulta queda *Bloqueada por seguridad*); las fuentes que se muestran son solo las secciones recuperadas que el texto cita; y si el proveedor falla, se queda sin cuota o entrega una respuesta incompleta, responde el motor extractivo.
- **Sin capacidades de acción:** el modelo no tiene herramientas ni credenciales.
- **Pruebas como frontera:** cada responsabilidad "tradicional" tiene pruebas deterministas que no dependen del modelo; la suite corre sin LLM.
- **Gobierno:** `AGENTS.md` y la constitución fijan qué decide la IA y qué decide una persona, tanto en operación como en desarrollo.

## 5. Optimización y operación (100.000 consultas diarias)

### ¿Qué componente tendría mayor riesgo de latencia?
La **llamada al LLM** (cientos de milisegundos a segundos, con variabilidad de red y del proveedor). En segundo lugar, la **persistencia** al escalar horizontalmente: 100.000 consultas diarias son ~1,2 escrituras por segundo en promedio, algo que SQLite soporta holgadamente en una sola instancia (medido: 0,22 ms por escritura con 10.000 registros), pero un archivo SQLite no se comparte entre varias réplicas del backend ni ofrece alta disponibilidad. La recuperación BM25 es despreciable (microsegundos en memoria) mientras el corpus sea pequeño; con decenas de miles de fragmentos pasaría a un índice dedicado.

### ¿Qué estrategia utilizaría para reducir tiempos de respuesta?
- Responder en **modo extractivo** todo lo que no necesite redacción (en el corpus actual, la mayoría) y llamar al LLM solo en los casos que lo justifican (mejora propuesta; hoy, con LLM activo, se llama siempre que hay fragmentos candidatos).
- **Caché** (siguiente punto) delante del LLM.
- **Streaming** de la respuesta del modelo hacia la interfaz y timeouts estrictos con fallback extractivo.
- Modelo pequeño por defecto; prompt corto y estable; contexto mínimo.
- Índice y corpus en memoria en cada réplica; carga del corpus al arranque (ya implementado) y recarga en caliente.
- **Escrituras asíncronas** a la base de datos (cola) para que la persistencia no esté en el camino crítico de la respuesta.
- Escalado horizontal del backend (sin estado) detrás de un balanceador.

### ¿Qué podría cachear?
- Respuesta completa por **pregunta normalizada + versión del corpus** (muchas preguntas de asesores se repiten casi literalmente).
- Resultados de recuperación por conjunto de raíces.
- El prompt del sistema y los fragmentos frecuentes (caché de prompt del proveedor).
- Embeddings de fragmentos (cuando existan) y de preguntas frecuentes.
- Historial y estadísticas en la interfaz con TTL corto.
Invalidación por versión del corpus y por cambio de reglas de seguridad.

### ¿Qué monitorearía?
Latencia p50/p95/p99 por etapa (validación, recuperación, LLM, persistencia); tasa de errores 4xx/5xx; distribución de estados; tasa de acierto de caché; tasa de fallback y timeouts del LLM; cuota restante del proveedor (cabeceras `x-ratelimit-*`, ya expuesta en `GET /api/llm` y en el panel de la interfaz, con alerta por debajo del 10 %); costo por consulta y por día; tasa de bloqueos por categoría (con alerta ante picos); salud del corpus (documentos, fragmentos, advertencias); saturación de la base de datos; y las métricas de calidad de la sección 2.

### ¿Cómo optimizaría costos de operación?
Modelo pequeño y escalamiento selectivo; caché; modo extractivo como primera opción; `max_tokens` acotado; procesamiento por lotes para evaluaciones; autoescalado del backend según carga; retención de registros con archivado de los antiguos; y presupuesto con alertas por consumo del proveedor de LLM.

## 6. Persistencia y gestión de datos

### Qué mecanismo de almacenamiento seleccionó
**SQLite** mediante el módulo `sqlite3` de la biblioteca estándar, con una tabla `consultas` (`id`, `pregunta`, `fecha_hora` UTC ISO 8601, `respuesta`, `fuentes` JSON, `estado` con restricción `CHECK`, `latencia_ms`, `modo`) e índices por fecha y estado, encapsulada en `RepositorioConsultas`.

### Por qué lo seleccionó
Cumple el requisito (pregunta, fecha y hora, respuesta, fuentes, estado) sin instalar ni configurar nada, funciona 100 % en local, es transaccional y confiable, y el repositorio aísla el cambio de motor. Para el volumen de la prueba y de un piloto interno es más que suficiente.

### Qué ventajas tiene para este escenario
Cero dependencias externas (es una librería embebida en Python: no hay servidor que ejecutar); un solo archivo fácil de inspeccionar, respaldar y borrar; recuperación por ID con la llave primaria (`GET /api/consultas/{id}`); arranque inmediato para quien evalúa; pruebas con base en memoria (`:memory:`) rápidas y aisladas; consultas SQL para estadísticas; y el esquema es portable a PostgreSQL sin cambios conceptuales.

**Alternativa evaluada y descartada: un archivo JSON.** Medido en la máquina de desarrollo con 10.000 consultas: SQLite guarda en 0,22 ms y lee por ID en 0,05 ms (constante al crecer); un JSON reescrito en cada consulta tarda 61,8 ms en guardar y 12,8 ms en leer por ID (crece con el archivo, ~7 MB), no tiene índices y se corrompe si el proceso cae a mitad de escritura o hay escrituras concurrentes.

**Memoria de conversación:** no se persiste en el servidor. El navegador envía las últimas 3 preguntas como `contexto` opcional y el servidor sigue sin estado; así el esquema de `consultas` (pregunta, fecha y hora, respuesta, fuentes, estado) no cambia. Persistir conversaciones con un identificador es una mejora que cambiaría el esquema.

## 7. Escenario de producción

### ¿Mantendría la misma solución de persistencia?
No. SQLite es adecuado para desarrollo, pruebas y pilotos de una sola instancia, pero en producción habrá varias réplicas del backend, escrituras concurrentes sostenidas, requisitos de respaldo, retención, auditoría y consultas analíticas.

### ¿Qué motor de base de datos utilizaría?
**PostgreSQL** (gestionado), con la extensión **`pgvector`** cuando se incorporen embeddings.

### ¿Por qué?
- Concurrencia real y escalabilidad horizontal de lectura (réplicas), con alta disponibilidad y respaldos gestionados.
- Tipos nativos útiles: `timestamptz` para fechas, `jsonb` para fuentes (consultable e indexable), `enum`/`CHECK` para estados.
- Un solo motor para consultas, fragmentos, versiones del corpus y vectores (`pgvector`), evitando una base vectorial adicional en la primera etapa.
- Particionado por fecha y políticas de retención para 100.000 registros diarios; índices por estado y fecha para monitoreo.
- Auditoría y control de acceso por rol a nivel de base de datos.
La migración es directa: el repositorio ya aísla el SQL y el esquema actual se traduce sin cambios conceptuales.
