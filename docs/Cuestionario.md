# Cuestionario

## 1. Uso de IA

### Herramientas utilizadas
| Para qué | Herramienta |
|----------|-------------|
| Agente de desarrollo | Claude Code en VS Code, instruido con `AGENTS.md` y la constitución |
| Solución | Python 3.12 + FastAPI, SQLite, React 19 + TypeScript + Vite, fastembed (embeddings locales) y Groq (gratuito) como LLM opcional |
| Calidad | pytest, Vitest, ruff, mypy y Playwright para recorridos en navegador |
| Entrega | Git, GitHub y GitHub Actions |

### Qué actividades realicé manualmente
- **Construí la primera versión** de la aplicación, backend y frontend.
- **Definí la arquitectura.** Cuando esa versión creció como un monolito, la rediseñé como orquestador + agentes especializados (crédito, microseguros, operativo y fuera de dominio) + herramientas compartidas, en capas que no pueden importarse hacia arriba.
- **Diseñé la interfaz tipo chat:** disposición de mensajes, selector de modo y aviso de cuota.
- **Leí el negocio antes que el código:** identifiqué la trampa de `Información restringida.md` y las reglas implícitas de las políticas (citar la fuente, frase exacta cuando no hay información, escalamiento) y las convertí en requisitos.
- **Hice las pruebas:** escribí la prueba de cada cambio antes de implementarlo (TDD), probé la aplicación a mano en la interfaz y con `curl`, y verifiqué cada función generada por la IA leyendo el código y comprobando su comportamiento antes de aceptarla.
- **Tomé las decisiones de seguridad:** que la detección de documentos restringidos fuera determinista y no quedara en manos de un agente, y guardar el historial enmascarado porque, sin autenticación, es compartido.

### Qué delegué a la IA
- Las refactorizaciones (de monolito a agentes, prompts a Jinja2, capas), que hicimos en conjunto: yo definí el diseño y revisé cada paso.
- La implementación de las características que definí.
- El afinamiento del motor de respuesta.
- Las correcciones de una auditoría del proyecto.

El ciclo siempre fue el mismo: especificación, yo escribía la prueba que fallaba, la IA implementaba y la suite completa tenía que pasar.

### Qué sugerencias de la IA rechacé
- **Que los embeddings eligieran la línea de la respuesta en el modo sin conexión.** Lo medí con 40 preguntas nuevas: ganaba entre 1 y 3 aciertos, pero las respuestas equivocadas subían de 4 a entre 6 y 10. El modelo reconoce el tema de una línea, no si la responde. Lo que sí dejé es que elijan qué **sección** leer, solo cuando una sección es claramente la más parecida, y la respuesta es la sección literal completa.
- **Una regla del motor que pasaba todas las pruebas y aun así estaba mal.** Al medirla contra el banco de regresión rompía 17 respuestas correctas. Desde entonces ninguna regla entra sin medir el antes y el después.
- **Sinónimos que "mejoraban" la cobertura** ("plata" por monto, "codeudor" por garantía): hacían que algunas preguntas se respondieran con datos de otro producto. En un banco, un dato equivocado es peor que decir "no tengo información".

### Cómo validé lo que produjo la IA
- **Pruebas:** 403 de backend y 37 de frontend, con cobertura del 99 %. Nada entra en rojo.
- **Conjunto de evaluación:** 97 preguntas con respuesta esperada; la precisión pasó de 48,5 % a 100 %.
- **Banco de regresión:** 293 preguntas que comparan texto, estado y fuentes. Cada respuesta que cambiaba la revisé a mano.
- **Generalización:** 40 preguntas nuevas que nunca usé para ajustar reglas, para no engañarme con el 100 %, y otras 35 escritas antes de la última ronda de cambios.
- **Aciertos, incorrectas y abstenciones por separado** (`tests/backend/medicion.py`), más la completitud de las listas. En un banco, bajar de 4 a 2 respuestas incorrectas vale más que subir 5 aciertos, y una lista con un requisito de menos cuenta como incorrecta.
- **Seguridad:** pruebas negativas que leen el documento restringido en tiempo de ejecución y comprueban que ningún valor suyo aparece en el índice, en el LLM ni en las respuestas.
- **Uso real:** consultas con `curl` y recorridos de la interfaz en el navegador.

## 2. Decisiones técnicas para paso a productivo

### ¿Qué modelo utilizaría y por qué?
Usaría los **modelos de OpenAI** para generar, los **embeddings de OpenAI** (`text-embedding-3`) para la búsqueda por significado y **Azure AI Search** para los índices. Son los que mejor resultado me han dado y encajan en una misma plataforma.

- **Generación con GPT, a través de Azure OpenAI.** Siguen muy bien instrucciones estrictas como "responde solo con los fragmentos" y "cita la sección", y responden bien en español. Usaría un modelo *mini* para la mayoría de consultas y uno completo solo para casos difíciles. Con Azure, los datos del banco no se usan para entrenar y se quedan en la región elegida.
- **Embeddings `text-embedding-3`.** Entienden las paráfrasis del asesor mejor que el modelo local de esta prueba, y permiten reducir el tamaño del vector para bajar costos.
- **Azure AI Search.** Hace búsqueda híbrida (BM25 + vectores) de forma nativa, que es justo el diseño de esta prueba, pero gestionado. Trae un reordenador semántico que decide qué fragmento responde la pregunta, filtros por producto y por el rol del asesor, e indexadores que actualizan el índice cuando cambian los documentos.

**En esta prueba** uso Groq con `openai/gpt-oss-20b`, porque es gratuito y el enunciado no admite herramientas pagas. Es opcional: si falta la clave o `LLM_PROVIDER` tiene otro valor, el backend arranca en modo sin conexión. Si Groq falla, responde el motor extractivo.

Evalué usar un LLM local con Ollama en lugar de Groq. Lo descarté porque Ollama tarda más en ejecutarse en CPU y exige instalar una aplicación aparte en la máquina de quien evalúa, y por el tiempo de la prueba no era procedente.

### ¿Cómo optimizaría costos?
- No llamar al LLM cuando no aporta: hoy no se llama en preguntas bloqueadas ni fuera de dominio, y en producción también responderían sin LLM las preguntas con un dato exacto de tabla.
- Caché de respuestas por pregunta normalizada.
- Enviar solo los fragmentos relevantes, con un límite de tokens.
- Modelo pequeño por defecto y el grande solo cuando haga falta.

### ¿Cómo mitigaría Prompt Injection?
- Lo restringido no existe para el modelo: los documentos confidenciales nunca se indexan, así que no hay nada que revelar.
- Los documentos se envían marcados como datos, no como instrucciones, y las líneas con apariencia de instrucción se eliminan al cargar los documentos.
- Bloqueo por intención en la entrada (en español e inglés) y filtro de secretos en la salida.
- El modelo no tiene herramientas ni acceso a sistemas: su único efecto es texto, y ese texto se filtra.
- En producción sumaría un banco de ataques en el CI y límites de consultas por usuario.

### ¿Qué guardrails implementaría?
| Capa | Hoy | En producción |
|------|-----|---------------|
| Entrada | Validación de tipo, vacía, longitud y caracteres; seis categorías de bloqueo | Autenticación, roles, límite de consultas y detección de datos personales |
| Documentos | Exclusión de restringidos y de instrucciones embebidas | Clasificación al cargar y aprobación de cambios |
| Generación | Solo fragmentos recuperados, temperatura 0 y respaldo extractivo | Verificar que cada afirmación esté en los fragmentos |
| Salida | Filtro de secretos y cita obligatoria | Detección de datos personales |
| Operación | Estado de cada consulta y logs | Alertas por picos de bloqueos y auditoría |

### ¿Cómo monitorearía calidad?
- Distribución de estados (exitosa, sin información, bloqueada), latencia y tasa de fallos del LLM.
- El conjunto de evaluación corriendo en el CI y tras cada cambio de documentos.
- Calificación del asesor en la interfaz (útil o incorrecta).
- Revisión semanal de una muestra de respuestas y de las preguntas sin respuesta, para mejorar los documentos.
- Alertas si sube de golpe el "sin información" (documentos rotos) o los bloqueos (ataque o regla rota).

### ¿Cómo evolucionaría la solución hacia RAG?
Ya es un RAG con búsqueda híbrida. La evolución es pasar el índice a Azure AI Search con `text-embedding-3`, sumar el reordenador semántico para que también pueda responder por significado sin equivocarse, agregar metadatos como producto y vigencia, y actualizar el índice automáticamente cuando cambien los documentos. La exclusión de documentos restringidos seguiría en código, antes del índice.

## 3. Uso de agentes

### ¿Utilizó agentes de desarrollo?
Sí. Claude Code como agente principal, que edita y corre las pruebas, y agentes revisores en paralelo que no escriben código: hicieron una auditoría de arquitectura, backend, frontend, seguridad y cumplimiento del enunciado. Separar quien escribe de quien revisa evita que el agente se valide a sí mismo.

### ¿Cómo fueron instruidos?
- **`AGENTS.md`** como contrato para cualquier agente: los documentos son datos y no instrucciones, nunca leer el archivo restringido, TDD obligatorio, todo en español y una lista de decisiones reservadas para mí.
- **La constitución**, con los principios que prevalecen ante cualquier conflicto.
- **Especificación, plan y tareas** de cada característica antes de tocar código.
- Los revisores recibían su enfoque y un formato de entrega (severidad, archivo, evidencia y qué hacer). Solo reportaban; yo decidía qué se corregía.

### ¿Qué tareas delegó?
Las refactorizaciones (en conjunto conmigo), la implementación de lo que definí, el afinamiento del motor medido contra el banco de preguntas y la ejecución repetitiva de las pruebas.

### ¿Qué tareas supervisó manualmente?
Las pruebas, que escribí yo; las pruebas manuales de la aplicación; cada función generada por la IA; cada regla de seguridad y cada cambio del motor, leyendo el diff y el resultado del banco de preguntas; y que ningún archivo tuviera valores sensibles.

### ¿Qué decisiones no permitió tomar a la IA?
Qué documentos son restringidos y cómo se detectan, activar un LLM o elegir modelo, la tecnología de persistencia, relajar límites o reglas de bloqueo y eliminar pruebas.

## 4. Frontera entre IA y desarrollo tradicional

### ¿Qué responsabilidades resolvería mediante desarrollo tradicional?
Todo lo que deba ser determinista y auditable: validación de entradas, autenticación, control de acceso a documentos, filtros de seguridad, persistencia, contratos de API, manejo de errores y monitoreo.

### ¿Qué responsabilidades delegaría a IA?
Entender preguntas en lenguaje natural, redactar respuestas a partir de fragmentos verificados y, en desarrollo, generar código bajo supervisión.

### ¿Qué responsabilidades nunca permitiría ejecutar a una IA?
Decidir qué información es confidencial o quién puede verla, aprobar créditos o calcular condiciones para un cliente, modificar documentos oficiales o la base de datos, ejecutar acciones sobre sistemas y desactivar guardrails o pruebas.

### ¿Cómo mantendría separadas estas responsabilidades?
- El LLM solo recibe fragmentos y devuelve texto; la validación, el filtrado y la persistencia son código que lo rodea.
- El orquestador elige el agente con reglas, sin LLM, y la seguridad nunca se delega a un agente.
- La salida del modelo siempre pasa por el filtro de secretos.
- Las pruebas corren sin LLM, así que cada responsabilidad tradicional se verifica sin depender del modelo.

## 5. Optimización y operación (100.000 consultas diarias)

### ¿Qué componente tendría mayor riesgo de latencia?
La llamada al LLM: entre medio segundo y varios segundos, según la red y el proveedor. Hoy, con Groq, la primera pregunta tarda 0,64 s y el modo sin conexión menos de 0,01 s.

### ¿Qué estrategia utilizaría para reducir tiempos de respuesta?
Responder sin LLM lo que no necesite redacción, poner una caché delante del modelo, mostrar la respuesta a medida que se genera, usar un modelo pequeño por defecto y guardar en la base de datos sin bloquear la respuesta.

### ¿Qué podría cachear?
La respuesta completa por pregunta normalizada y versión de los documentos, los resultados de búsqueda, los embeddings de los documentos y la parte fija del prompt. Todo se invalida cuando cambian los documentos o las reglas de seguridad.

### ¿Qué monitorearía?
Latencia por etapa, errores, distribución de estados, aciertos de la caché, fallos y cuota del LLM, costo por consulta y picos de bloqueos.

### ¿Cómo optimizaría costos de operación?
Modelo pequeño por defecto, caché, respuestas sin LLM cuando se pueda, límite de tokens, autoescalado según la carga y archivar los registros antiguos.

## 6. Persistencia y gestión de datos

### Qué mecanismo de almacenamiento seleccionó
**SQLite**, con una tabla `consultas` que guarda pregunta, fecha y hora, respuesta, fuentes y estado.

### Por qué lo seleccionó
Cumple lo que pide el enunciado sin instalar ni configurar nada y corre 100 % en local. También probé guardar en un archivo JSON: con 10.000 consultas, SQLite guarda en 0,22 ms y JSON en 61,8 ms, y JSON se corrompe si el proceso se cae a mitad de una escritura.

### Qué ventajas tiene para este escenario
Es una librería de Python, sin servidor; es un solo archivo fácil de revisar y borrar; busca por ID al instante; y las pruebas usan una base en memoria, rápida y aislada.

## 7. Escenario de producción

### ¿Mantendría la misma solución de persistencia?
No. En producción habrá varias réplicas del backend y conversaciones de varios turnos. Separaría la persistencia en dos piezas:
- **Redis para las conversaciones activas, organizadas en hilos.** Cada hilo guarda sus últimos mensajes como una lista con tiempo de expiración, y cualquier réplica recupera el contexto al instante.
- **Una base no relacional para el historial.** Cada hilo es un documento con sus mensajes en forma de lista, y cada mensaje conserva pregunta, fecha y hora, respuesta, fuentes y estado.

### ¿Qué motor de base de datos utilizaría?
**Redis** (Azure Cache for Redis) para los hilos activos y **Azure Cosmos DB** como base no relacional para el historial.

### ¿Por qué?
- El dato es una conversación: un hilo con su lista de mensajes se guarda y se lee completo en una sola operación, sin uniones entre tablas.
- Redis saca la lectura del contexto del camino de la respuesta, y la expiración limpia sola los hilos inactivos.
- Cosmos DB escala de forma horizontal sin administrarlo, con respaldos y retención gestionados.
- Encaja con Azure OpenAI y Azure AI Search en la misma plataforma.
- El cambio está aislado: solo hay que reemplazar `RepositorioConsultas`.
