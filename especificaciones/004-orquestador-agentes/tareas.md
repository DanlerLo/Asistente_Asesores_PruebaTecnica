# Tareas 004 — Orquestador y agentes especializados

Orden de ejecución; cada implementación va precedida por su prueba (TDD). `[x]` = completada.

## Fase A — Preparación
- [x] T-301 Corregir la suite en rojo: los nombres de archivo en NFD (macOS) se normalizan a NFC en `cargar_corpus`.
- [x] T-302 Redactar la especificación, el plan y las tareas de la característica 004.

## Fase B — Pruebas que fallan
- [x] T-303 `test_arquitectura.py`: dependencias entre capas (RNF-O3).
- [x] T-304 `test_agentes.py`: enrutamiento por dominio, fuera de dominio sin LLM, documento sin agente, base vacía, seguridad antes de los agentes, determinismo, log y salud.
- [x] T-305 Ejecutar la suite y confirmar el fallo.

## Fase C — Reorganización en capas, sin cambio de comportamiento
- [x] T-306 Extraer estados, frase canónica, `Fuente` y `RespuestaGenerada` a `dominio.py`.
- [x] T-307 Mover `texto`, `corpus` y `recuperacion` a `herramientas/`.
- [x] T-308 Mover el motor extractivo, `llm`, `plantillas` y `prompts/` a `generacion/`.
- [x] T-309 Mover `guardrails` a `seguridad/`, y `persistencia` y `observabilidad` a `infraestructura/`.
- [x] T-310 Mover la aplicación FastAPI a `api/app.py`; `main.py` queda como punto de entrada.
- [x] T-311 Actualizar las importaciones de las pruebas existentes, sin tocar aserciones, y correr la regresión.

## Fase D — Orquestador y agentes
- [x] T-312 `agentes/base.py`: protocolo `Agente` y `AgenteDocumental` (extractivo o LLM con *fallback*).
- [x] T-313 Agentes `credito`, `microseguros`, `operativo` y `fuera_de_dominio`.
- [x] T-314 `orquestador/enrutador.py`: reglas RF-O2 y RF-O3 y registro de agentes.
- [x] T-315 `orquestador/orquestador.py`: delega en el agente y registra `agente` y `motivo_ruta`.
- [x] T-316 `/api/salud` lista los agentes disponibles.
- [x] T-317 Suite completa en verde (pytest, `npm test`, `npm run build`).

## Fase E — Documentación
- [x] T-318 Actualizar la constitución (principio 5), `README.md`, `AGENTS.md` y `docs/Cuestionario.md`.

## Fase F — Revisión independiente
- [x] T-319 Revisión de regresión, seguridad, empaquetado y trazabilidad, verificando cada hallazgo (5 confirmados, 2 descartados).
- [x] T-320 Prueba negativa y filtro `dato`: un documento o una pregunta no pueden cerrar el bloque `<fragmentos>` ni inyectar un fragmento falso.
- [x] T-321 `test_consulta_valida` exige el conjunto exacto de campos (RF-O8); la prueba de arquitectura detecta todas las formas de importar una capa.

## Fase G — Módulos más pequeños
- [x] T-322 Catálogo por agente: crédito y microseguros listan un atributo por producto cuando la pregunta no nombra ninguno (RF-O9).
- [x] T-323 Mover la política de ingesta a `seguridad/ingesta.py` y pasarla a `cargar_corpus` por inyección (`FiltroIngesta`).
- [x] T-324 Mover el parser a `herramientas/markdown.py` y dividir `fragmentar` en `_Fragmentador`, un método por tipo de línea.
- [x] T-325 Dividir `crear_app` en `api/app.py` (composición), `api/rutas.py` y `api/esquemas.py`.
- [x] T-326 Comentarios de una línea y comparación archivo-documento compartida (`pertenece_a`); verificado que el código no cambia.
