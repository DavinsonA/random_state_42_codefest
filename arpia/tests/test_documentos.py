"""`GET /api/documentos`: los documentos detras de una cifra.

Cada fila de un agregado solo trae una muestra de 10 `doc_id`; sin esta lista,
"ver todos los documentos de esta barra" no tiene de donde salir.
"""

from __future__ import annotations

import os

os.environ.setdefault("ARPIA_MODE", "stub")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from src.api.main import app  # noqa: E402
from src.retrieval import aggregates  # noqa: E402

client = TestClient(app)


def _fila(doc_id, fen, org, formato="pdf", anio=None, n=10):
    return {
        "doc_id": doc_id,
        "fenomeno": fen,
        "organizacion": org,
        "formato": formato,
        "anio": anio,
        "fuente": f"{fen}/{org}/{doc_id}.{formato}",
        "n_fragmentos": n,
    }


TABLA = [
    *[_fila(f"F3-SIPRI-{i:03d}", "F3", "SIPRI", anio=2021 if i % 2 else None) for i in range(30)],
    *[_fila(f"F3-ALERTAS-{i:03d}", "F3", "Alertas", formato="csv") for i in range(5)],
    _fila("F1-CSET-001", "F1", "CSET", anio=2024),
    _fila("F2-ESA-001", "F2", "ESA", formato="json", anio=2025),
]


@pytest.fixture(autouse=True)
def _tabla(monkeypatch):
    monkeypatch.setattr(aggregates, "tabla", lambda: TABLA)
    yield
    aggregates.reset()


def _get(**params):
    r = client.get("/api/documentos", params=params)
    assert r.status_code == 200, "el tablero nunca recibe otro codigo"
    return r.json()


def test_cada_fila_trae_lo_que_hace_falta_para_llegar_a_la_fuente():
    fila = _get(fenomeno="F1")["filas"][0]
    assert fila == {
        "doc_id": "F1-CSET-001",
        "organizacion": "CSET",
        "anio": 2024,
        "formato": "pdf",
        "fenomeno": "F1",
        "fuente": "F1/CSET/F1-CSET-001.pdf",
        "n_fragmentos": 10,
        "primer_chunk_id": "F1-CSET-001__chunk_000000",
    }


def test_filtra_por_fenomeno_organizacion_y_formato():
    assert _get(fenomeno="F3", organizacion="Alertas")["total"] == 5
    assert _get(formato="csv")["total"] == 5
    assert _get(fenomeno="F1,F2")["total"] == 2


def test_pagina_de_forma_estable_y_sin_repetir_ni_perder_documentos():
    vistos, offset = [], 0
    while offset is not None:
        pag = _get(fenomeno="F3", organizacion="SIPRI", limite=8, offset=offset)
        vistos += [f["doc_id"] for f in pag["filas"]]
        offset = pag["siguiente"]
    assert vistos == sorted(vistos) and len(vistos) == len(set(vistos)) == 30


def test_la_ultima_pagina_no_tiene_siguiente():
    pag = _get(fenomeno="F3", organizacion="SIPRI", limite=25, offset=25)
    assert len(pag["filas"]) == 5 and pag["siguiente"] is None and pag["total"] == 30


def test_un_offset_pasado_del_final_devuelve_una_pagina_vacia_no_un_error():
    pag = _get(offset=10_000)
    assert pag["disponible"] and pag["filas"] == [] and pag["total"] == 37


def test_el_rango_de_anos_declara_lo_que_deja_fuera():
    pag = _get(desde=2020, hasta=2025)
    assert pag["total"] == 15 + 2  # los SIPRI con ano + F1 + F2
    assert pag["excluidos_por_fecha"] == 20 and "no declaran fecha" in pag["aviso"]


def test_sin_rango_no_hay_aviso():
    assert _get()["aviso"] == ""


def test_un_fenomeno_invalido_es_un_error_legible_y_no_un_422():
    r = _get(fenomeno="F9")
    assert r["disponible"] is False and "F9" in r["motivo"]


def test_una_organizacion_inexistente_es_una_lista_vacia_no_un_error():
    r = _get(organizacion="NoExiste")
    assert r["disponible"] and r["total"] == 0 and r["filas"] == []


def test_sin_corpus_lo_dice_en_vez_de_devolver_una_lista_vacia(monkeypatch):
    monkeypatch.setattr(aggregates, "tabla", lambda: [])
    r = _get()
    assert r["disponible"] is False and "corpus" in r["motivo"]


def test_el_tope_de_pagina_se_respeta():
    excedido = client.get("/api/documentos", params={"limite": 500})
    assert excedido.status_code == 200 and excedido.json()["disponible"] is False, "nunca un 422"
    assert len(aggregates.documentos(limite=10_000)["filas"]) <= aggregates.MAX_PAGINA
