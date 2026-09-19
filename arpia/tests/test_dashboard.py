"""Pruebas de los endpoints del tablero (`src/api/dashboard.py`).

Dos propiedades: que los datos salgan con su trazabilidad, y que **ningun
camino devuelva un codigo distinto de 200**. Un 500 durante la demo del Reto 2
se ve igual que un despliegue caido, y un 404 se confunde con un endpoint que no
existe.
"""

from __future__ import annotations

import os

os.environ.setdefault("ARPIA_MODE", "stub")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from src.api.main import app  # noqa: E402
from src.retrieval import aggregates  # noqa: E402

client = TestClient(app)

TABLA = [
    {
        "doc_id": "F1-A",
        "fenomeno": "F1",
        "organizacion": "CSET",
        "formato": "pdf",
        "anio": 2024,
        "n_fragmentos": 10,
    },
    {
        "doc_id": "F1-B",
        "fenomeno": "F1",
        "organizacion": "CSET",
        "formato": "pdf",
        "anio": 2025,
        "n_fragmentos": 20,
    },
    {
        "doc_id": "F2-C",
        "fenomeno": "F2",
        "organizacion": "CSIS",
        "formato": "csv",
        "anio": None,
        "n_fragmentos": 5,
    },
]


@pytest.fixture(autouse=True)
def _tabla(monkeypatch):
    monkeypatch.setattr(aggregates, "tabla", lambda: TABLA)
    yield
    aggregates.reset()


@pytest.fixture
def indice(monkeypatch):
    class FakeIndex:
        def chunk(self, chunk_id):
            if chunk_id != "F1-A__chunk_000001":
                return None
            return {
                "chunk_id": chunk_id,
                "doc_id": "F1-A",
                "texto": "el texto exacto que sustenta la cita",
                "fuente": "F1_IA/CSET/doc.pdf",
                "organizacion": "CSET",
                "anio": 2024,
                "formato": "pdf",
                "fenomeno_id": "F1",
                "fenomeno_nombre": "IA y Capacidades Estrategicas",
            }

    from src.tools import corpus

    monkeypatch.setattr(corpus, "_index", FakeIndex())


# -- catalogo y agregacion ---------------------------------------------------


def test_components_lista_lo_que_el_tablero_puede_pintar():
    body = client.get("/api/components").json()
    assert "bar" in body["componentes"]
    assert "map" not in body["componentes"]  # no hay geografia en el corpus
    assert body["dimensiones"]["organizaciones"] == ["CSET", "CSIS"]


def test_aggregate_devuelve_cifras_con_sus_documentos():
    """`RETO.md`: todo dato mostrado debe rastrearse hasta su `doc_id`."""
    body = client.get("/api/aggregate", params={"group_by": "organizacion"}).json()
    assert body["disponible"] is True
    fila = next(f for f in body["filas"] if f["clave"] == "CSET")
    assert fila["valor"] == 2
    assert fila["doc_ids"] == ["F1-A", "F1-B"]


def test_aggregate_filtra_por_fenomeno():
    body = client.get(
        "/api/aggregate", params={"fenomenos": "F2", "group_by": "organizacion"}
    ).json()
    assert [f["clave"] for f in body["filas"]] == ["CSIS"]


def test_aggregate_con_parametros_basura_no_es_un_500():
    r = client.get("/api/aggregate", params={"group_by": "DROP TABLE", "metrica": "riesgo"})
    assert r.status_code == 200


# -- linea de tiempo ---------------------------------------------------------


def test_timeline_declara_lo_que_deja_fuera():
    """Una serie temporal que oculta su cobertura convierte un conteo honesto en
    una cifra enganosa."""
    body = client.get("/api/timeline").json()
    assert [f["clave"] for f in body["filas"]] == ["2024", "2025"]
    assert body["cobertura"]["sin_dato_en_la_dimension"] == 1
    assert "1 de 3 documentos no declaran ano" in body["aviso"]


def test_un_rango_de_anos_no_borra_el_aviso_de_cobertura():
    """Filtrar por fecha descarta en silencio los documentos sin ano. Si la
    cobertura se midiera despues del filtro, el aviso diria siempre "0 sin
    dato": tranquilizador y falso."""
    body = client.get("/api/timeline", params={"desde": 2025}).json()
    assert body["cobertura"]["sin_dato_en_la_dimension"] == 1
    assert body["cobertura"]["documentos_contados"] == 1


def test_timeline_es_anual_porque_es_lo_que_el_corpus_sostiene():
    assert client.get("/api/timeline").json()["granularidad"] == "anio"


# -- geo ---------------------------------------------------------------------


def test_geo_responde_200_diciendo_que_no_hay_dato():
    """El corpus no tiene ubicacion. Un 404 se confundiria con un fallo de
    despliegue; inventar una ubicacion esta prohibido."""
    r = client.get("/api/geo")
    assert r.status_code == 200
    body = r.json()
    assert body["disponible"] is False
    assert "ubicacion" in body["motivo"]
    assert "organizacion" in body["alternativa"]


# -- evidencia ---------------------------------------------------------------


def test_evidence_devuelve_el_fragmento_exacto(indice):
    body = client.get("/api/evidence/F1-A__chunk_000001").json()
    assert body["disponible"] is True
    assert body["texto"] == "el texto exacto que sustenta la cita"
    assert body["doc_id"] == "F1-A"
    assert body["organizacion"] == "CSET"


def test_evidence_de_un_chunk_inexistente_no_es_un_404(indice):
    r = client.get("/api/evidence/no-existe")
    assert r.status_code == 200
    assert r.json()["disponible"] is False


def test_evidence_sin_indice_degrada_en_vez_de_reventar():
    r = client.get("/api/evidence/F1-A__chunk_000001")
    assert r.status_code == 200
    assert r.json()["disponible"] is False


# -- traza -------------------------------------------------------------------


def test_la_respuesta_trae_un_trace_id_consultable():
    """Es lo que permite explicar una respuesta rara despues de que ocurrio."""
    respuesta = client.post("/chat", json={"texto": "una consulta cualquiera"}).json()
    trace_id = respuesta["trace_id"]
    assert trace_id

    body = client.get(f"/api/trace/{trace_id}").json()
    assert body["disponible"] is True
    assert body["spans"], "la traza del turno no puede venir vacia"
    assert all("parent_id" in s and "type" in s for s in body["spans"])


def test_una_traza_que_ya_no_esta_no_es_un_404():
    r = client.get("/api/trace/" + "0" * 32)
    assert r.status_code == 200
    assert r.json()["disponible"] is False
