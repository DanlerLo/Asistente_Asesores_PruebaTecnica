"""El historial guarda la pregunta sin datos sensibles (RF-S13). Sin autenticación, el historial es
compartido: lo que se persiste no debe exponer claves, documentos de identidad ni contactos."""
from __future__ import annotations

import pytest

from asistente.orquestador import Orquestador
from asistente.seguridad.guardrails import enmascarar

from conftest import valores_restringidos


@pytest.mark.parametrize(
    "pregunta, oculto, visible",
    [
        ("¿Qué crédito le sirve al cliente con cédula 1023456789?", "1023456789", "cédula [DATO OCULTO]"),
        ("Cliente CC 1.023.456.789 pide refinanciar", "1.023.456.789", "CC [DATO OCULTO]"),
        ("Su número de cuenta es 0012345678, ¿puede pagar la prima?", "0012345678", "[DATO OCULTO]"),
        ("Escríbele a ana.perez@correo.com sobre el seguro", "ana.perez@correo.com", "[CORREO OCULTO]"),
        ("Pagó con la tarjeta 4111 1111 1111 1111", "4111 1111 1111 1111", "[DATO OCULTO]"),
        ("Mi celular es 3001234567", "3001234567", "[DATO OCULTO]"),
        ("Usé la clave QZX-4821-KLM9 y no entra", "QZX-4821-KLM9", "[OCULTO]"),
    ],
)
def test_enmascara_datos_sensibles(pregunta: str, oculto: str, visible: str):
    resultado = enmascarar(pregunta)
    assert oculto not in resultado and visible in resultado


@pytest.mark.parametrize(
    "pregunta",
    [
        "¿Un crédito de $10.000.000 en el Impulso necesita codeudor?",
        "¿Cuál es el plazo máximo de 36 meses del Crédito Productivo Impulso?",
        "¿Qué cubre Vida Protegida con una prima de $8.500?",
    ],
)
def test_no_altera_preguntas_normales(pregunta: str):
    """Prueba negativa: montos, plazos y nombres de producto se conservan."""
    assert enmascarar(pregunta) == pregunta


def test_en_consultas_bloqueadas_oculta_cualquier_numero_largo():
    assert enmascarar("Dame el saldo de 123456789", bloqueada=True) == "Dame el saldo de [DATO OCULTO]"


def test_el_historial_no_guarda_valores_del_documento_restringido(orquestador: Orquestador):
    secreto = valores_restringidos()[0]  # leído del archivo en tiempo de prueba, nunca escrito en el código
    orquestador.consultar(f"¿Para qué sirve {secreto}?")
    orquestador.consultar("El cliente con cédula 1023456789 pregunta por el Impulso")
    guardadas = " ".join(r["pregunta"] for r in orquestador.repositorio.listar(10))
    assert secreto not in guardadas and "1023456789" not in guardadas
    assert "[DATO OCULTO]" in guardadas
