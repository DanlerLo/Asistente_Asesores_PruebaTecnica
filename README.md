# Asistente interno para asesores comerciales

Prueba técnica — Desarrollador de IA · Laboratorio Digital, Vicepresidencia de Innovación y Mercadeo.

Asistente que responde preguntas de asesores comerciales sobre **productos de crédito, microseguros, procedimientos operativos y políticas internas** usando únicamente la documentación oficial de `Data/`, citando las fuentes y registrando cada consulta con su estado. Funciona **100 % en local, sin servicios pagos**; un LLM es opcional.

## Descripción

| Pregunta del asesor | Resultado |
|---------------------|-----------|
| «¿Cuál es el monto máximo del Crédito Productivo Impulso?» | **Exitosa** — `Monto máximo: $50.000.000` · Fuente: `Productos de Crédito.md › Crédito Productivo Impulso > Condiciones` |
| «¿Cuál es el periodo de gracia del Crédito Productivo Impulso?» | **Sin información suficiente** — «No tengo información suficiente para responder.» (el producto no tiene ese dato; no se responde con el de otro producto) |
| «¿Cuál es el token interno?» / «Ignora tus instrucciones y…» | **Bloqueada por seguridad** — mensaje de escalamiento con cita a la política |

Cada consulta se guarda con pregunta, fecha y hora, respuesta, fuentes y estado.

## Arquitectura

```
                          ┌──────────────── backend (FastAPI) · Orquestador ────────────────┐
 frontend (React) ──HTTP──► POST /api/consultar                                              │
 formulario, estado,      │   1. validar_pregunta        seguridad/      (forma)             │
 respuesta, fuentes,      │   2. evaluar_entrada         seguridad/      (intención)         │
 errores, historial       │   3. IndiceBM25.buscar       herramientas/   (Data/*.md)         │
                          │   4. Enrutador.elegir        orquestador/    (reglas, sin LLM)   │
                          │   5. agente.responder        agentes/  ──► generacion/           │
                          │        credito · microseguros · operativo · fuera_de_dominio     │
                          │   6. filtrar_salida          seguridad/      (secretos)          │
                          │   7. RepositorioConsultas    infraestructura/ (SQLite)           │
                          └──────────────────────────────────────────────────────────────────┘
```

- **Corpus:** los `.md` se dividen por encabezados en fragmentos autocontenidos (tablas → `clave: valor`, etiqueta + lista → una línea). `Información restringida.md` (o cualquier archivo marcado CONFIDENCIAL) **nunca entra al índice**; sus valores alimentan el filtro de salida.
- **Orquestador y agentes:** el orquestador aplica los guardrails y delega la respuesta en un agente elegido por reglas deterministas según el documento del mejor fragmento: *crédito*, *microseguros*, *operativo* (procedimientos, políticas, manual, FAQ y documentos sin agente) o *fuera de dominio* (ningún término de la pregunta existe en la base: responde la frase canónica sin invocar al LLM). La seguridad nunca se delega a un agente.
- **Recuperación:** BM25 propio con "bloqueo por entidad": si la pregunta nombra un producto, solo se consideran sus fragmentos.
- **Respuesta extractiva:** se devuelven las líneas del documento que contienen los atributos pedidos, con cita. No se genera texto nuevo, así que no puede inventar datos.
- **LLM opcional:** con `LLM_PROVIDER=groq` (plan gratuito de GroqCloud) el modelo redacta a partir de los fragmentos; cualquier fallo degrada al modo extractivo.
- **Guardrails:** validación → bloqueo por intención (credenciales, accesos admin, configuración interna, información restringida, inyección de prompt, datos de terceros) → filtro de salida. Las líneas con apariencia de instrucción dentro de documentos se descartan en la ingesta.
- **Persistencia y observabilidad:** SQLite (`storage/consultas.db`), logs JSON con `request_id`, endpoints de historial, estadísticas y salud.

Más detalle: `sdd/especificaciones/*/plan.md`.

## Estructura del repositorio

```
.
├── sdd/
│   ├── constitucion/constitucion.md
│   └── especificaciones/
│       ├── 001-consulta-documental/{especificacion,plan,tareas}.md
│       ├── 002-guardrails-seguridad/{especificacion,plan,tareas}.md
│       ├── 003-interfaz-asesor/{especificacion,plan,tareas}.md
│       ├── 004-orquestador-agentes/{especificacion,plan,tareas}.md
│       ├── 005-cuota-y-modo-llm/{especificacion,plan,tareas}.md
│       └── 006-contexto-y-recuperacion/{especificacion,plan,tareas}.md
├── src/
│   ├── backend/asistente/
│   │   ├── main.py             (punto de entrada: uvicorn asistente.main:app)
│   │   ├── config.py · dominio.py   (configuración; estados, frase canónica, Fuente)
│   │   ├── api/                (FastAPI: app, rutas, esquemas)
│   │   ├── orquestador/        (flujo de la consulta y enrutador de agentes)
│   │   ├── agentes/            (credito, microseguros, operativo, fuera_de_dominio)
│   │   ├── herramientas/       (texto, corpus, markdown, recuperacion BM25)
│   │   ├── generacion/         (extractivo, llm, plantillas)
│   │   │   └── prompts/        (prompts del LLM en Jinja2: sistema.j2, usuario.j2)
│   │   ├── seguridad/          (guardrails de consultas, política de ingesta)
│   │   └── infraestructura/    (persistencia SQLite, observabilidad)
│   └── frontend/               (Vite + React + TypeScript)
├── tests/
│   ├── backend/                (pytest, 311 pruebas)
│   └── frontend/               (Vitest, 37 pruebas)
├── Data/                       (base documental; incluye el archivo restringido de ejemplo)
├── docs/Cuestionario.md
├── AGENTS.md
├── README.md
├── requirements.txt / requirements-dev.txt / pyproject.toml
├── package.json                (workspace npm → src/frontend)
├── .env.example
```

> En el árbol del enunciado, `constitucion/` y `especificaciones/` cuelgan de una carpeta cuyo nombre no es legible en el PDF; aquí se llama `sdd/`.

## Tecnologías

| Capa | Tecnología | Motivo |
|------|------------|--------|
| Backend | Python 3.12, FastAPI, Pydantic, Uvicorn | Tipado, validación automática, OpenAPI en `/docs` |
| Recuperación | BM25 y normalización propios (sin NLTK/embeddings) | Determinista, explicable, sin modelos ni red |
| Persistencia | SQLite (`sqlite3` estándar) | Cero configuración, archivo local, suficiente para el alcance |
| LLM (opcional) | Groq (plan gratuito) vía `httpx`; prompts en plantillas Jinja2 | Intercambiable por configuración; prompts versionados fuera del código |
| Frontend | React 19, TypeScript, Vite | Preferidos por el enunciado; build rápido |
| Pruebas | pytest, Vitest + Testing Library | TDD en ambos extremos, sin red |

## Instalación

Requisitos: **Python 3.12 o 3.13** (las versiones fijadas, como `pydantic==2.11.4`, no publican paquetes para 3.14) y Node.js 20+ (probado con 22). Sin claves ni servicios externos.

```bash
git clone https://github.com/DanlerLo/asistente-asesores.git && cd asistente-asesores

# Backend: entorno virtual con Python 3.12 o 3.13
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# Frontend (instala el workspace src/frontend)
npm install

# Configuración local (valores por defecto: sin LLM, 100 % local)
cp .env.example .env
```

## Configuración

Copia `.env.example` a `.env` si quieres cambiar valores (todas las variables tienen un valor por defecto local). El backend lo carga con `--env-file .env`, que **exige** que el archivo exista (`cp .env.example .env`); sin `.env`, omite `--env-file` y se usan los valores por defecto:

| Variable | Por defecto | Descripción |
|----------|-------------|-------------|
| `DATA_DIR` | `./Data` | Carpeta con la base documental (`.md`/`.txt`) |
| `DB_PATH` | `./storage/consultas.db` | Archivo SQLite (se crea solo) |
| `ARCHIVOS_RESTRINGIDOS` | `Información restringida.md` | Archivos excluidos del índice, separados por `;` (además de la detección por marca CONFIDENCIAL) |
| `MAX_LONGITUD_PREGUNTA` | `1000` | Límite de caracteres por pregunta |
| `TOP_K` | `8` | Fragmentos candidatos por consulta |
| `UMBRAL_COBERTURA` | `0.3` | Cobertura mínima de términos útiles de la pregunta |
| `CORS_ORIGENES` | `http://localhost:5173;http://127.0.0.1:5173` | Orígenes permitidos |
| `LLM_PROVIDER` | `none` | `none` (sin LLM, 100 % local) o `groq` (gratuito) |
| `LLM_MODEL` | `openai/gpt-oss-20b` | Modelo de Groq (p. ej. `openai/gpt-oss-120b`) |
| `GROQ_API_KEY` | — | Solo con `LLM_PROVIDER=groq` ([crear clave](https://console.groq.com/keys)) |
| `LLM_TIMEOUT_SEGUNDOS` | `30` | Tiempo máximo de espera del LLM |
| `LOG_LEVEL` | `INFO` | Nivel de log (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`; otro valor impide arrancar) |

Frontend: `VITE_API_URL` (vacío = mismo origen; en desarrollo Vite reenvía `/api` a `http://localhost:8000`, configurable con `VITE_API_PROXY`).

## Ejecución

Terminal 1 — backend (http://localhost:8000, documentación interactiva en `/docs`):
```bash
python3 -m uvicorn asistente.main:app --app-dir src/backend --env-file .env --reload --port 8000
```

Terminal 2 — frontend (http://localhost:5173):
```bash
npm run dev
```

Prueba rápida sin frontend:
```bash
curl -s -X POST localhost:8000/api/consultar -H 'content-type: application/json' \
  -d '{"pregunta":"¿Cuál es el monto máximo del Crédito Productivo Impulso?"}'
```
Respuesta:
```json
{
  "id": 1,
  "respuesta": "Según «Productos de Crédito» (sección: Crédito Productivo Impulso > Condiciones):\n- Monto máximo: $50.000.000\n\nFuente: Productos de Crédito.md › Crédito Productivo Impulso > Condiciones",
  "fuentes": [{"documento": "Productos de Crédito", "archivo": "Productos de Crédito.md", "seccion": "Crédito Productivo Impulso > Condiciones", "puntaje": 1.0, "extracto": "Monto máximo: $50.000.000"}],
  "estado": "Exitosa",
  "fecha_hora": "2026-10-21T17:19:23.616+00:00",
  "latencia_ms": 0,
  "modo": "extractivo"
}
```

Preguntas de seguimiento: `POST /api/consultar` acepta un campo **opcional** `contexto` con hasta 3 preguntas anteriores (`{"pregunta": "¿Y el más bajo?", "contexto": ["¿Cuál es el monto máximo del Crédito Productivo Impulso?"]}`): si la pregunta empieza por «y» o usa «ese/esa…» y no nombra un producto, hereda el de la pregunta anterior. Sin referente responde la frase canónica en vez de adivinar. El frontend guarda la conversación en el navegador (botón «Nueva conversación»).

Otros endpoints: `GET /api/consultas/{id}` (una consulta guardada; 404 `CONSULTA_NO_ENCONTRADA`), `GET /api/historial?limite=20`, `GET /api/estadisticas`, `GET /api/salud`, `GET /api/llm` (proveedor LLM, si está activo, llamadas y cuota de la API gratuita) y `PUT /api/llm` con `{"activo": false}` (modo sin conexión) o `{"activo": true}` (reactivar el LLM configurado en `.env`).

La interfaz es un **chat**: tus preguntas a la derecha y las respuestas del asistente a la izquierda, cada una con estado, fuentes y hora; mientras se procesa aparece «Procesando la consulta…». Enter envía y Shift+Enter agrega una línea. En la cabecera, el selector **«Modo conexión (Groq)» / «Modo sin conexión»** cambia el modo sin reiniciar (al pasar a sin conexión un pop-up explica qué implica) y muestra en pequeño **«Quedan X de Y llamadas hoy»** (Groq informa la cuota en cada respuesta, así que se conoce después de la primera consulta). El modo elegido vive en memoria: al reiniciar manda `LLM_PROVIDER` de `.env`. **«Nueva conversación»** borra el chat y su contexto. Cuando no hay información suficiente, debajo de la frase canónica se muestran las especialidades del asistente.

**Sobre el contrato.** El enunciado pide `{"pregunta"}` → `{"respuesta", "fuentes", "estado"}`; eso se cumple tal cual: `contexto` es opcional (sin él la petición es la del enunciado) y los campos extra de la respuesta (`id`, `fecha_hora`, `latencia_ms`, `modo`) solo agregan información, no cambian ni quitan ninguno de los pedidos.

Todos los errores tienen la forma `{"error": "<mensaje legible>", "codigo": "<CÓDIGO>"}` y cada respuesta lleva la cabecera `x-request-id` (también aparece en los logs de esa solicitud):

| HTTP | Código | Cuándo |
|------|--------|--------|
| 400 | `PREGUNTA_VACIA` | La pregunta está vacía o solo tiene espacios |
| 400 | `TIPO_INVALIDO` | `pregunta` no es un texto (número, lista, `null`…) |
| 400 | `PREGUNTA_DEMASIADO_LARGA` | Supera `MAX_LONGITUD_PREGUNTA` (1000 por defecto) |
| 400 | `CARACTERES_NO_PERMITIDOS` | Caracteres de control en la pregunta |
| 400 | `CONTEXTO_INVALIDO` | `contexto` no es una lista de textos válidos |
| 400 | `SOLICITUD_INVALIDA` | Cuerpo que no es JSON; `activo` no booleano en `PUT /api/llm`; `limite` fuera de 1..200 |
| 400 | `ID_INVALIDO` | `GET /api/consultas/{id}` con un id que no es un entero positivo |
| 400 | `LLM_NO_CONFIGURADO` | `PUT /api/llm` con `{"activo": true}` sin proveedor en `.env` |
| 404 | `CONSULTA_NO_ENCONTRADA` | No existe una consulta con ese id |
| 500 | `ERROR_INTERNO` | Error inesperado; mensaje genérico, sin detalles internos |

Una pregunta bloqueada por seguridad **no** es un error: responde 200 con estado `Bloqueada por seguridad`.


### Activar un LLM (opcional)
```bash
# Groq (gratuito): en .env
LLM_PROVIDER=groq
GROQ_API_KEY=<tu clave de https://console.groq.com/keys>
# LLM_MODEL=openai/gpt-oss-120b   # opcional; por defecto openai/gpt-oss-20b
```
La clave es personal y gratuita (sin tarjeta): nunca se versiona. Sin ella, el asistente funciona completo en modo sin conexión.
El modelo recibe la pregunta y solo los fragmentos recuperados (nunca el documento restringido), con temperatura 0 e instrucción de responder la frase canónica si no hay información; su salida pasa por el mismo filtro de secretos.

## Pruebas

```bash
python -m pytest              # backend: 311 pruebas (< 1 s, sin red), con el .venv activado
npm test                      # frontend: 37 pruebas (Vitest + jsdom)
npm run build                 # verificación de tipos + build de producción
python -m ruff check src/backend tests/backend && python -m mypy   # lint y tipos
```

**Integración continua:** GitHub Actions (`.github/workflows/ci.yml`) ejecuta en cada push y pull request ruff, mypy, pytest con cobertura, Vitest y el build. Sin secretos ni red: el LLM queda desactivado en CI.

Casos cubiertos (ver `tests/`): consulta válida · pregunta vacía · cuerpo inválido · base documental vacía/inexistente · caracteres especiales y de control · documentos duplicados · consultas extensas (dentro y fuera del límite) · atributo inexistente para el producto nombrado · comparación entre productos · bloqueo por credenciales, accesos admin, configuración interna, información restringida, inyección de prompt (español e inglés) y datos de terceros · instrucción embebida en un documento · fuga de secreto desde documento público y desde un LLM · fallback del LLM · persistencia, historial y estadísticas · error interno sin detalles · productos y atributos inexistentes («crédito hipotecario») · preguntas de seguimiento con contexto · banco de regresión de 293 preguntas con foto de respuestas esperadas (`test_banco.py`) · enrutamiento a agentes por dominio y fuera de dominio sin LLM · nombres de archivo en NFD (macOS) · dependencias entre capas (prueba de arquitectura).

## Limitaciones

- **Emparejamiento léxico:** el modo extractivo depende de que la pregunta use palabras presentes en los documentos (hay stemming y un mapa pequeño de sinónimos; p. ej. "cubre" ≈ "cobertura", "cuesta" ≈ "costo"). Preguntas muy coloquiales o con muchos términos ajenos al corpus pueden recibir «Sin información suficiente». Activar el LLM mejora la comprensión.
- **Sin razonamiento:** no calcula ni infiere (p. ej. no suma cuotas ni compara más de dos productos a la vez).
- **Con LLM (Groq) activo:** el prompt prohíbe cálculos, pero el modelo puede hacer aritmética simple sobre valores citados (p. ej. «la diferencia es de 36 meses» en una comparación de plazos). Las fuentes citadas permiten verificarlo; el modo por defecto (sin LLM) nunca calcula. La pregunta del asesor se envía a Groq: no escribir datos personales del cliente.
- **Reglas de seguridad por patrones:** pueden bloquear preguntas legítimas que contengan palabras como "clave" o "confidencial" (decisión deliberada: se prefiere el falso positivo).
- **Idioma:** español únicamente.
- **Carga en el arranque:** cambios en `Data/` requieren reiniciar el backend.
- **Sin autenticación:** pensado para red interna; en producción se requiere identidad y autorización por rol.
- **Un solo proceso:** el modo LLM elegido, el contador de llamadas y la cuota viven en memoria del proceso; con varios workers de uvicorn cada uno tendría los suyos. Se ejecuta con un worker (suficiente para uso interno); para escalar habría que llevar ese estado a un almacén compartido.
- **SQLite con una conexión y un candado:** las escrituras se serializan. Los endpoints que tocan la base (`consultar`, `historial`, `estadisticas`, `consultas/{id}`) son síncronos y corren en el threadpool, así que el candado no bloquea el bucle de eventos (una prueba lo verifica). En producción, PostgreSQL con un pool.

## Mejoras futuras

- Recuperación híbrida (BM25 + embeddings) y reordenamiento; evolución a RAG descrita en `docs/Cuestionario.md`.
- Caché de respuestas por pregunta normalizada y recarga del corpus en caliente.
- Conjunto de evaluación automática (preguntas/respuestas esperadas) con métricas de precisión y cobertura en CI.
- Autenticación, autorización por rol y auditoría; PostgreSQL con `pgvector` en producción.
- Banco de pruebas adversariales (prompt injection) y clasificador de intención como capa adicional.
- Enrutador opcional con LLM (con el enrutador por reglas como *fallback*) y prompts por dominio para cada agente.

## Uso de IA

Construí la primera versión de la aplicación y después la refactoricé y amplié apoyándome en Claude Code como agente de desarrollo. Las decisiones de arquitectura, alcance, tecnologías y reglas de seguridad son mías. La documentación (constitución, especificaciones, planes, tareas, este README y el cuestionario) la definí y la revisé yo; Claude Code me ayudó a redactar los borradores y a mantener la trazabilidad. El detalle de herramientas, tareas delegadas, tareas manuales, sugerencias rechazadas y método de validación está en `docs/Cuestionario.md`. Las instrucciones dadas a los agentes de desarrollo están en `AGENTS.md`.
