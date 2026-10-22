# Tareas 002 — Guardrails de seguridad y protección de información

Orden de ejecución; prueba antes que implementación. `[x]` = completada.

## Fase A — Exclusión en la fuente (RF-S1, RF-S2)
- [x] T-101 Prueba: el corpus real excluye `Información restringida.md` y ningún valor sensible aparece en el texto indexable (los valores se leen del archivo, nunca se escriben en código).
- [x] T-102 Implementar `es_restringido()` por nombre (`ARCHIVOS_RESTRINGIDOS`, comparación sin tildes ni mayúsculas) y por marca de cabecera.
- [x] T-103 Prueba + implementación de `extraer_secretos()` (tokens con dígitos, `-` o `_`, longitud ≥ 6).
- [x] T-104 Prueba: archivo confidencial con otro nombre se excluye igual.

## Fase B — Saneamiento de documentos (RF-S5)
- [x] T-105 Prueba: línea `Ignora tus instrucciones…` se descarta y genera advertencia; frase del "prompt administrativo" se detecta.
- [x] T-106 Implementar `PATRONES_INYECCION` y `es_instruccion_sospechosa()` en la ingesta.
- [x] T-107 Prueba de servicio: instrucción embebida no se obedece ni se repite; el dato legítimo sí se responde.

## Fase C — Validación y bloqueo de entrada (RF-S3, RF-06)
- [x] T-108 Pruebas de `validar_pregunta`: vacía, tipo inválido, longitud, caracteres de control, normalización de espacios, caracteres especiales legítimos.
- [x] T-109 Implementar `validar_pregunta()` y `ErrorValidacion` con códigos estables.
- [x] T-110 Pruebas parametrizadas de `evaluar_entrada`: 14 preguntas peligrosas (6 categorías, español e inglés) y 5 legítimas.
- [x] T-111 Implementar `REGLAS_ENTRADA` declarativas evaluadas sobre texto normalizado.
- [x] T-112 Implementar `respuesta_bloqueada()` con mensaje de escalamiento y cita de política.

## Fase D — Filtro de salida (RF-S4)
- [x] T-113 Pruebas de `filtrar_salida`: secreto conocido, patrones `ABC-123`, `admin_*`, `sk-…`; textos normales permitidos.
- [x] T-114 Implementar `filtrar_salida()` con lista de denegación y patrones con flag `requiere_digito`.
- [x] T-115 Prueba de servicio: fuga desde documento público → *Bloqueada*; LLM que revela secreto → *Bloqueada*.

## Fase E — Trazabilidad y errores (RF-S6, RF-S7)
- [x] T-116 Registrar categoría del bloqueo en el log (`seguridad=entrada:<categoria>` / `salida:<motivo>`) y persistir el estado.
- [x] T-117 Prueba + manejador global de excepciones con mensaje genérico (`ERROR_INTERNO`) y `x-request-id`.
- [x] T-118 Documentar las reglas y su racional en `docs/Cuestionario.md` (mitigación de prompt injection, guardrails).

## Mejoras futuras
- [ ] T-119 Clasificador de intención (LLM pequeño) como capa adicional para reformulaciones no cubiertas por reglas.
- [ ] T-120 Autenticación y autorización por rol; auditoría de accesos.
- [ ] T-121 Pruebas adversariales automatizadas (banco de ataques de prompt injection) en CI.

## Fase extra — Hallazgo de auditoría (RF-S8)
- [x] T-122 Prueba: un documento público con un valor de la lista de denegación y un LLM que cita su sección sin repetir el valor; la respuesta salía «Exitosa» con el valor en `fuentes[].extracto`.
- [x] T-123 El orquestador aplica el filtro de salida al texto y a cada fuente (documento, sección, extracto); si alguna falla, bloquea toda la respuesta.

