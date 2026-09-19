"""Pruebas de las dimensiones derivadas del corpus (`src/retrieval/enrich.py`).

Se ejercitan contra rutas reales de `metadata.jsonl`. Son funciones puras: ni
tocan disco ni consumen tokens.
"""

from __future__ import annotations

import pytest

from src.retrieval.enrich import anio, enrich, fenomeno_id, fenomeno_numero, organizacion

RUTA_REAL = (
    "F1_IA_y_Capacidades_Estrategicas/Atlantic_Council/GeoTech_Cues/page_04/"
    "ATLCOUNCIL_01-beyond-chips-prioritizing-standardization.json"
)


def test_organizacion_sale_del_segundo_nivel_de_la_ruta():
    assert organizacion(RUTA_REAL) == "Atlantic_Council"
    assert organizacion("F2_Seguridad_Espacial/CSIS_Aerospace/informe.pdf") == "CSIS_Aerospace"


@pytest.mark.parametrize("ruta", ["", "solo_un_nivel.pdf", "/", "///"])
def test_organizacion_vacia_en_vez_de_adivinada(ruta):
    assert organizacion(ruta) == ""


@pytest.mark.parametrize(
    ("ruta", "esperado"),
    [
        ("F2/CSIS/space-threat-assessment-2024.pdf", 2024),
        ("F1/Stanford/AI_Index_2025/cap03.pdf", 2025),
        ("F3/ILIA/informe.pdf", None),
    ],
)
def test_anio_se_lee_de_la_ruta(ruta, esperado):
    assert anio(ruta) == esperado


@pytest.mark.parametrize("ruta", ["modelo-4096-tokens.pdf", "chunk-1024.json", "doc-1750.pdf"])
def test_anio_ignora_cifras_que_no_son_fechas(ruta):
    """4096 y 1024 aparecen en textos tecnicos; no son anos."""
    assert anio(ruta) is None


def test_traduccion_entre_el_entero_del_corpus_y_el_id_del_contrato():
    """La metadata usa `fenomeno: 2`; el contrato usa `"F2"`."""
    assert fenomeno_id(2) == "F2"
    assert fenomeno_numero("F2") == 2
    assert fenomeno_id(9) is None
    assert fenomeno_numero("F9") is None
    assert fenomeno_id(None) is None


def test_enrich_anade_sin_mutar_el_original():
    fila = {"doc_id": "F1-ATLCOUNCIL-001", "fuente": RUTA_REAL, "fenomeno": 1, "texto": "x"}
    salida = enrich(fila)
    assert salida["organizacion"] == "Atlantic_Council"
    assert salida["fenomeno_id"] == "F1"
    assert salida["fenomeno_nombre"] == "IA y Capacidades Estrategicas"
    assert "organizacion" not in fila  # no se toca la fila original


def test_enrich_omite_lo_que_no_pudo_derivar():
    """Ausencia distinguible de vacio: `anio` no identificado no es `anio: null`."""
    salida = enrich({"fuente": "F3/ILIA/informe.pdf", "fenomeno": 3})
    assert "anio" not in salida
    assert salida["organizacion"] == "ILIA"
