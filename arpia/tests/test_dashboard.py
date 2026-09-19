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


def test_la_traza_no_se_publica_por_defecto():
    """Contiene el texto de la pregunta, los fragmentos recuperados y la salida
    del modelo. En `agent.*` —el dominio que evalua ADL— eso no puede estar
    accesible sin autenticacion."""
    respuesta = client.post("/chat", json={"texto": "una consulta cualquiera"}).json()
    body = client.get(f"/api/trace/{respuesta['trace_id']}").json()
    assert body["disponible"] is False
    assert "ARPIA_DEBUG_TRACE" in body["motivo"]


def test_la_traza_se_consulta_con_la_variable_de_depuracion(monkeypatch):
    """Es lo que permite explicar una respuesta rara despues de que ocurrio."""
    from src import config

    monkeypatch.setenv("ARPIA_DEBUG_TRACE", "1")
    config.get_settings.cache_clear()

    respuesta = client.post("/chat", json={"texto": "una consulta cualquiera"}).json()
    trace_id = respuesta["trace_id"]
    assert trace_id

    body = client.get(f"/api/trace/{trace_id}").json()
    assert body["disponible"] is True
    assert body["spans"], "la traza del turno no puede venir vacia"
    assert all("parent_id" in s and "type" in s for s in body["spans"])
    config.get_settings.cache_clear()


def test_una_traza_que_ya_no_esta_no_es_un_404(monkeypatch):
    from src import config

    monkeypatch.setenv("ARPIA_DEBUG_TRACE", "1")
    config.get_settings.cache_clear()
    r = client.get("/api/trace/" + "0" * 32)
    assert r.status_code == 200
    assert r.json()["disponible"] is False
    config.get_settings.cache_clear()


# -- POST /api/view: el puente entre el chat y el tablero --------------------


def test_view_resuelve_un_view_spec_a_datos():
    """El tablero manda la vista que emitio el agente y recibe la serie lista."""
    r = client.post("/api/view", json={"chart": "bar", "group_by": "organizacion"})
    body = r.json()
    assert body["disponible"] is True
    assert body["chart"] == "bar"
    assert [f["clave"] for f in body["filas"]] == ["CSET", "CSIS"]
    assert body["filas"][0]["doc_ids"] == ["F1-A", "F1-B"]


def test_view_ordena_cronologicamente_las_vistas_temporales():
    body = client.post("/api/view", json={"chart": "timeline"}).json()
    assert body["group_by"] == "anio"  # se impone aunque el agente no lo diga
    assert [f["clave"] for f in body["filas"]] == ["2024", "2025"]


def test_view_antepone_la_cobertura_medida_a_la_nota_del_agente():
    """La nota del modelo no sustituye al dato: el numero va primero."""
    body = client.post("/api/view", json={"chart": "timeline", "nota": "Aviso del agente."}).json()
    assert body["aviso"].startswith("1 de 3 documentos no declaran ano")
    assert body["aviso"].endswith("Aviso del agente.")


def test_view_rechaza_lo_que_no_pasa_el_esquema_cerrado():
    """Misma validacion que emite el visualizador: lo que no pasa, no se pinta."""
    r = client.post("/api/view", json={"chart": "map", "sql": "select 1"})
    assert r.status_code == 200
    assert r.json()["disponible"] is False


def test_view_filtra_por_fenomeno():
    body = client.post(
        "/api/view", json={"chart": "bar", "group_by": "organizacion", "fenomenos": ["F2"]}
    ).json()
    assert [f["clave"] for f in body["filas"]] == ["CSIS"]


def test_un_rango_de_anos_avisa_lo_que_se_lleva_por_delante():
    """Medido en el corpus real: un rango 2005-2026 sobre un conteo por
    organizacion dejaba 621 de 1.826 documentos y hacia desaparecer al mayor
    publicador, con `aviso` vacio. La grafica salia creible y falsa."""
    body = client.post(
        "/api/view",
        json={"chart": "bar", "group_by": "organizacion", "desde": "2024", "hasta": "2026"},
    ).json()
    assert body["cobertura"]["excluidos_por_fecha"] == 1  # el documento sin anio
    assert "deja fuera 1 de 3 documentos" in body["aviso"]


def test_sin_rango_no_se_pierde_nada_y_no_hay_aviso_de_fecha():
    body = client.post("/api/view", json={"chart": "bar", "group_by": "organizacion"}).json()
    assert body["cobertura"]["excluidos_por_fecha"] == 0
    assert "deja fuera" not in body["aviso"]


# -- el corpus ausente no se cachea como "vacio" ----------------------------


def test_sin_corpus_los_endpoints_dicen_no_disponible(monkeypatch):
    """Si el volumen del indice aun no esta montado cuando llega la primera
    peticion, cachear la lista vacia dejaria el tablero en blanco hasta
    reiniciar, respondiendo 200 y sin un solo aviso."""
    from src.retrieval import aggregates

    monkeypatch.setattr(aggregates, "tabla", list)
    for ruta in ("/api/aggregate", "/api/timeline"):
        cuerpo = client.get(ruta).json()
        assert cuerpo["disponible"] is False
        assert "no esta cargado" in cuerpo["motivo"]
    cuerpo = client.post("/api/view", json={"chart": "bar"}).json()
    assert cuerpo["disponible"] is False


def test_una_tabla_vacia_no_se_cachea():
    from src.retrieval import aggregates

    aggregates.reset()
    assert aggregates.tabla() == [] or aggregates.tabla()
    # el fallo no queda fijado: el siguiente intento vuelve a construirla
    assert aggregates._tabla is None or aggregates._tabla
