"""Pruebas de la voz del sistema (`src/agents/voz.py`).

El usuario lee texto de nueve sitios y solo uno es un prompt de modelo. Estas
pruebas vigilan que ninguno se desvie: que las respuestas fijas salgan del
modulo, que reencaucen en vez de solo negar, y que el registro no contradiga
las reglas del reto.
"""

from __future__ import annotations

import re

import pytest

from src.agents import voz

FIJAS = [
    voz.SIN_CONSULTA,
    voz.SIN_EVIDENCIA,
    voz.SIN_RESULTADOS,
    voz.FUERA_DE_DOMINIO,
    voz.PETICION_RECHAZADA,
    voz.SIN_REDACCION,
    voz.SERVICIO_DEGRADADO,
    voz.MODO_NO_HABILITADO,
]


@pytest.mark.parametrize("texto", FIJAS)
def test_las_respuestas_fijas_llevan_tildes(texto):
    """Un producto dirigido a oficiales con la ortografia rota se lee como un
    producto descuidado, y el tono es el 25% del bloque de calidad."""
    sospechosas = re.findall(
        r"\b(analisis|informacion|documentacion|consulta s|razon|tambien|"
        r"unicamente|reformulacion|operativo s)\b",
        texto,
    )
    assert not sospechosas, sospechosas


@pytest.mark.parametrize("texto", FIJAS)
def test_ninguna_respuesta_fija_tutea(texto):
    """El registro es impersonal: se le habla a un analista, no a un usuario de
    aplicacion de consumo."""
    assert not re.search(r"\b(preguntame|te respondo|tu consulta|puedes|dime)\b", texto.lower())


@pytest.mark.parametrize("texto", FIJAS)
def test_ninguna_respuesta_fija_trae_relleno(texto):
    for muletilla in ("excelente pregunta", "espero que", "no dudes", "¡", "lamento"):
        assert muletilla not in texto.lower()


@pytest.mark.parametrize(
    "texto", [voz.SIN_CONSULTA, voz.SIN_RESULTADOS, voz.FUERA_DE_DOMINIO, voz.PETICION_RECHAZADA]
)
def test_los_rechazos_reencauzan_hacia_el_corpus(texto):
    """Negar sin decir que si se puede preguntar deja al analista sin salida."""
    assert "inteligencia artificial" in texto
    assert "espacial" in texto
    assert "territoriales" in texto


# -- el registro que comparten los prompts -----------------------------------


def test_el_registro_prohibe_pronosticar():
    """`RETO.md` prohibe presentar como medicion objetiva cualquier puntaje
    calculado ad-hoc. Este sistema reporta lo que el corpus registra."""
    assert "Sin pronosticos ni probabilidades" in voz.REGISTRO


def test_el_registro_exige_neutralidad_tecnica():
    """Toxicity es el 15% del bloque de calidad y el corpus habla de actores
    armados y capacidades antisatelite: el registro militar mal calibrado
    deriva con facilidad a lenguaje adversarial."""
    assert "Neutralidad tecnica" in voz.REGISTRO
    assert "adversarial" in voz.REGISTRO


def test_el_registro_pide_la_conclusion_primero():
    assert "La conclusion va primero" in voz.REGISTRO


def test_el_registro_exige_procedencia_caracterizada():
    """Citar solo `F2-SWF-120` es opaco para un humano; con organizacion y ano
    la frase es legible y sigue siendo verificable."""
    assert "organizacion, ano e" in voz.REGISTRO


def test_los_prompts_de_modelo_usan_el_registro_compartido():
    """Si un prompt define su propio tono, el sistema habla de dos maneras."""
    from src.agents.executors import REDACCION_PROMPT

    assert voz.REGISTRO in REDACCION_PROMPT
    assert voz.DOMINIO in REDACCION_PROMPT


def test_el_registro_no_nombra_a_ninguna_institucion():
    """La denominacion de la fuerza ha cambiado por ley, sentencia y acto
    legislativo. El sistema solo afirma lo que esta en el corpus, y eso no lo
    esta: si hace falta nombrarla, es configuracion, no conocimiento del modelo.
    """
    for nombre in ("Fuerza Aerea", "Fuerza Aeroespacial", "FAC", "Colombia"):
        assert nombre not in voz.REGISTRO


def test_el_registro_prohibe_filtrar_el_andamiaje():
    """La version anterior del prompt producia citas como
    `(documento_recuperado id="F2-SWF-079__chunk_000322")` dentro de la
    respuesta: estructura interna del sistema entregada al usuario como si
    fuera contenido."""
    assert "Nunca menciones la estructura interna" in voz.REGISTRO
    assert "documento_recuperado" in voz.REGISTRO
