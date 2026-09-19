"""Vista de respaldo (`src/agents/vista_respaldo.py`): reconstruir sin modelo la vista pedida.

El caso real que la motiva, medido contra `gpt-oss-20b`: la misma pregunta de dona
por organizacion (F3) produjo una vista en 1 de 3 redacciones; en las otras dos el
modelo contesto "Lo siento, pero la categoria ... no esta disponible", el JSON no
valido y el turno termino sin grafico, sin vistas de apoyo y sin hallazgos.
"""

from __future__ import annotations

import pytest

from src.agents import vista_respaldo as vr

CONTEO_ORG_F3 = {
    "name": "consultar_agregado",
    "input_parameters": {
        "metrica": "conteo_documentos",
        "group_by": "organizacion",
        "fenomenos": "F3",
    },
    "output": "{}",
}
VISUALIZADOR = ["orquestador", "agente_analitico", "agente_visualizador"]


def test_reconstruye_la_dona_de_f3_con_los_parametros_del_conteo():
    v = vr.desde_turno(
        "Muestra en una dona la proporción de cada organización en dinámicas territoriales",
        VISUALIZADOR,
        [CONTEO_ORG_F3],
    )
    assert (v.chart, v.group_by, v.fenomenos, v.metrica) == (
        "donut",
        "organizacion",
        ["F3"],
        "conteo_documentos",
    )
    assert v.titulo == "Documentos por organización · F3"


def test_sin_el_visualizador_no_inventa_una_vista():
    """El usuario no pidio verla: una pregunta de texto no gana un grafico."""
    assert (
        vr.desde_turno(
            "cuantos documentos hay por organizacion",
            ["orquestador", "agente_analitico"],
            [CONTEO_ORG_F3],
        )
        is None
    )
    assert vr.desde_turno("hola", [], []) is None


@pytest.mark.parametrize(
    "pregunta, group_by, esperado",
    [
        ("Grafica en dona la participación de cada organización", "organizacion", "donut"),
        ("¿Qué parte del total aporta cada fuente?", "fuente", "donut"),
        ("Muéstrame la evolución de los documentos", "fenomeno", "timeline"),
        ("Dame una tabla por organización", "organizacion", "table"),
        ("Barras apiladas por formato", "formato", "stacked_bar"),
        ("Grafica los documentos por organización", "organizacion", "bar"),
        ("lo que sea", "anio", "timeline"),  # por año, siempre serie temporal
        ("dona por año", "anio", "timeline"),  # una dona de años no dice nada
    ],
)
def test_elige_el_grafico_por_las_palabras_de_la_pregunta(pregunta, group_by, esperado):
    assert vr.elegir_grafico(pregunta, group_by) == esperado


def test_una_serie_temporal_lleva_el_aviso_de_cobertura():
    llamada = {
        "name": "consultar_agregado",
        "input_parameters": {"metrica": "conteo_documentos", "group_by": "anio", "fenomenos": "F2"},
    }
    v = vr.desde_turno("Grafica la evolución anual", VISUALIZADOR, [llamada])
    assert v.chart == "timeline" and v.fenomenos == ["F2"]
    assert "34%" in v.nota, (
        "toda vista temporal impone el aviso: no se confia en que alguien lo recuerde"
    )


def test_una_vista_no_temporal_no_lleva_aviso():
    v = vr.desde_turno("Grafica por organización", VISUALIZADOR, [CONTEO_ORG_F3])
    assert v.nota == ""


def test_el_conteo_de_fragmentos_se_respeta():
    llamada = {
        "name": "consultar_agregado",
        "input_parameters": {
            "metrica": "conteo_fragmentos",
            "group_by": "formato",
            "fenomenos": "",
        },
    }
    v = vr.desde_turno("Grafica los fragmentos por formato", VISUALIZADOR, [llamada])
    assert v.metrica == "conteo_fragmentos" and v.fenomenos == []
    assert v.titulo == "Fragmentos por formato"


def test_sin_conteo_se_deduce_de_la_pregunta_y_solo_con_un_fenomeno_claro():
    v = vr.desde_turno(
        "Grafica por organización los documentos de seguridad espacial", VISUALIZADOR, []
    )
    assert (v.group_by, v.fenomenos) == ("organizacion", ["F2"])
    # dos fenomenos nombrados, o ninguno: sin filtro. Ante la duda, los tres.
    v2 = vr.desde_turno(
        "Grafica por organización la inteligencia artificial y el espacio", VISUALIZADOR, []
    )
    assert v2.fenomenos == []


def test_un_fenomeno_invalido_en_el_conteo_no_rompe_la_vista():
    llamada = {
        "name": "consultar_agregado",
        "input_parameters": {
            "metrica": "conteo_documentos",
            "group_by": "organizacion",
            "fenomenos": "F9",
        },
    }
    v = vr.desde_turno("Grafica por organización", VISUALIZADOR, [llamada])
    assert v.fenomenos == []


def test_una_dimension_fuera_del_vocabulario_devuelve_none_en_vez_de_lanzar():
    llamada = {
        "name": "consultar_agregado",
        "input_parameters": {"metrica": "conteo_documentos", "group_by": "lugar", "fenomenos": ""},
    }
    assert vr.desde_turno("Grafica por lugar", VISUALIZADOR, [llamada]) is None


def test_usa_la_primera_consulta_del_analitico():
    otra = {"name": "consultar_agregado", "input_parameters": {"group_by": "formato"}}
    v = vr.desde_turno("Grafica", VISUALIZADOR, [CONTEO_ORG_F3, otra])
    assert v.group_by == "organizacion"
