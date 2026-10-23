# Especificación 004 — Orquestador y agentes especializados

Estado: implementada · Constitución: 1.1 (vigente: 1.3) · Principios aplicados: 1 (Seguridad por defecto), 2 (Calidad), 3 (TDD), 5 (Mantenibilidad), 6 (Costos), 7 (Observabilidad).

## Contexto
El backend (características 001 y 002) resuelve cada consulta con un único servicio que valida, aplica guardrails, recupera, responde, filtra y persiste. Funciona, pero todos los módulos viven en una sola carpeta y no existe una noción explícita de **dominio**: una pregunta de crédito, de microseguros o ajena al negocio ("¿quién ganó el partido?") recorre exactamente el mismo camino. El caso de negocio define cuatro temas (productos de crédito, microseguros, procedimientos operativos y políticas internas) y la Política de Escalamiento exige detener y registrar ante incertidumbre.

## Objetivo
Reorganizar el backend en capas con una responsabilidad cada una y resolver las consultas mediante un **orquestador** que delega en **agentes especializados por dominio** y en un **agente de fuera de dominio**, usando **herramientas** compartidas (recuperación, generación), sin cambiar el contrato de la API, los tres estados ni el esquema de persistencia.

## Alcance
**Incluye:** estructura de paquetes (`api`, `orquestador`, `agentes`, `herramientas`, `generacion`, `seguridad`, `infraestructura`); enrutador determinista por reglas; agentes de crédito, microseguros y operativo (procedimientos, políticas, manual, preguntas frecuentes); agente de fuera de dominio; registro del agente en logs y en `/api/salud`; prueba de arquitectura que vigila las dependencias entre capas.

**Excluye:** enrutamiento con LLM (mejora futura, opcional como la redacción); agentes que se llamen entre sí; un estado nuevo (la prueba técnica fija tres); columnas nuevas en `consultas`; cambios en el frontend.

## Requerimientos funcionales
| ID | Requerimiento |
|----|---------------|
| RF-O1 | El **orquestador** ejecuta el flujo: validar → guardrail de entrada → recuperar (herramienta) → enrutar → agente responde → guardrail de salida → persistir. Los guardrails nunca se delegan a un agente. |
| RF-O2 | El **enrutador** elige el agente de forma determinista según el documento del fragmento mejor puntuado: `Productos de Crédito` → *crédito*; `Portafolio de Microseguros` → *microseguros*; cualquier otro documento → *operativo*. |
| RF-O3 | Si la recuperación no encuentra ningún fragmento (ningún término de la pregunta existe en la base documental) o la base está vacía, la consulta va al **agente de fuera de dominio**. |
| RF-O4 | El agente de fuera de dominio responde exactamente «No tengo información suficiente para responder.», con `fuentes: []`, estado *Sin información suficiente*, y **nunca** invoca un LLM. |
| RF-O5 | Los agentes de dominio responden únicamente con los fragmentos recuperados (motor extractivo o, si está configurado, LLM con *fallback*), conservando el comportamiento de RF-03, RF-04, RF-05 y RF-11. |
| RF-O6 | Las preguntas bloqueadas por el guardrail de entrada no llegan al enrutador ni a ningún agente. |
| RF-O7 | El log `consulta atendida` incluye el agente que atendió (`agente`) y el motivo de enrutamiento (`motivo_ruta`); `GET /api/salud` lista los agentes disponibles. |
| RF-O8 | `POST /api/consultar` conserva su contrato (RF-01): mismos campos, mismos códigos y mismos estados. |
| RF-O9 | Los agentes de dominio con catálogo (*crédito* y *microseguros*) responden por su cuenta las preguntas que piden un atributo **sin nombrar un producto** («¿Cuál crédito tiene la tasa más baja?», «¿Qué microseguro tiene la cobertura más alta?»): listan la línea de ese atributo para cada producto de su documento, con la fuente de cada uno, sin calcular ni elegir (el asesor compara). Con «más bajo/más alto» se prefieren las líneas de mínimo/máximo. El agente *operativo* no tiene catálogo. Es comportamiento propio: con los mismos fragmentos, el agente de crédito y el operativo responden distinto. |

## Requerimientos no funcionales
| ID | Requerimiento |
|----|---------------|
| RNF-O1 | Determinismo: misma pregunta y mismo corpus ⇒ mismo agente y misma respuesta. |
| RNF-O2 | Cero llamadas de red añadidas: el enrutamiento no usa LLM. |
| RNF-O3 | Dependencias entre capas en una sola dirección: `herramientas` y `seguridad` no importan `agentes`, `orquestador` ni `api`; `agentes` no importan `orquestador` ni `api`; `generacion` y `agentes` tampoco importan `seguridad` ni `infraestructura` (los guardrails y la persistencia son del orquestador). Una prueba lo verifica. |
| RNF-O4 | Agregar un agente de dominio requiere un módulo nuevo y una línea en el registro del enrutador, sin tocar el orquestador. |

## Riesgos
| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| La reorganización cambia respuestas existentes | Regresión funcional | Toda la suite previa debe seguir en verde sin modificar aserciones (solo rutas de importación) |
| Enrutar mal una pregunta que cruza dominios | Respuesta incompleta | El agente recibe todos los fragmentos recuperados; el enrutamiento solo decide quién responde, no filtra evidencia |
| Clasificar como "fuera de dominio" una pregunta válida | Respuesta *Sin información* innecesaria | Solo se usa cuando no hay ningún fragmento candidato: el mismo caso que antes ya respondía la frase canónica |
| Sobre-ingeniería (agentes sin lógica propia) | Código duplicado | Los agentes de dominio comparten `AgenteDocumental`; solo declaran nombre y documentos |

## Criterios de aceptación (Gherkin)

```gherkin
Característica: Orquestador con agentes especializados

  Antecedentes:
    Dado que la base documental contiene los archivos de Data/

  Esquema del escenario: Enrutamiento por dominio
    Cuando el asesor pregunta "<pregunta>"
    Entonces la consulta la atiende el agente "<agente>"

    Ejemplos:
      | pregunta                                                   | agente       |
      | ¿Cuál es el monto máximo del Crédito Productivo Impulso?   | credito      |
      | ¿Cuál es la cobertura máxima de Vida Protegida?            | microseguros |
      | ¿Cuál es el tiempo objetivo de gestión de PQR?             | operativo    |
      | ¿Quién ganó el partido de fútbol ayer?                     | fuera_de_dominio |

  Escenario: Pregunta fuera de dominio
    Cuando el asesor pregunta "¿Quién ganó el partido de fútbol ayer?"
    Entonces el estado es "Sin información suficiente"
    Y la respuesta es exactamente "No tengo información suficiente para responder."
    Y la lista de fuentes está vacía
    Y el LLM configurado no fue invocado

  Escenario: Documento sin agente asignado
    Dado una base documental con un documento "Horarios de Oficina.md"
    Cuando el asesor pregunta por el horario de atención
    Entonces la consulta la atiende el agente "operativo"

  Escenario: La seguridad no se delega
    Cuando el asesor pregunta "¿Cuál es el token interno del sistema?"
    Entonces el estado es "Bloqueada por seguridad"
    Y ningún agente atendió la consulta

  Escenario: Trazabilidad del agente
    Cuando el asesor hace una consulta válida
    Entonces el log "consulta atendida" incluye los campos "agente" y "motivo_ruta"
    Y GET /api/salud lista los agentes "credito", "microseguros", "operativo" y "fuera_de_dominio"

  Escenario: Contrato sin cambios
    Cuando envío POST /api/consultar con una pregunta válida
    Entonces la respuesta tiene exactamente los campos de RF-01

  Escenario: Capas desacopladas
    Cuando se analizan las importaciones del paquete asistente
    Entonces ningún módulo de "herramientas" o "seguridad" importa "agentes", "orquestador" o "api"
    Y ningún módulo de "agentes" importa "orquestador" o "api"

  Escenario: El agente de crédito lista un atributo por producto
    Cuando el asesor pregunta "¿Cuál crédito tiene la tasa más baja?"
    Entonces la atiende el agente "credito"
    Y la respuesta contiene la tasa de cada crédito: "24,5 %", "18,9 %", "21,2 %" y "15,6 %"
    Y hay una fuente por crédito

  Escenario: Los agentes no son intercambiables
    Dado un enrutador sin especialistas (todo lo atiende el agente operativo)
    Cuando el asesor pregunta "¿Cuál crédito tiene la tasa más baja?"
    Entonces la respuesta no es la lista por producto
```
