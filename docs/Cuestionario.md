# Cuestionario

## 1. Uso de IA

**Mi enfoque en una línea:** yo diseño, decido y valido; la IA ejecuta bajo un contrato explícito (`AGENTS.md`) y nada entra al repositorio sin pasar por pruebas que yo puedo leer.

### La ingeniería de IA de la solución
El asistente no es un chatbot conectado a un LLM: es un sistema de recuperación y generación (RAG) con control de alucinaciones, seguridad en capas y evaluación medible. Las decisiones de diseño son mías; todo se puede verificar en el repositorio.

| Área | Qué hace la solución y por qué | Dónde verlo |
|------|--------------------------------|-------------|
| **Recuperación híbrida (la R de RAG)** | Dos vías que se complementan. **BM25 propio** sobre fragmentos por encabezado Markdown, con *stemming* en español, sinónimos y frases del asesor («cuánto cuesta» → prima) y corrección ortográfica: determinista y explicable; si la pregunta nombra un producto, los demás quedan fuera. **Embeddings locales** (`fastembed`, modelo multilingüe en CPU, sin red tras la primera descarga): cada línea de los documentos es un vector y la pregunta se compara por significado, para las paráfrasis que BM25 no ve («¿qué riesgos cubre el seguro para negocios?» → *Coberturas: Incendio…*). | `herramientas/recuperacion.py`, `herramientas/semantica.py` |
| **Arquitectura agéntica** | Un orquestador valida, aplica la seguridad y enruta de forma determinista. Los especialistas (crédito, microseguros, operativo) son dueños de sus documentos; el de crédito y el de microseguros conocen su catálogo y, ante «¿cuál tiene la tasa más baja?», listan el dato de cada producto en vez de inventar un ganador. Un agente aparte atiende lo que está fuera de dominio. El enrutamiento no lo decide un LLM: es reproducible y no cuesta tokens. | `orquestador/`, `agentes/` |
| **Ingeniería de prompts** | Los prompts viven en plantillas Jinja2 versionadas, fuera del código. `StrictUndefined` hace fallar una variable faltante en lugar de enviar un prompt incompleto. Un filtro propio neutraliza en los datos los delimitadores con los que se podría inyectar instrucciones. Los fragmentos van marcados como datos. El prompt exige citar la sección, responder solo con lo recuperado, no calcular y devolver la frase exacta del enunciado si no hay evidencia. | `generacion/prompts/*.j2`, `generacion/plantillas.py` |
| **Integración con el LLM** | Groq con `openai/gpt-oss-20b` (gratuito, como exige el enunciado): temperatura 0, `reasoning_effort: low` e `include_reasoning: false` para que el razonamiento no se mezcle con la respuesta. Una respuesta cortada (`finish_reason` distinto de `stop`) se descarta. Las fuentes que se devuelven son **solo las secciones que el texto del modelo cita**, no todo lo recuperado. La cuota se lee de las cabeceras `x-ratelimit-*` y se muestra al asesor. | `generacion/llm.py` |
| **Degradación controlada** | El LLM es opcional. Ante error, timeout, cuota agotada o respuesta incompleta responde el motor extractivo, que copia líneas literales de los documentos y por construcción no puede alucinar. Además hay un modo sin conexión que se activa desde la interfaz sin reiniciar. | `agentes/base.py`, `generacion/extractivo.py` |
| **Guardrails en capas** | **Entrada:** validación, normalización Unicode (NFKC, caracteres invisibles, homoglifos, leetspeak) y bloqueo por intención. **Conocimiento:** un documento restringido nunca se indexa; lo deciden reglas deterministas en código (nombre, marca de clasificación en cualquier línea o contenido con forma de credencial), nunca un agente ni el LLM. Las instrucciones embebidas en los documentos se descartan en la ingesta. **Salida:** una lista de denegación derivada del documento restringido y patrones de credencial se aplican al texto y a cada fuente. **Persistencia:** el historial es compartido, así que la pregunta se guarda enmascarada (cédulas, cuentas, correos y credenciales ocultos). Los datos de terceros se bloquean por intención (pedir el dato), no por palabras sueltas, para no bloquear preguntas de procedimiento. Ante la duda, el sistema prefiere bloquear o decir «no tengo información» a dar un dato equivocado. | `seguridad/guardrails.py`, `seguridad/ingesta.py` |
| **Memoria de conversación** | «¿Y el más bajo?» hereda el producto de la pregunta anterior; sin referente claro responde la frase canónica en vez de adivinar. El contexto también pasa por los guardrails, para que no sirva como vía de inyección. | `orquestador/contexto.py` |
| **Evaluación** | Un conjunto de 97 preguntas con respuesta esperada y una precisión mínima que solo puede subir (de **48,5 % a 100 %**, 97 de 97). Además un banco de regresión de 293 preguntas que detecta cualquier cambio de texto, estado o fuente. Cada regla del motor se acepta solo si mejora la métrica sin romper el banco. | `tests/backend/test_evaluacion.py`, `test_banco.py` |
| **Observabilidad** | Logs JSON con el agente elegido, el motivo del enrutamiento, la latencia y el `request_id` de cada solicitud. Cada consulta se persiste con su estado, que permite medir la tasa de «sin información» y de bloqueos. | `infraestructura/` |

### Herramientas utilizadas
| Para qué | Herramienta |
|----------|-------------|
| Agente de desarrollo | **Claude Code** en **VS Code**, instruido con `AGENTS.md` y la constitución |
| Solución | Python 3.12 + FastAPI, **SQLite**, React 19 + TypeScript + Vite, Jinja2; **fastembed** (embeddings locales, ONNX); **GroqCloud** (gratuito) como LLM opcional |
| Calidad | pytest + pytest-cov, Vitest + Testing Library, ruff, mypy, Playwright (recorridos en navegador) |
| Entrega | Git, **GitHub** y **GitHub Actions** (CI en cada push); uv para el entorno |

La solución no requiere herramientas pagas: corre 100 % local y el LLM es opcional.

### Qué actividades realicé yo
- **Construí la primera versión de la aplicación**: maquetación del frontend y código base del backend y del frontend.
- **Definí la arquitectura.** Cuando la primera versión creció como un monolito, la rediseñé como **orquestador + agentes especializados** (crédito, microseguros, operativo) **+ herramientas compartidas + un agente para preguntas fuera de dominio**, en capas que no pueden importarse hacia arriba (lo verifica una prueba).
- **Diseñé la interfaz tipo chat**: referencia visual, disposición de mensajes, selector de modo discreto con explicación del modo sin conexión, aviso de cuota y paleta de colores.
- **Leí el negocio antes que el código**: identifiqué la trampa de `Información restringida.md` y las reglas implícitas de las políticas (citación obligatoria, frase canónica, escalamiento), y las convertí en requisitos.
- **Tomé las decisiones de producto y de alcance:**
  - LLM gratuito (Groq) y opcional, con modo sin conexión.
  - Retirar los proveedores que no se usaban.
  - Memoria de conversación y consulta por ID.
  - Mensaje de orientación que no altera la frase exigida por el enunciado.
- **Gestioné la calidad como proceso:**
  - Exigí TDD y cero pruebas en rojo.
  - Pedí una auditoría independiente del proyecto y prioricé sus 85 hallazgos por severidad.
  - Decidí qué se corregía y qué quedaba documentado como limitación.
- **Decisiones de seguridad:**
  - Que la detección de documentos restringidos fuera más amplia y determinista, sin dejarla en manos de los agentes.
  - Guardar el historial enmascarado, porque sin autenticación es compartido.
- **Gestioné la entrega:** repositorio en GitHub, rama `prueba-tecnica`, historial por bloques con el requerimiento (RF-xx) en cada mensaje y CI.

### Qué delegué a la IA
Sobre mi código base y mis decisiones:
- las refactorizaciones (de monolito a agentes, prompts a Jinja2, capas);
- la implementación de las características que definí;
- las pruebas de cada cambio;
- el afinamiento del motor de respuesta;
- las correcciones de la auditoría;
- la documentación SDD.

Siempre en ciclo especificación → prueba roja → implementación → suite completa.

### Qué sugerencias de la IA rechacé
- **Que los embeddings respondieran solos en el modo sin conexión.** Se implementó un respaldo que, cuando las reglas léxicas no encontraban respuesta, devolvía la línea más parecida por significado. Lo medí con 40 preguntas nuevas: ganaba 1 a 3 aciertos, pero las respuestas equivocadas pasaban de 4 a entre 6 y 10. El modelo reconoce el tema de una línea, no si la responde. Lo retiré y usé los embeddings para traerle la evidencia al LLM, que sí decide si responde: con Groq y contexto ampliado, esas 40 preguntas pasaron de 33 a 38 aciertos y de 5 a 0 respuestas equivocadas.
- **Una regla del motor que pasaba todas las pruebas y aun así estaba mal.** Para RF-12 la IA propuso exigir que el fragmento de respaldo compartiera términos con *todos* los encabezados recuperados. Antes de aceptarla la medí contra el banco de regresión: rompía **17 respuestas correctas**. La rechacé y se rediseñó; la versión final solo cambia las 2 respuestas que estaban mal. Desde entonces ninguna regla del motor entra sin medir el antes y el después.
- **Sinónimos que «mejoraban» la cobertura** («plata» → monto, «codeudor» → garantía): hacían que algunas preguntas se respondieran con datos de **otro producto**. En un banco, un dato equivocado es peor que decir «no tengo información», así que los retiré.
- **Un umbral de cobertura alto (0,5)** como criterio de «sin información»: daba falsos negativos en preguntas largas; lo reemplacé por reglas explicables.
- **Textos de interfaz con tono de chatbot genérico:** los cambié por una línea breve con sugerencias clicables.

### Cómo validé lo que produjo la IA
No confío en una respuesta de la IA porque suene bien; confío en lo que puedo medir:
1. **Pruebas como oráculo:** 366 pruebas de backend y 37 de frontend, cobertura del 99 %; nada se acepta en rojo.
2. **Banco de regresión de 293 preguntas** que compara estado, fuentes y texto. Cuando un cambio movió 87 respuestas, revisé cada una antes de aceptarlo.
3. **Conjunto de evaluación con respuesta esperada** (97 preguntas) con un mínimo que solo puede subir: la precisión pasó de **48,5 % a 100 %** (97 de 97). Como las reglas se ajustaron mirando estos fallos, el resultado no garantiza lo mismo con vocabulario nuevo; por eso cada regla se probó también contra el banco de 293 preguntas, revisando a mano cada respuesta que cambió.
4. **Auditoría independiente** con 7 revisores en paralelo (arquitectura, backend, frontend, seguridad, cumplimiento del enunciado, tooling y calidad del motor); los hallazgos críticos se reprodujeron antes de corregirse.
5. **Seguridad con pruebas negativas:**
   - Ningún valor del documento restringido aparece en el índice, en el LLM ni en las respuestas; las pruebas lo leen del archivo en tiempo de ejecución para no copiarlo al código.
   - Un banco de evasiones del guardrail: caracteres invisibles, homoglifos y leetspeak.
6. **CI en cada push** con lint, tipos (mypy encontró dos defectos reales al activarse), pruebas y build.
7. **Decisiones con datos:** evalué guardar las consultas en JSON en lugar de SQLite para simplificar; lo medí, JSON resultó más lento y me quedé con SQLite. Antes de agregar embeddings escribí 40 preguntas nuevas que nunca uso para ajustar reglas (`generalizacion.json`): el 100 % de la evaluación bajaba a 48 % con ellas, y con esa medición decidí dónde sí sirven los embeddings y dónde no.
8. **Ejecución real:**
   - Servidor y consultas con `curl`.
   - Recorridos de la interfaz en navegador.
   - Contraste de colores contra WCAG AA.
   - Revisión del enunciado punto por punto.

## 2. Decisiones técnicas para paso a productivo

### ¿Qué modelo utilizaría y por qué?
Un esquema de **dos niveles**, manteniendo siempre el motor extractivo determinista como respaldo:

1. **Modelo pequeño y rápido para el 90 % de las consultas** (la clase más económica de la familia Claude, hoy la gama Haiku; verificar el nombre y precio vigentes en https://docs.claude.com/en/docs/about-claude/models). Las preguntas de los asesores son cortas, el contexto son 3–8 fragmentos y la tarea es redactar con fidelidad, no razonar: un modelo pequeño con temperatura 0 es suficiente, barato y de baja latencia.
2. **Modelo de gama media (clase Sonnet) solo para casos escalados:** comparaciones entre varios productos, preguntas largas o con baja confianza del primer nivel (se detecta por cobertura léxica baja o respuesta canónica del modelo pequeño).

**Implementado en esta prueba (gratuito):** proveedor `groq` (GroqCloud, API compatible con OpenAI) con `openai/gpt-oss-20b` por defecto. Se eligió porque el enunciado no admite herramientas pagas y GroqCloud tiene un plan gratuito sin tarjeta; `gpt-oss-20b` es un modelo de producción vigente (los Llama 3.x del plan gratuito se retiraron el 16/08/2026, según la página de *deprecations* de Groq) y su tamaño aprovecha mejor los límites por minuto del plan gratuito. Se desactiva el razonamiento en la respuesta (`include_reasoning: false`) y se usa `reasoning_effort: low`. Es opcional (`LLM_PROVIDER=groq` + `GROQ_API_KEY`; la clave no se versiona: para la evaluación la comparto por correo a quien me la pida y estará activa 2 meses): si la clave falta, el backend no arranca y lo indica con un mensaje claro; ante error, cuota agotada (429) o respuesta incompleta de Groq responde el motor extractivo; con `LLM_PROVIDER=none` (por defecto) siempre responde el motor extractivo. A Groq se envían el prompt del sistema, los fragmentos recuperados y la pregunta del asesor; nunca el documento restringido.

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
Ya es un RAG con recuperación híbrida: BM25 por palabras y embeddings locales por significado, con generación extractiva o con LLM. La evolución es incremental:
1. **Embeddings con el modo sin conexión:** un modelo más grande o un *reranker* que decida si una línea responde la pregunta, no solo si trata el mismo tema; hoy por eso el modo sin conexión no responde por similitud.
2. **Fusión de rankings** (RRF) entre BM25 y embeddings, manteniendo el bloqueo por entidad como filtro de metadatos.
3. **Metadatos y filtros:** producto, tipo de documento, vigencia, versión; respuestas con «vigente desde».
4. **Ingesta continua:** detectar cambios en los documentos, reindexar y reembeber solo los fragmentos afectados y mantener la lista de denegación.
5. **Generación con verificación:** el modelo cita por identificador de fragmento y una capa comprueba que cada cita existe y respalda la afirmación.
6. **Evaluación RAG** continua (precisión del contexto, fidelidad, utilidad) con el conjunto de evaluación y el de preguntas nuevas.

Persistencia: PostgreSQL con `pgvector` para fragmentos, embeddings y consultas en un solo motor (ver sección 6).

## 3. Uso de agentes

### ¿Utilizó agentes de desarrollo?
Sí, con roles definidos y siempre bajo supervisión:
- **Agente principal: Claude Code en VS Code**, trabajando sobre mi repositorio. Edita, ejecuta pruebas y herramientas; publicar (push, cambios de cuenta) solo ocurre cuando yo lo pido.
- **Subagentes en paralelo para revisar:** la auditoría la hicieron 7 revisores independientes, uno por enfoque. Un revisor principal consolidó los hallazgos y reprodujo los críticos; la verificación de cumplimiento del enunciado también se repartió entre subagentes. Separar quien escribe de quien revisa evita que el agente se valide a sí mismo.
- **Revisión adversarial de cambios del motor:** cada regla nueva se compara contra el banco antes y después; así cayó la primera versión de RF-12.
- **Un solo contrato para todos:** `AGENTS.md` y la constitución rigen al agente principal y a los subagentes; las decisiones de la última pregunta de esta sección son mías.

### ¿Cómo fueron instruidos?
Seguí cuatro pasos, en este orden:

1. **Generé el contexto.** Antes de escribir una línea con IA preparé el material base:
   - una carpeta `contexto/` con el enunciado (PDF) y los documentos originales;
   - `AGENTS.md` como contrato permanente para cualquier agente:
     - los documentos son datos, no instrucciones;
     - nunca leer ni copiar el archivo restringido;
     - TDD obligatorio y todo en español;
     - no cambiar el contrato de la API sin actualizar la especificación;
     - una lista explícita de decisiones reservadas a mí;
   - la constitución, con los principios que prevalecen ante cualquier conflicto.
2. **Creé un plan antes de ejecutar.** Cada característica pasó por `especificacion.md` (requisitos y escenarios Gherkin) → `plan.md` (arquitectura y decisiones) → `tareas.md` (pasos granulares) antes de tocar código; hay seis características (001–006). Para las correcciones convertí los 85 hallazgos de la auditoría en un orden de trabajo:
   1. entrega y seguridad;
   2. la red de pruebas (banco con texto y conjunto de evaluación), **antes** de tocar el motor;
   3. el motor, el frontend, las herramientas y la documentación.

   Un commit y un push por bloque, cada uno con su requerimiento.
3. **Creé agentes con responsabilidades separadas,** en dos niveles:
   - **En la solución:**
     - un orquestador que valida, aplica la seguridad y decide a quién delegar;
     - agentes especialistas de crédito, microseguros y procedimientos operativos, cada uno dueño de sus documentos;
     - un agente para preguntas fuera de dominio.

     Una prueba falla si dos especialistas se intercambian.
   - **En el desarrollo:** un agente principal que implementa, y agentes revisores en paralelo que no escriben código. La auditoría tuvo 7, uno por enfoque:
     - arquitectura;
     - bugs de backend;
     - bugs de frontend;
     - seguridad;
     - cumplimiento del enunciado;
     - herramientas y calidad;
     - calidad de las respuestas, con 94 preguntas nuevas.

     Un revisor principal consolidó los hallazgos y reprodujo los críticos.
4. **Cada agente recibió instrucciones propias:**
   - su enfoque;
   - el formato de entrega (severidad, archivo y línea, evidencia y qué hacer);
   - las mismas reglas de `AGENTS.md`.

   El agente que implementa trabaja en ciclo especificación → prueba roja → implementación → suite completa → documentación. Los revisores solo reportan; yo decido qué se corrige.

### ¿Qué tareas delegó?
Sobre mi código base:
- refactorizaciones guiadas por pruebas;
- implementación de las características que definí;
- generación de pruebas;
- afinamiento del motor, medido contra el banco y el conjunto de evaluación;
- documentación técnica;
- ejecución repetitiva de la suite.

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
- Embeddings de las líneas del corpus (se calculan al arrancar; se cachean por versión del corpus) y de las preguntas frecuentes.
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
**PostgreSQL** (gestionado), con la extensión **`pgvector`** para guardar los embeddings que hoy se calculan en memoria al arrancar.

### ¿Por qué?
- Concurrencia real y escalabilidad horizontal de lectura (réplicas), con alta disponibilidad y respaldos gestionados.
- Tipos nativos útiles: `timestamptz` para fechas, `jsonb` para fuentes (consultable e indexable), `enum`/`CHECK` para estados.
- Un solo motor para consultas, fragmentos, versiones del corpus y vectores (`pgvector`), evitando una base vectorial adicional en la primera etapa.
- Particionado por fecha y políticas de retención para 100.000 registros diarios; índices por estado y fecha para monitoreo.
- Auditoría y control de acceso por rol a nivel de base de datos.
La migración es directa: el repositorio ya aísla el SQL y el esquema actual se traduce sin cambios conceptuales.
