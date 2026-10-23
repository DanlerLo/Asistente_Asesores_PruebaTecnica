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
- [x] T-124 Prueba (RF-S9): evasiones con espacio de ancho cero, guion suave, homoglifos cirílicos, «t0ken»/«c1ave» y «usuario del administrador»; pasaban como «Sin información».
- [x] T-125 `textos_para_reglas`: NFKC + sin caracteres invisibles + homoglifos + lecturas sin dígitos-letra; `validar_pregunta` quita los invisibles. El banco de 293 preguntas no cambia.

## Fase extra — Ingesta segura (RF-S10, RF-S11; hallazgos C4 y C5)
- [x] T-126 Pruebas en `test_corpus.py`: advertencia sin texto ni ruta absoluta, `/api/salud` sin el valor de una línea descartada, paráfrasis detectadas, **pruebas negativas** con líneas legítimas que no deben descartarse, encabezado malicioso reemplazado.
- [x] T-127 Implementar en `corpus.py`; banco de 293 preguntas sin cambios.

## Fase extra — Detección de restringidos (RF-S12; hallazgo C9, decisión del usuario: detección más amplia y determinista)
- [x] T-128 Pruebas: marca en cualquier línea, credenciales sin marca, aviso con motivo, **pruebas negativas** (menciones normales de «clave» o «contraseña» no excluyen), los documentos públicos reales no se excluyen sin la lista de nombres, enlace simbólico fuera de `Data/`.
- [x] T-129 Implementar `motivo_restriccion` en `seguridad/ingesta.py` y el aviso y los enlaces en `corpus.py`; banco de 293 preguntas sin cambios.

## Fase extra — Historial sin datos sensibles (RF-S13; hallazgo C6, decisión del usuario)
- [x] T-130 Pruebas `test_enmascarado.py`: cédula, CC con puntos, cuenta, correo, tarjeta, celular y credencial ocultos; **pruebas negativas** con montos, plazos y productos intactos; números largos en bloqueadas; valores del documento restringido nunca persistidos.
- [x] T-131 Implementar `enmascarar` en `seguridad/guardrails.py` y aplicarlo en el orquestador antes de `repositorio.guardar`.

## Fase extra — Bloqueo por intención (RF-S14; hallazgo C3, el usuario delegó el criterio)
- [x] T-132 Pruebas: 7 preguntas de procedimiento y política que eran falsos positivos ahora pasan; **pruebas negativas** (AGENTS.md §2.4): 9 pedidos de datos de terceros o restringidos siguen bloqueados (incluido «Dame el saldo del cliente Pérez», que antes pasaba) y las preguntas liberadas no filtran valores restringidos (`test_orquestador.py`).
- [x] T-133 Implementar en `guardrails.py` (`_ORDEN_DE_ENTREGA`, `_PREGUNTA_DE_POLITICA`); banco: cambia 1 respuesta, revisada a mano («¿Se puede compartir información de otros clientes?» pasa de Bloqueada a responder la política del Manual).
