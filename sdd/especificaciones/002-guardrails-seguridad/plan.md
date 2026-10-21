# Plan 002 — Guardrails de seguridad y protección de información

## Arquitectura propuesta: defensa en profundidad

```
Data/*.md ──► corpus.cargar_corpus
               ├─ es_restringido()      ─► excluido del índice ─► extraer_secretos() ─► lista de denegación
               └─ fragmentar()          ─► es_instruccion_sospechosa() ─► línea descartada + advertencia

pregunta ──► guardrails.validar_pregunta  (forma: tipo, vacía, longitud, control)   → HTTP 400
         ──► guardrails.evaluar_entrada   (intención: 6 categorías de reglas)       → Bloqueada
         ──► recuperación + motor/LLM      (solo documentos no restringidos)
         ──► guardrails.filtrar_salida    (lista de denegación + patrones)           → Bloqueada
         ──► persistencia + log (categoría del bloqueo, nunca el valor sensible)
```

Cuatro barreras independientes: aunque una falle, las demás evitan la fuga. La más importante es la primera: **lo que no está indexado no se puede recuperar**.

## Componentes
| Componente | Responsabilidad |
|------------|-----------------|
| `corpus.es_restringido` | Decide exclusión por nombre (`ARCHIVOS_RESTRINGIDOS`) o por marca en la cabecera del archivo |
| `corpus.extraer_secretos` | Construye la lista de denegación con tokens que contienen dígitos, `-` o `_` (≥ 6 caracteres) |
| `corpus.es_instruccion_sospechosa` | Patrones de instrucción (`ignora tus instrucciones`, `prompt administrativo`, `si un usuario pregunta… entregue`) |
| `guardrails.validar_pregunta` | Errores de forma con códigos estables |
| `guardrails.evaluar_entrada` | Reglas por categoría: `credenciales`, `acceso_administrativo`, `configuracion_interna`, `informacion_restringida`, `inyeccion_de_prompt`, `datos_de_terceros` |
| `guardrails.filtrar_salida` | Lista de denegación + patrones (`ABC-123…` con dígito, `admin_*`, `sk-…`) |
| `motor.respuesta_bloqueada` | Mensaje de bloqueo con cita a *Manual del Asesor › Información Sensible* y *Políticas › Escalamiento* |
| `main.py` | Manejador global de excepciones con mensaje genérico; `x-request-id` para correlación |

## Decisiones
- **ADR-S1 Reglas declarativas en vez de clasificador ML.** Son auditables, rápidas, deterministas y se prueban una a una; un clasificador puede añadirse después como capa adicional, nunca como sustituto.
- **ADR-S2 La lista de denegación se deriva del documento restringido en tiempo de carga.** Evita copiar secretos al código y cubre valores que los patrones genéricos no anticipen.
- **ADR-S3 El bloqueo responde con estado 200 y estado lógico "Bloqueada por seguridad"**, no con 403: es una respuesta válida del asistente que debe persistirse y mostrarse al asesor con su explicación.
- **ADR-S4 Se prefiere el falso positivo al falso negativo** (RNF-S3): las reglas incluyen términos genéricos como "clave" o "confidencial".
- **ADR-S5 Las pruebas leen los valores sensibles del archivo** en lugar de escribirlos en el código (RNF-S4).

## Estrategia de pruebas
| Archivo | Cubre |
|---------|-------|
| `tests/backend/test_corpus.py` | exclusión por nombre y por marca, extracción de secretos, líneas de instrucción descartadas |
| `tests/backend/test_guardrails.py` | validación de forma; 14 preguntas peligrosas por categoría; 5 preguntas legítimas; filtro de salida positivo y negativo |
| `tests/backend/test_servicio.py` | bloqueo extremo a extremo sin fuga, inyección embebida, fuga desde documento público, LLM que revela un secreto |
| `tests/backend/test_api.py` | bloqueo por HTTP sin fuga en el cuerpo, error interno genérico |

Criterio de salida: ninguna prueba de la suite contiene literalmente un valor del archivo restringido (`grep` en CI).

## Trazabilidad
| RF | Pruebas |
|----|---------|
| RF-S1 | `test_corpus_real_excluye_documento_restringido_y_extrae_secretos`, `test_documento_marcado_confidencial_se_excluye_aunque_tenga_otro_nombre` |
| RF-S2 | `test_extraer_secretos_reconoce_identificadores_tecnicos` |
| RF-S3 | `test_preguntas_peligrosas_se_bloquean`, `test_consultas_sobre_informacion_restringida_se_bloquean_y_no_filtran_secretos`, `test_consulta_bloqueada_por_seguridad` |
| RF-S4 | `test_salida_con_secreto_conocido_se_bloquea`, `test_filtro_de_salida_bloquea_respuesta_con_secreto`, `test_llm_que_filtra_un_secreto_es_bloqueado_por_el_filtro_de_salida` |
| RF-S5 | `test_fragmentar_descarta_lineas_con_instrucciones_para_el_asistente`, `test_instruccion_inyectada_en_un_documento_no_se_obedece_ni_se_repite` |
| RF-S6 | `test_historial_y_estadisticas` (bloqueo persistido) |
| RF-S7 | `test_error_interno_no_expone_detalles` |
