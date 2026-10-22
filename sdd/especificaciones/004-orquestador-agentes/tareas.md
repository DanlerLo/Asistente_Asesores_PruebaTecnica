# Tareas 004 — Orquestador y agentes especializados

Orden de ejecución; prueba antes que implementación. `[x]` = completada.

## Fase A — Preparación
- [x] T-501 Corregir la suite en rojo: nombres de archivo en NFD (macOS) se normalizan a NFC en `cargar_corpus` (prueba `test_nombres_de_archivo_se_normalizan_a_nfc`).
- [x] T-502 Redactar especificación, plan y tareas de la característica 004.

## Fase B — Pruebas que fallan
- [x] T-503 `test_arquitectura.py`: dependencias entre capas (RNF-O3).
- [x] T-504 `test_agentes.py`: enrutamiento por dominio, fuera de dominio sin LLM, documento sin agente, base vacía, seguridad antes de agentes, determinismo, log y salud.
- [x] T-505 Ejecutar la suite y confirmar el fallo (paquetes y módulos inexistentes).

## Fase C — Reorganización en capas (sin cambio de comportamiento)
- [x] T-506 Extraer estados, frase canónica, `Fuente` y `RespuestaGenerada` a `dominio.py`.
- [x] T-507 Mover `texto`, `corpus`, `recuperacion` a `herramientas/`.
- [x] T-508 Mover `motor` (→ `extractivo`), `llm`, `plantillas`, `prompts/` a `generacion/`.
- [x] T-509 Mover `guardrails` a `seguridad/`; `persistencia` y `observabilidad` a `infraestructura/`.
- [x] T-510 Mover la aplicación FastAPI a `api/app.py`; `main.py` queda como punto de entrada.
- [x] T-511 Actualizar importaciones de las pruebas existentes (sin tocar aserciones) y ejecutar la suite de regresión.

## Fase D — Orquestador y agentes
- [x] T-512 `agentes/base.py`: protocolo `Agente` y `AgenteDocumental` (extractivo o LLM con *fallback*).
- [x] T-513 Agentes `credito`, `microseguros`, `operativo` y `fuera_de_dominio`.
- [x] T-514 `orquestador/enrutador.py`: reglas RF-O2/RF-O3 y registro de agentes.
- [x] T-515 `orquestador/orquestador.py` (antes `servicio.py`): delega en el agente y registra `agente` y `motivo_ruta`.
- [x] T-516 `/api/salud` lista los agentes disponibles.
- [x] T-517 Suite completa en verde (`python3 -m pytest`, `npm test`, `npm run build`).

## Fase E — Documentación
- [x] T-518 Constitución 1.1 (principio 5 con la nueva estructura), `README.md`, `AGENTS.md` y `docs/Cuestionario.md`.

## Fase F — Revisión adversarial
- [x] T-522 Revisión independiente (regresión, seguridad, empaquetado, trazabilidad) con verificación de cada hallazgo; 5 confirmados (severidad baja), 2 descartados.
- [x] T-523 Prueba negativa + filtro `dato` en `generacion/plantillas.py`: un documento o una pregunta no pueden cerrar el bloque `<fragmentos>`/`<pregunta>` ni inyectar un fragmento falso.
- [x] T-524 `test_api.py::test_consulta_valida` exige el conjunto **exacto** de campos (RF-O8); la prueba de arquitectura detecta `from asistente import <capa>` y vigila `dominio.py`/`config.py`; trazabilidad RF-O2/RF-O3 corregida.

## Pendientes / mejoras futuras (fuera de alcance)
- [ ] T-519 Enrutador opcional con LLM (clasificación de intención) activado por variable de entorno, con el enrutador por reglas como *fallback*.
- [ ] T-520 Persistir el agente que atendió cada consulta (requiere cambiar el esquema de `consultas`: decisión humana).
- [ ] T-521 Prompts del sistema por dominio (`prompts/<agente>/sistema.j2`).
