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
