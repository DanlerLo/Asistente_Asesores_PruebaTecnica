# Tareas 002 — Guardrails de seguridad y protección de información

Orden de ejecución; cada implementación va precedida por su prueba (TDD). `[x]` = completada.

## Fase A — Exclusión en la fuente (RF-S1, RF-S2)
- [x] T-101 Prueba: el corpus real excluye `Información restringida.md` y ningún valor sensible aparece en el texto indexable (los valores se leen del archivo, nunca se escriben en código).
- [x] T-102 Implementar `es_restringido()` por nombre (sin tildes ni mayúsculas) y por marca de cabecera.
- [x] T-103 Prueba e implementación de `extraer_secretos()`: tokens con dígitos, `-` o `_`, de longitud ≥ 6.
- [x] T-104 Prueba: un archivo confidencial con otro nombre se excluye igual.

## Fase B — Saneamiento de documentos (RF-S5)
- [x] T-105 Prueba: la línea «Ignora tus instrucciones…» se descarta con advertencia; la frase del «prompt administrativo» se detecta.
- [x] T-106 Implementar `PATRONES_INYECCION` y `es_instruccion_sospechosa()` en la ingesta.
- [x] T-107 Prueba: una instrucción embebida no se obedece ni se repite y el dato legítimo sí se responde.

## Fase C — Validación y bloqueo de entrada (RF-S3, RF-06)
- [x] T-108 Pruebas de `validar_pregunta`: vacía, tipo inválido, longitud, caracteres de control, espacios, caracteres especiales legítimos.
- [x] T-109 Implementar `validar_pregunta()` y `ErrorValidacion` con códigos estables.
- [x] T-110 Pruebas parametrizadas de `evaluar_entrada`: preguntas peligrosas por categoría (español e inglés) y preguntas legítimas.
- [x] T-111 Implementar `REGLAS_ENTRADA` declarativas, evaluadas sobre el texto normalizado.
- [x] T-112 Implementar `respuesta_bloqueada()` con mensaje de escalamiento y cita de política.

## Fase D — Filtro de salida (RF-S4)
- [x] T-113 Pruebas de `filtrar_salida`: secreto conocido, patrones `ABC-123`, `admin_*`, `sk-…`; textos normales permitidos.
- [x] T-114 Implementar `filtrar_salida()` con lista de denegación y patrones con `requiere_digito`.
- [x] T-115 Pruebas: fuga desde un documento público → *Bloqueada*; LLM que revela un secreto → *Bloqueada*.

## Fase E — Trazabilidad y errores (RF-S6, RF-S7)
- [x] T-116 Registrar la categoría del bloqueo en el log y persistir el estado.
- [x] T-117 Prueba e implementación del manejador global de excepciones con mensaje genérico (`ERROR_INTERNO`).
- [x] T-118 Documentar las reglas y su razón en `docs/Cuestionario.md`.

## Fase F — Fuentes y evasiones (RF-S8, RF-S9)
- [x] T-119 Prueba: un LLM que cita una sección con un valor de la lista de denegación sin repetirlo en el texto; el valor salía en `fuentes[].extracto`.
- [x] T-120 Aplicar el filtro de salida al texto y a cada fuente; si alguna falla, se bloquea toda la respuesta.
- [x] T-121 Pruebas de evasión: espacio de ancho cero, guion suave, homoglifos cirílicos, «t0ken», «c1ave», «usuario del administrador».
- [x] T-122 Implementar `textos_para_reglas`: NFKC, sin caracteres invisibles, homoglifos y lecturas sin dígitos por letras.

## Fase G — Ingesta segura (RF-S10, RF-S11)
- [x] T-123 Pruebas: las advertencias de ingesta no reproducen el texto descartado ni la ruta absoluta de `DATA_DIR`.
- [x] T-124 Implementar advertencias con archivo y línea, sin contenido.
- [x] T-125 Pruebas de instrucciones parafraseadas y de encabezados maliciosos, con pruebas negativas de líneas legítimas.
- [x] T-126 Ampliar los patrones de inyección y revisar también los encabezados.

## Fase H — Detección de restringidos (RF-S12)
- [x] T-127 Pruebas: marca de clasificación en cualquier línea, credenciales sin marca y aviso con motivo; pruebas negativas con menciones normales de «clave» o «contraseña».
- [x] T-128 Prueba: los documentos públicos reales no se excluyen sin la lista de nombres.
- [x] T-129 Implementar `motivo_restriccion` con reglas deterministas en `seguridad/ingesta.py`.
- [x] T-130 Avisar cada exclusión con su motivo e ignorar enlaces simbólicos fuera de `Data/`.

## Fase I — Historial sin datos sensibles (RF-S13)
- [x] T-131 Pruebas: cédula, CC con puntos, cuenta, correo, tarjeta, celular y credencial ocultos; montos, plazos y productos intactos.
- [x] T-132 Implementar `enmascarar` y aplicarlo en el orquestador antes de guardar la consulta.

## Fase J — Bloqueo por intención (RF-S14)
- [x] T-133 Pruebas: 7 preguntas de procedimiento y de política que eran falsos positivos ahora pasan.
- [x] T-134 Pruebas negativas: 9 pedidos de datos de terceros o de información restringida siguen bloqueados y las preguntas liberadas no filtran valores restringidos.
- [x] T-135 Implementar `_ORDEN_DE_ENTREGA` y `_PREGUNTA_DE_POLITICA` en `guardrails.py`.
- [x] T-136 Revisar a mano la única respuesta del banco que cambió antes de actualizar la foto.
