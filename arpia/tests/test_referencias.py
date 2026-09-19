"""Referencias de una respuesta: tooltip (citas enriquecidas) y visor del documento.

El indice es un `VectorIndex` REAL sobre un JSONL pequeno, sin FAISS ni encoder:
lo que se prueba es la lectura por posicion, que es donde estaria el error. Un
doble del indice pasaria aunque el acceso directo apuntara a la fila equivocada.
"""

from __future__ import annotations

import json
import os

os.environ.setdefault("ARPIA_MODE", "stub")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from src.api.contracts import Citation  # noqa: E402
from src.api.main import app  # noqa: E402
from src.observability import turnlog  # noqa: E402
from src.retrieval.index import Hit, VectorIndex  # noqa: E402
from src.tools import corpus  # noqa: E402

client = TestClient(app)

DOCS = (("F1-A", 5, "pdf"), ("F2-B", 3, "csv"))


@pytest.fixture
def indice(tmp_path, monkeypatch):
    filas = [
        {
            "doc_id": doc,
            "chunk_id": f"{doc}__chunk_{i:06d}",
            "fuente": f"F1_IA/CSET/2024/{doc}.{fmt}",
            "formato": fmt,
            "fenomeno": 1,
            "posicion": i,
            "num_tokens": 5,
            "texto": f"texto de {doc} numero {i}",
        }
        for doc, n, fmt in DOCS
        for i in range(n)
    ]
    ruta = tmp_path / "metadata.jsonl"
    ruta.write_text("\n".join(json.dumps(f) for f in filas) + "\n", encoding="utf-8")

    idx = VectorIndex(tmp_path)
    idx._scan_offsets()
    idx._fh = ruta.open("rb")
    idx._index = object()  # `_load` sale antes de tocar FAISS
    monkeypatch.setattr(corpus, "_index", idx)
    yield idx
    idx._fh.close()


# -- indice: lectura por posicion -------------------------------------------


def test_chunks_of_devuelve_la_ventana_en_orden(indice):
    filas = indice.chunks_of("F1-A", 1, 3)
    assert [f["posicion"] for f in filas] == [1, 2, 3]
    assert filas[0]["texto"] == "texto de F1-A numero 1"


def test_chunks_of_recorta_al_documento_y_no_se_sale_a_otro(indice):
    filas = indice.chunks_of("F1-A", -3, 99)
    assert [f["posicion"] for f in filas] == [0, 1, 2, 3, 4]
    assert {f["doc_id"] for f in filas} == {"F1-A"}, "no debe colarse F2-B"


def test_chunks_of_un_documento_inexistente_es_none(indice):
    assert indice.chunks_of("no-existe", 0, 2) is None
    assert indice.n_chunks("no-existe") is None


def test_las_filas_llevan_el_total_de_fragmentos_de_su_documento(indice):
    assert indice.chunk("F2-B__chunk_000001")["total_fragmentos"] == 3
    assert indice.documents_meta(["F1-A"])["F1-A"]["total_fragmentos"] == 5


def test_chunk_salta_directo_a_su_fila_sin_recorrer_el_documento(indice, monkeypatch):
    lecturas: list[int] = []
    original = indice._row_at

    def contando(offset):
        lecturas.append(offset)
        return original(offset)

    monkeypatch.setattr(indice, "_row_at", contando)
    fila = indice.chunk("F1-A__chunk_000004")
    assert fila["texto"] == "texto de F1-A numero 4"
    assert len(lecturas) == 1, "un CSV llega a 76.220 fragmentos: no se recorre"


def test_chunk_con_id_raro_sigue_funcionando_por_recorrido(indice):
    assert indice.chunk("F1-A__chunk_000009") is None  # fuera de rango
    assert indice.chunk("F1-A__chunk_abc") is None
    assert indice.chunk("no-existe__chunk_000000") is None


@pytest.mark.parametrize("sufijo", ["²", "٣", "-1", " 1", "1.0", "9" * 5000, ""])
def test_chunk_no_revienta_con_sufijos_hostiles(indice, sufijo):
    """El `chunk_id` llega de internet. `"²".isdigit()` es True e `int("²")` lanza."""
    assert indice.chunk(f"F1-A__chunk_{sufijo}") is None


@pytest.mark.parametrize("truncado", ["F1-A__chunk_", "F1-A__chunk_00000", "F1-A__chunk_0000"])
def test_un_chunk_id_truncado_no_devuelve_otro_fragmento(indice, truncado):
    """Antes se comparaba por subcadena: `...chunk_00000` abria el fragmento 0."""
    assert indice.chunk(truncado) is None


def test_chunk_con_ceros_a_la_izquierda_de_mas_no_engana_al_acceso_directo(indice):
    """`chunk_0000001` (7 digitos) no es el id de la fila 1: nadie debe recibirla."""
    assert indice.chunk("F1-A__chunk_0000001") is None


# -- endpoint /api/document --------------------------------------------------


def test_document_centra_la_ventana_en_el_fragmento_citado(indice):
    body = client.get(
        "/api/document/F1-A", params={"chunk_id": "F1-A__chunk_000002", "ventana": 1}
    ).json()
    assert body["disponible"] is True
    assert [f["posicion"] for f in body["fragmentos"]] == [1, 2, 3]
    assert [f["citado"] for f in body["fragmentos"]] == [False, True, False]
    assert (body["desde"], body["hasta"], body["total_fragmentos"]) == (1, 3, 5)
    assert body["hay_anterior"] is True and body["hay_siguiente"] is True
    assert body["formato"] == "pdf"


def test_document_en_los_bordes_avisa_que_no_hay_mas(indice):
    inicio = client.get("/api/document/F1-A", params={"ventana": 1}).json()
    assert inicio["hay_anterior"] is False and inicio["hay_siguiente"] is True
    final = client.get("/api/document/F1-A", params={"posicion": 99, "ventana": 1}).json()
    assert final["hay_siguiente"] is False and final["hasta"] == 4


def test_document_pagina_pidiendo_otra_posicion(indice):
    body = client.get("/api/document/F1-A", params={"posicion": 3, "ventana": 0}).json()
    assert [f["posicion"] for f in body["fragmentos"]] == [3]
    assert not any(f["citado"] for f in body["fragmentos"])


def test_document_acota_la_ventana(indice):
    from src.api.dashboard import MAX_VENTANA

    body = client.get("/api/document/F1-A", params={"ventana": 10_000}).json()
    assert len(body["fragmentos"]) <= 2 * MAX_VENTANA + 1


def test_document_rechaza_un_fragmento_de_otro_documento(indice):
    r = client.get("/api/document/F1-A", params={"chunk_id": "F2-B__chunk_000000"})
    assert r.status_code == 200
    assert r.json()["disponible"] is False


def test_document_desconocido_o_con_forma_de_ruta_no_toca_el_disco(indice):
    """`doc_id` es una clave del indice, nunca una ruta."""
    r = client.get("/api/document/no-existe")
    assert r.status_code == 200 and r.json()["disponible"] is False

    # Con barras el enrutador ni siquiera llega al endpoint (404): no hay ruta.
    for doc in ("..%2F..%2Fetc%2Fpasswd", "F1-A%2F..%2FF2-B"):
        r = client.get(f"/api/document/{doc}")
        assert r.status_code in (200, 404)
        assert r.json().get("disponible") is not True


def test_document_recorta_los_fragmentos_enormes_y_lo_avisa(indice, monkeypatch):
    from src.api import dashboard

    monkeypatch.setattr(dashboard, "MAX_CHARS_FRAGMENTO", 10)
    body = client.get("/api/document/F1-A", params={"ventana": 0}).json()
    assert body["fragmentos"][0]["truncado"] is True
    assert len(body["fragmentos"][0]["texto"]) == 10


def test_document_sin_indice_degrada_en_vez_de_reventar(monkeypatch):
    monkeypatch.setattr(corpus, "_index", None)
    monkeypatch.setenv("VECTOR_INDEX_PATH", "/no/existe")
    r = client.get("/api/document/F1-A")
    assert r.status_code == 200
    assert r.json()["disponible"] is False


def test_evidence_incluye_posicion_y_total(indice):
    body = client.get("/api/evidence/F1-A__chunk_000003").json()
    assert (body["posicion"], body["total_fragmentos"]) == (3, 5)


# -- citas enriquecidas ------------------------------------------------------


def test_las_citas_llevan_lo_que_el_tooltip_necesita(monkeypatch):
    class Falso:
        def search(self, query, k=8):  # noqa: ARG002
            return [
                Hit(
                    chunk_id="F1-A__chunk_000002",
                    doc_id="F1-A",
                    text="x" * 500,
                    score=0.9,
                    metadata={
                        "organizacion": "CSET",
                        "formato": "pdf",
                        "posicion": 2,
                        "total_fragmentos": 87,
                        "anio": 2024,
                    },
                )
            ]

    monkeypatch.setattr(corpus, "_index", Falso())
    turnlog.start_turn()
    corpus.recuperar("algo")
    cita = turnlog.citations()[0]
    assert cita["fuente"] == "CSET"
    assert (cita["formato"], cita["posicion"], cita["total_fragmentos"], cita["anio"]) == (
        "pdf",
        2,
        87,
        2024,
    )
    assert len(cita["fragmento"]) == corpus.FRAGMENTO_CHARS
    assert Citation(**cita).total_fragmentos == 87  # valida contra el contrato


def test_una_cita_sin_esos_datos_sigue_siendo_valida():
    cita = Citation(doc_id="d", chunk_id="d__chunk_000000")
    assert cita.formato is None and cita.posicion is None
