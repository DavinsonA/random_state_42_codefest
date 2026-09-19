"""`POST /api/view` entrega la vista lista para pintar (series, hallazgos, apoyo).

Antes la GUI hacia tres peticiones (una por fenomeno) y armaba las series por su
cuenta; los hallazgos solo existian cuando la vista nacia de `/chat`. Ahora una
sola llamada devuelve todo, con los `doc_id` que sustentan cada frase.
"""

from __future__ import annotations

import os

os.environ.setdefault("ARPIA_MODE", "stub")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from src.api.main import app  # noqa: E402
from src.retrieval import aggregates  # noqa: E402

client = TestClient(app)


def _docs(fenomeno: str, org: str, n: int, anio: int | None = None) -> list[dict]:
    return [
        {
            "doc_id": f"{fenomeno}-{org}-{i:03d}",
            "fenomeno": fenomeno,
            "organizacion": org,
            "formato": "pdf" if i % 2 else "html",
            "anio": anio,
            "n_fragmentos": 10,
        }
        for i in range(n)
    ]


#: F3 esta concentrada en dos organizaciones (6 + 4 de 13); F1 y F2 son planas.
TABLA = [
    *_docs("F3", "Alertas", 6),
    *_docs("F3", "SIPRI", 4),
    *_docs("F3", "RESDAL", 1),
    *_docs("F3", "CEPAL", 1),
    *_docs("F3", "OEA", 1),
    *_docs("F1", "CSET", 2, anio=2024),
    *_docs("F1", "CSIS", 1, anio=2025),
    *_docs("F2", "ESA", 2, anio=2024),
]


@pytest.fixture(autouse=True)
def _tabla(monkeypatch):
    monkeypatch.setattr(aggregates, "tabla", lambda: TABLA)
    yield
    aggregates.reset()


def _view(**spec):
    return client.post("/api/view", json=spec).json()


# -- series --------------------------------------------------------------------


def test_por_organizacion_trae_una_serie_por_fenomeno():
    r = _view(chart="bar", group_by="organizacion")
    assert r["disponible"] and r["serie_por"] == "fenomeno"
    assert [s["clave"] for s in r["series"]] == ["F1", "F2", "F3"]
    assert all(len(s["valores"]) == len(r["categorias"]) for s in r["series"])
    assert r["series"][2]["etiqueta"] == "F3 · Dinámicas Territoriales"


def test_las_series_suman_lo_mismo_que_las_filas_planas():
    """Una sola verdad: la matriz y `filas` nunca discrepan."""
    r = _view(chart="stacked_bar", group_by="organizacion")
    por_cat = {c: sum(s["valores"][i] for s in r["series"]) for i, c in enumerate(r["categorias"])}
    assert por_cat == {f["clave"]: f["valor"] for f in r["filas"]}
    assert sum(por_cat.values()) == r["total"]


def test_las_categorias_van_por_total_descendente_y_las_del_ano_cronologicas():
    r = _view(chart="bar", group_by="organizacion", fenomenos=["F3"])
    assert r["categorias"][:2] == ["Alertas", "SIPRI"]
    t = _view(chart="timeline")
    assert t["group_by"] == "anio" and t["categorias"] == ["2024", "2025"]


def test_agrupar_por_fenomeno_es_una_sola_serie_total():
    r = _view(chart="donut", group_by="fenomeno")
    assert r["serie_por"] is None
    assert [s["clave"] for s in r["series"]] == ["total"]
    assert r["categorias"] == ["F3", "F1", "F2"]
    assert r["series"][0]["valores"] == [13, 3, 2]


def test_cada_celda_lleva_los_doc_id_que_la_sustentan():
    r = _view(chart="bar", group_by="organizacion", fenomenos=["F3"])
    celda = r["series"][0]["doc_ids"][r["categorias"].index("Alertas")]
    assert celda and all(d.startswith("F3-Alertas-") for d in celda)


def test_el_conteo_de_fragmentos_pesa_por_fragmento():
    r = _view(chart="bar", metrica="conteo_fragmentos", group_by="fenomeno")
    assert r["series"][0]["valores"] == [130, 30, 20]


def test_se_conserva_filas_para_quien_ya_las_consume():
    r = _view(chart="bar", group_by="organizacion")
    assert {"clave", "valor", "doc_ids"} <= r["filas"][0].keys()


# -- hallazgos y apoyo ------------------------------------------------------------


def test_los_hallazgos_llegan_con_soporte_y_doc_ids():
    r = _view(chart="bar", group_by="organizacion", fenomenos=["F3"])
    assert r["hallazgos"], "un reparto concentrado tiene algo que decir"
    h = r["hallazgos"][0]
    assert h["texto"] and h["soporte"] and h["doc_ids"]
    assert all(d.startswith("F3-") for d in h["doc_ids"])


def test_un_reparto_plano_no_inventa_hallazgos(monkeypatch):
    plano = _docs("F1", "A", 2) + _docs("F1", "B", 2) + _docs("F1", "C", 2) + _docs("F1", "D", 2)
    monkeypatch.setattr(aggregates, "tabla", lambda: plano)
    r = _view(chart="bar", group_by="organizacion")
    assert r["hallazgos"] == [] and r["complementarias"] == []


def test_las_complementarias_son_view_specs_validos_y_como_mucho_dos():
    from src.api.contracts import ViewSpec

    r = _view(chart="bar", group_by="organizacion", fenomenos=["F3"])
    assert 1 <= len(r["complementarias"]) <= 2
    for c in r["complementarias"]:
        ViewSpec.model_validate(c)
    assert r["complementarias"][0]["chart"] == "donut"


def test_una_vista_de_una_cifra_no_se_rodea_de_graficas():
    assert _view(chart="kpi")["complementarias"] == []


def test_chat_y_view_dicen_lo_mismo_de_la_misma_vista():
    """Un solo camino: `apoyo_de_vista` alimenta a los dos."""
    from src.api.chat import _componer_tablero
    from src.api.contracts import ViewSpec

    spec = {"chart": "bar", "group_by": "organizacion", "fenomenos": ["F3"]}
    vistas, textos = _componer_tablero(ViewSpec.model_validate(spec))
    r = _view(**spec)
    assert [h.texto for h in textos] == [h["texto"] for h in r["hallazgos"]]
    assert len(vistas) - 1 == len(r["complementarias"])


# -- degradacion --------------------------------------------------------------


def test_si_falla_el_apoyo_la_vista_sale_igual(monkeypatch):
    def explota(*_a, **_k):
        raise RuntimeError("bug en el compositor")

    monkeypatch.setattr("src.api.dashboard.apoyo_de_vista", explota)
    r = _view(chart="bar", group_by="organizacion")
    assert r["disponible"] and r["filas"]
    assert r["series"] == [] and r["hallazgos"] == [] and r["complementarias"] == []


def test_agregar_series_rechaza_una_dimension_repetida():
    with pytest.raises(ValueError, match="serie_por"):
        aggregates.agregar_series(group_by="organizacion", serie_por="organizacion")


def test_los_topes_se_declaran_en_vez_de_recortar_en_silencio(monkeypatch):
    muchas = [
        {"doc_id": f"F1-{i}", "fenomeno": "F1", "organizacion": f"org{i:02d}", "formato": "pdf",
         "anio": None, "n_fragmentos": 1}
        for i in range(aggregates.MAX_CATEGORIAS + 5)
    ]  # fmt: skip
    monkeypatch.setattr(aggregates, "tabla", lambda: muchas)
    r = _view(chart="bar", group_by="organizacion")
    assert len(r["categorias"]) == aggregates.MAX_CATEGORIAS
    assert r["categorias_omitidas"] == 5


# -- serie_por: una segunda dimension ------------------------------------------


def test_serie_por_cruza_dos_dimensiones():
    r = _view(chart="stacked_bar", group_by="organizacion", serie_por="formato", fenomenos=["F3"])
    assert r["serie_por"] == "formato"
    assert {s["clave"] for s in r["series"]} == {"pdf", "html"}
    por_cat = {c: sum(s["valores"][i] for s in r["series"]) for i, c in enumerate(r["categorias"])}
    assert por_cat == {f["clave"]: f["valor"] for f in r["filas"]}, "el cruce no cambia los totales"


def test_serie_por_ordena_las_series_por_total_y_las_de_fenomeno_por_clave():
    r = _view(chart="stacked_bar", group_by="fenomeno", serie_por="organizacion")
    totales = [sum(s["valores"]) for s in r["series"]]
    assert totales == sorted(totales, reverse=True)
    assert r["categorias"] == ["F3", "F1", "F2"]


def test_una_serie_por_repetida_se_quita_y_la_vista_sigue_valida():
    """Descartar la vista entera por un campo de mas deja al usuario sin grafico."""
    r = _view(chart="stacked_bar", group_by="organizacion", serie_por="organizacion")
    assert r["disponible"] and r["serie_por"] == "fenomeno", "vuelve al comportamiento por defecto"


@pytest.mark.parametrize("chart", ["donut", "kpi", "table"])
def test_los_graficos_que_no_separan_series_ignoran_serie_por(chart):
    from src.api.contracts import ViewSpec

    v = ViewSpec(chart=chart, group_by="organizacion", serie_por="formato")
    assert v.serie_por is None


def test_un_timeline_con_serie_por_anio_se_corrige_porque_el_eje_ya_es_el_anio():
    from src.api.contracts import ViewSpec

    assert ViewSpec(chart="timeline", serie_por="anio").serie_por is None
    assert ViewSpec(chart="timeline", serie_por="organizacion").serie_por == "organizacion"


def test_serie_por_fuera_del_vocabulario_sigue_siendo_un_error():
    """El esquema cerrado no se relaja: solo se corrige lo que se entiende."""
    r = _view(chart="bar", group_by="organizacion", serie_por="lugar")
    assert r["disponible"] is False


def test_serie_por_no_esta_en_el_esquema_que_ve_el_visualizador():
    """Medido con el modelo real: visible, la dona de F3 salia con F1 (4 de 4).

    Si alguien lo expone, que sea una decision tomada midiendo, no un descuido.
    """
    from src.api.contracts import ViewSpec

    assert "serie_por" not in ViewSpec.model_json_schema()["properties"]


# -- reglas por componente (/api/components) -----------------------------------


def test_components_publica_las_reglas_de_cada_grafico():
    from src.api.contracts import ChartType, GroupBy

    r = client.get("/api/components").json()
    assert set(r["reglas"]) == set(ChartType.__args__), "ningun componente sin reglas"
    for chart, regla in r["reglas"].items():
        assert set(regla["group_by"]) <= set(GroupBy.__args__), chart
        if regla["por_defecto"]:
            assert regla["por_defecto"] in regla["group_by"], chart
    assert r["limites"] == {
        "categorias": aggregates.MAX_CATEGORIAS,
        "series": aggregates.MAX_SERIES,
    }


def test_las_reglas_dicen_lo_que_el_endpoint_hace():
    """Lo que se anuncia es lo que se cumple: el tablero se fia de este catalogo."""
    reglas = client.get("/api/components").json()["reglas"]
    assert reglas["timeline"]["group_by"] == ["anio"] and reglas["timeline"]["nota_obligatoria"]
    assert "anio" not in reglas["donut"]["group_by"] and reglas["kpi"]["group_by"] == []
    # un timeline agrupa por ano aunque se pida otra cosa
    assert _view(chart="timeline", group_by="organizacion")["group_by"] == "anio"
    # y la segunda dimension solo existe donde la regla lo dice
    for chart, regla in reglas.items():
        spec = {"chart": chart, "group_by": "organizacion", "serie_por": "formato"}
        from src.api.contracts import ViewSpec

        assert (ViewSpec.model_validate(spec).serie_por is not None) == regla["serie_por"], chart


def test_un_timeline_con_serie_por_anio_se_corrige_aunque_el_group_by_sea_otro():
    from src.api.contracts import ViewSpec

    assert ViewSpec(chart="timeline", group_by="organizacion", serie_por="anio").serie_por is None


def test_el_catalogo_del_visualizador_no_cambia():
    """Las reglas son del endpoint: lo que lee el modelo se queda como estaba."""
    import json

    from src.tools.analytics import componentes_disponibles

    assert "reglas" not in json.loads(componentes_disponibles())
