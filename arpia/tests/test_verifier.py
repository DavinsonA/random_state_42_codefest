"""Pruebas del verificador condicional (`src/agents/verifier.py`).

Dos propiedades, y la segunda importa tanto como la primera:

1. Que atrape una cita inventada.
2. Que **no se active** en una respuesta sana. Un verificador que salta siempre
   duplica el coste del turno sin comprar nada, y el Bloque B se normaliza
   contra los otros equipos.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.agents import verifier
from src.agents.verifier import MIN_CHARS_SIN_CITAS, SIN_EVIDENCIA, diagnosticar, verificar

EVIDENCIA = [
    {"doc_id": "F2-SWF-120", "chunk_id": "c1", "texto": "texto real", "citacion": "F2-SWF-120"},
    {"doc_id": "F2-SWF-117", "chunk_id": "c2", "texto": "otro texto", "citacion": "F2-SWF-117"},
]

SANA = "Segun F2-SWF-120, las capacidades crecieron. F2-SWF-117 lo confirma."
FABRICADA = "Segun F2-INVENTADO-999, las capacidades crecieron."
LARGA_SIN_CITAS = "Las capacidades antisatelite crecieron de forma sostenida. " * 6


@pytest.fixture(autouse=True)
def _contador_limpio():
    verifier.contador = verifier.Contador()
    yield


@pytest.fixture
def llm(monkeypatch):
    class FakeLLM:
        def __init__(self):
            self.llamadas = 0
            self.fallar = False

        def invoke(self, mensajes):
            self.llamadas += 1
            if self.fallar:
                raise RuntimeError("gateway caido")
            return SimpleNamespace(
                content="Respuesta corregida segun F2-SWF-120.",
                usage_metadata={"input_tokens": 500, "output_tokens": 90},
            )

    fake = FakeLLM()
    from src.agents import executors

    monkeypatch.setattr(executors, "_llm", lambda agente: fake)
    return fake


# -- deteccion determinista (0 tokens) ---------------------------------------


def test_detecta_una_cita_que_no_se_recupero():
    """No hay interpretacion posible: el identificador esta en la evidencia o no."""
    d = diagnosticar(FABRICADA, EVIDENCIA)
    assert d.fabricadas == {"F2-INVENTADO-999"}
    assert d.requiere_verificacion


def test_una_respuesta_bien_citada_no_dispara_nada():
    d = diagnosticar(SANA, EVIDENCIA)
    assert not d.fabricadas and not d.sin_citas
    assert not d.requiere_verificacion


def test_una_respuesta_larga_sin_citas_es_sospechosa():
    assert len(LARGA_SIN_CITAS) >= MIN_CHARS_SIN_CITAS
    assert diagnosticar(LARGA_SIN_CITAS, EVIDENCIA).sin_citas


def test_una_respuesta_corta_sin_citas_no_lo_es():
    """Suele ser un "no encontre evidencia", que no tiene nada que verificar.
    Sin este guardia el verificador se activa en todos los turnos."""
    assert not diagnosticar("No encontre evidencia.", EVIDENCIA).sin_citas


def test_sin_evidencia_toda_cita_queda_sin_respaldo():
    """No es un falso positivo: si no se recupero nada, ningun identificador
    citado esta sustentado en este turno."""
    d = diagnosticar(SANA, [])
    assert d.fabricadas == {"F2-SWF-120", "F2-SWF-117"}


# -- comportamiento ----------------------------------------------------------


def test_una_respuesta_sana_no_cuesta_ni_una_llamada(llm):
    assert verificar(SANA, EVIDENCIA) == SANA
    assert llm.llamadas == 0
    assert verifier.contador.activaciones == 0


def test_una_cita_inventada_se_corrige(llm):
    salida = verificar(FABRICADA, EVIDENCIA)
    assert llm.llamadas == 1
    assert "F2-INVENTADO-999" not in salida
    assert verifier.contador.correcciones == 1


def test_citar_sin_evidencia_degrada_sin_gastar_nada(llm):
    """Afirmar con fuentes cuando no se recupero ninguna no se puede corregir:
    no hay con que."""
    salida = verificar("Segun F1-ALGO-001 esto es asi.", [])
    assert salida == SIN_EVIDENCIA
    assert llm.llamadas == 0
    assert verifier.contador.degradaciones == 1


def test_si_falla_la_correccion_se_degrada_en_vez_de_mentir(llm):
    llm.fallar = True
    assert verificar(FABRICADA, EVIDENCIA) == SIN_EVIDENCIA


def test_si_falla_la_correccion_de_una_respuesta_sin_citas_se_conserva(llm):
    """No hay cita inventada que retirar: el texto puede ser correcto aunque no
    cite. Degradarlo seria destruir una respuesta util."""
    llm.fallar = True
    assert verificar(LARGA_SIN_CITAS, EVIDENCIA) == LARGA_SIN_CITAS


def test_el_contador_permite_calibrar_el_disparador(llm):
    verificar(SANA, EVIDENCIA)
    verificar(SANA, EVIDENCIA)
    verificar(FABRICADA, EVIDENCIA)
    s = verifier.contador.stats()
    assert s["turnos"] == 3 and s["activaciones"] == 1
    assert s["tasa_activacion"] == pytest.approx(0.333, abs=0.01)


# -- evidencia agregada: conteos exactos, no documentos citables ------------

AGREGADA = [
    {
        "chunk_id": "agregado:organizacion:SIPRI",
        "doc_id": "F3-SIPRI-015, F3-SIPRI-017",
        "texto": "SIPRI: 128 documentos",
        "citacion": "conteo exacto sobre 1826 documentos",
    }
]
CONTEO = "Conteo de documentos por organizacion:\n- SIPRI: 128 documentos\n" * 4


def test_un_conteo_exacto_no_necesita_citar_documentos(llm):
    """Con el gateway real, el verificador exigio citas a una tabla de conteos y
    la reescritura acabo 'citando' `agregado:organizacion:SIPRI` como si fuera
    un documento. Un conteo exacto es evidencia por si mismo."""
    assert len(CONTEO) >= MIN_CHARS_SIN_CITAS
    d = diagnosticar(CONTEO, AGREGADA)
    assert not d.requiere_verificacion
    assert verificar(CONTEO, AGREGADA) == CONTEO
    assert llm.llamadas == 0


def test_la_evidencia_documental_sigue_exigiendo_citas(llm):
    """El arreglo no puede apagar el verificador cuando si hay que citar."""
    assert diagnosticar(LARGA_SIN_CITAS, [*AGREGADA, *EVIDENCIA]).sin_citas
