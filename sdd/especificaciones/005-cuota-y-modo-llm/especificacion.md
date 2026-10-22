# Especificación 005 — Cuota de la API gratuita y modo sin conexión

Estado: implementada · Constitución: 1.1 (vigente: 1.2) · Principios aplicados: 4 (Uso responsable de IA), 6 (Costos), 7 (Observabilidad).

## Contexto
Con `LLM_PROVIDER=groq` (RF-11) el asistente usa el plan gratuito de GroqCloud, limitado por solicitudes por minuto y por día. Hoy el asesor no sabe cuántas llamadas quedan ni puede dejar de usar el LLM sin editar `.env` y reiniciar el backend. Groq informa la cuota en cabeceras de **cada** respuesta (`x-ratelimit-limit-requests`, `x-ratelimit-remaining-requests`, `x-ratelimit-reset-requests` para el día; `*-tokens` para tokens por minuto) y no ofrece un endpoint para consultarla sin hacer una solicitud.

## Objetivo
Mostrar en la interfaz cuántas llamadas quedan en la API gratuita y permitir desactivarla (modo sin conexión: solo motor extractivo) o reactivarla, sin reiniciar y sin cambiar el contrato de `POST /api/consultar`.

## Alcance
**Incluye:** registro de la cuota desde las cabeceras de Groq (también en respuestas 429); contador de llamadas desde el arranque; `GET /api/llm` y `PUT /api/llm`; panel en el frontend con la cuota y el botón de modo.

**Excluye:** persistir el modo entre reinicios (al arrancar manda `.env`); activar un proveedor que no esté configurado en `.env`; autenticación del botón (la aplicación no tiene usuarios, ver limitaciones).

## Requerimientos funcionales
| ID | Requerimiento |
|----|---------------|
| RF-L1 | Tras cada respuesta de Groq (exitosa o de error, incluido 429) se registra: límite y restantes de solicitudes por día, límite y restantes de tokens por minuto, segundos hasta la recarga de cada uno y la hora de la última actualización. Cabeceras ausentes o mal formadas se registran como desconocidas, sin fallar. |
| RF-L2 | Se cuentan las llamadas hechas al proveedor desde el arranque (exitosas y fallidas). |
| RF-L3 | `GET /api/llm` devuelve `{"proveedor", "modelo", "activo", "modo", "llamadas", "cuota"}`; `proveedor` es `null` si `.env` no configura ninguno; `cuota` es `null` hasta la primera llamada o si el proveedor no informa cuota. |
| RF-L4 | `PUT /api/llm` con `{"activo": false}` pasa a modo sin conexión: las consultas siguientes no llaman al LLM y responden con el motor extractivo (`modo: "extractivo"`). Con `{"activo": true}` se reactiva el proveedor configurado. |
| RF-L5 | `PUT /api/llm` con `activo` no booleano devuelve 400 `SOLICITUD_INVALIDA`; activar sin proveedor configurado devuelve 400 `LLM_NO_CONFIGURADO`. Ninguno cambia el modo. |
| RF-L6 | El frontend muestra en la cabecera un selector compacto de dos botones, «Modo conexión (Groq)» y «Modo sin conexión», con el activo marcado (`aria-pressed`). Al pasar a modo sin conexión aparece un pop-up pequeño que explica el modo (responde solo con la documentación, sin enviar datos a Groq ni gastar cuota; entiende menos paráfrasis) con un botón «Entendido». En modo conexión se muestra en pequeño «Quedan X de Y llamadas hoy» (o que se conocerá tras la primera consulta), con aviso por debajo del 10 % y de cuota agotada. Sin proveedor configurado solo se muestra la etiqueta «Modo sin conexión», sin botones. Si `GET /api/llm` falla, el selector no se muestra y la aplicación funciona. |
| RF-L7 | `POST /api/consultar` conserva su contrato (RF-01): no se agregan campos. |

## Requerimientos no funcionales
| ID | Requerimiento |
|----|---------------|
| RNF-L1 | Cero llamadas extra a Groq para conocer la cuota: solo se leen cabeceras de las llamadas que ya ocurren. |
| RNF-L2 | La clave `GROQ_API_KEY` nunca aparece en `GET /api/llm`, logs ni errores. |
| RNF-L3 | Las pruebas no usan red (`httpx.post` y `fetch` simulados). |

## Riesgos
| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| La cuota mostrada está desactualizada (solo cambia con cada llamada) | El asesor ve un número viejo | Se muestra la hora de la última actualización |
| Cualquiera con acceso a la interfaz cambia el modo | Se reactiva el envío a un servicio externo | Solo se puede reactivar el proveedor que una persona configuró en `.env`; desactivar es siempre seguro; autenticación por rol es mejora de producción |
| Al reiniciar se pierde el modo elegido | Vuelve a usar el LLM | Documentado: `.env` es la fuente de verdad al arrancar (`LLM_PROVIDER=none` para dejarlo apagado) |

## Criterios de aceptación (Gherkin)

```gherkin
Característica: Cuota de la API gratuita y modo sin conexión

  Escenario: Cuota leída de las cabeceras de Groq
    Dado LLM_PROVIDER=groq
    Cuando Groq responde con x-ratelimit-limit-requests 1000 y x-ratelimit-remaining-requests 997
    Entonces GET /api/llm devuelve cuota.solicitudes_restantes 997 y cuota.solicitudes_limite 1000
    Y llamadas aumenta en 1

  Escenario: Cuota agotada
    Cuando Groq responde 429 con x-ratelimit-remaining-requests 0
    Entonces la consulta se responde en modo extractivo
    Y GET /api/llm devuelve cuota.solicitudes_restantes 0

  Escenario: Desactivar la API gratuita
    Cuando envío PUT /api/llm con {"activo": false}
    Entonces GET /api/llm devuelve activo false y modo "extractivo"
    Y una consulta válida se responde sin llamar al LLM

  Escenario: Reactivar la API gratuita
    Dado que la API gratuita está desactivada
    Cuando envío PUT /api/llm con {"activo": true}
    Entonces las consultas vuelven a usar Groq

  Escenario: Sin proveedor configurado
    Dado LLM_PROVIDER=none
    Cuando envío PUT /api/llm con {"activo": true}
    Entonces el código HTTP es 400 con codigo "LLM_NO_CONFIGURADO"
    Y el panel muestra "Modo sin conexión" sin botón

  Escenario: Selector de modo en la interfaz
    Dado que quedan 997 de 1000 llamadas
    Cuando abro la aplicación
    Entonces veo "Quedan 997 de 1000 llamadas hoy" y el botón "Modo conexión (Groq)" activo
    Cuando pulso "Modo sin conexión"
    Entonces ese botón queda activo
    Y aparece un pop-up que explica el modo sin conexión, que se cierra con "Entendido"
```
