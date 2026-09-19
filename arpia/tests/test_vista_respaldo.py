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


# -- el usuario pidio ver algo aunque el orquestador no llamara al visualizador ------------------


def _conteo(**p):
    base = {"metrica": "conteo_documentos", "group_by": "organizacion", "fenomenos": "F3"}
    return {"name": "consultar_agregado", "input_parameters": {**base, **p}}


def test_una_tabla_pedida_con_todas_las_letras_sale_aunque_no_se_llamo_al_visualizador():
    v = vr.desde_turno(
        "Dame una tabla con las 5 organizaciones que mas publican sobre dinamicas territoriales",
        ["orquestador", "agente_analitico"],
        [_conteo()],
    )
    assert (v.chart, v.group_by, v.fenomenos) == ("table", "organizacion", ["F3"])


def test_una_pregunta_de_evolucion_lleva_el_periodo_del_conteo():
    v = vr.desde_turno(
        "Como ha cambiado la produccion sobre inteligencia artificial entre 2020 y 2025?",
        ["orquestador", "agente_analitico"],
        [_conteo(group_by="anio", fenomenos="F1", desde="2020", hasta="2025")],
    )
    assert (v.chart, v.desde, v.hasta) == ("timeline", "2020", "2025")


def test_un_ano_mal_escrito_no_tumba_la_vista():
    v = vr.desde_turno(
        "Grafica la evolucion",
        ["agente_visualizador"],
        [_conteo(group_by="anio", desde="dos mil", hasta="")],
    )
    assert v.chart == "timeline" and v.desde is None and v.hasta is None


def test_una_sola_cifra_es_un_kpi_sin_dimension():
    v = vr.desde_turno(
        "Dime en una sola cifra cuantos documentos tiene el corpus",
        ["orquestador", "agente_analitico"],
        [_conteo(group_by="fenomeno", fenomenos="")],
    )
    assert v.chart == "kpi" and v.group_by is None and v.titulo == "Documentos en total"


def test_sin_conteo_una_palabra_de_grafico_no_alcanza():
    """Sin un conteo del analista no hay de donde sacar los datos: no se inventa la vista."""
    assert vr.desde_turno("Dame una tabla de lo que sea", ["orquestador"], []) is None


@pytest.mark.parametrize(
    "pregunta",
    [
        "Muestrame en un mapa donde ocurren mas incidentes de counterspace",
        "Grafica la distribucion geografica de los documentos",
        "Dame la ubicacion de las organizaciones",
    ],
)
def test_lo_que_el_corpus_no_tiene_no_se_sustituye_por_otra_vista(pregunta):
    """El visualizador declino bien; una barra por fenomeno no responde a un mapa."""
    assert vr.desde_turno(pregunta, VISUALIZADOR, [CONTEO_ORG_F3]) is None


@pytest.mark.parametrize(
    "pregunta, esperado",
    [
        ("Como ha cambiado esto entre 2020 y 2025?", ("2020", "2025")),
        ("Documentos de 2018 a 2022 por organizacion", ("2018", "2022")),
        ("entre 2025 y 2020", ("2020", "2025")),
        ("Todo lo publicado desde 2021", ("2021", None)),
        ("Documentos por organizacion", (None, None)),
        ("Hay 5 organizaciones y 2 formatos", (None, None)),
    ],
)
def test_el_periodo_se_toma_de_la_pregunta(pregunta, esperado):
    assert vr.periodo_de_pregunta(pregunta) == esperado


def test_el_periodo_pedido_llega_a_la_vista_aunque_el_analista_no_lo_aplico():
    v = vr.desde_turno(
        "Grafica la evolucion entre 2020 y 2025",
        ["agente_visualizador"],
        [_conteo(group_by="anio")],
    )
    assert (v.desde, v.hasta) == ("2020", "2025")


@pytest.mark.parametrize(
    "pregunta, esperado",
    [
        ("Dame una tabla con las 5 organizaciones que mas publican", 5),
        ("los 10 principales formatos", 10),
        ("top 3 de fuentes", 3),
        ("Hay 5 organizaciones", None),
        ("las 99 organizaciones", None),
        ("por organizacion", None),
    ],
)
def test_el_tope_se_toma_de_la_pregunta(pregunta, esperado):
    assert vr.limite_de_pregunta(pregunta) == esperado


def test_el_tope_llega_a_la_vista_pero_no_a_un_kpi_ni_a_una_serie_temporal():
    llamadas = [_conteo()]
    v = vr.desde_turno(
        "Dame una tabla con las 5 organizaciones que mas publican",
        ["agente_visualizador"],
        llamadas,
    )
    assert (v.chart, v.limite) == ("table", 5)
    kpi = vr.desde_turno("en una sola cifra los 5 primeros", ["agente_visualizador"], llamadas)
    assert kpi.limite is None
    serie = vr.desde_turno(
        "evolucion de los 5 primeros anos", ["agente_visualizador"], [_conteo(group_by="anio")]
    )
    assert serie.limite is None


# -- el idioma lo pone quien pregunta, no el modelo -----------------------------------------------


def _vista(**k):
    from src.api.contracts import ViewSpec

    return ViewSpec(**{"chart": "bar", "group_by": "organizacion", **k})


def test_un_titulo_en_ingles_para_una_pregunta_en_espanol_se_corrige():
    v = vr.en_espanol(
        _vista(titulo="Top 3 organizations by document count", fenomenos=["F2"]),
        "Las 3 organizaciones que mas publican sobre seguridad espacial en barras",
    )
    assert v.titulo == "Documentos por organización · F2"


def test_un_titulo_en_espanol_se_respeta():
    titulo = "Documentos sobre seguridad del entorno espacial por organización"
    assert (
        vr.en_espanol(_vista(titulo=titulo), "Grafica por organizacion los documentos").titulo
        == titulo
    )


def test_una_pregunta_en_ingles_conserva_el_titulo_en_ingles():
    v = vr.en_espanol(
        _vista(titulo="Top 3 organizations by document count"),
        "Show the top 3 organizations by documents",
    )
    assert v.titulo == "Top 3 organizations by document count"


def test_una_nota_en_ingles_se_descarta_para_que_el_codigo_ponga_el_aviso_en_espanol():
    v = vr.en_espanol(
        _vista(nota="Only 34% of the documents declare the year"),
        "Dame la evolucion de los documentos por organizacion",
    )
    assert v.nota == ""


def test_el_titulo_de_un_cruce_nombra_las_dos_dimensiones():
    assert (
        vr.titulo_por_defecto("stacked_bar", "conteo_documentos", "fenomeno", [], "formato")
        == "Documentos por fenómeno y formato"
    )


# -- la vista adopta lo que el analista conto -----------------------------------------------------


def test_sin_dimension_en_la_instruccion_la_vista_adopta_la_que_conto_el_analista():
    """El caso real: el visualizador recibio "muestra un grafico de barras" y cayo a fenomeno."""
    vista = _vista(
        group_by="fenomeno",
        fenomenos=["F1", "F2", "F3"],
        titulo="Conteo de documentos por fenómeno",
    )
    v = vr.reconciliar(vista, [_conteo(group_by="organizacion", fenomenos="F2")])
    assert (v.group_by, v.fenomenos) == ("organizacion", ["F2"])
    assert v.titulo == "Documentos por organización · F2", "el titulo viejo diria otra cosa"


def test_una_vista_elegida_con_informacion_no_se_toca():
    vista = _vista(group_by="formato", fenomenos=["F3"])
    assert vr.reconciliar(vista, [_conteo(group_by="organizacion", fenomenos="F2")]) is vista


def test_una_serie_temporal_y_una_cifra_no_se_reconcilian():
    for chart in ("timeline", "kpi"):
        vista = _vista(chart=chart, group_by=None)
        assert vr.reconciliar(vista, [_conteo(group_by="organizacion")]) is vista


def test_sin_conteo_no_hay_con_que_reconciliar():
    vista = _vista(group_by="fenomeno")
    assert vr.reconciliar(vista, []) is vista


def test_si_el_analista_conto_por_fenomeno_no_se_filtra_a_un_solo_fenomeno():
    """Una barra de una sola categoria no dice nada."""
    vista = _vista(group_by="fenomeno", fenomenos=[])
    assert vr.reconciliar(vista, [_conteo(group_by="fenomeno", fenomenos="F2")]) is vista
