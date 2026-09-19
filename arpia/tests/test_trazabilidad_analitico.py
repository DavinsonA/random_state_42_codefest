"""Una cifra que se muestra debe poder rastrearse hasta los documentos que la sustentan.

`RETO.md`: "todo dato mostrado debe rastrearse a su `doc_id` y `chunk_id`". La
especificacion de ADL lo exige para todo dato de un componente (§3.3, punto 3) y
para toda variable derivada como `organizacion` o `anio` (B.1.3), y mide
Faithfulness contra `retrieval_context` (Bloque A, 30%).

Hasta ahora una respuesta cuantitativa salia con el texto sin un solo `doc_id`,
`citations` vacio y `retrieval_context` vacio, aunque el sistema SI tenia los
documentos detras de cada cifra: quedaban dentro de la evidencia interna y nunca
llegaban al usuario ni a ADL. Ademas el texto mostraba hasta 25 filas y la
evidencia respaldaba solo 10.

El verificador ya no exige citas a una respuesta cuantitativa (`8d96e8d`): la
trazabilidad se garantiza POR CONSTRUCCION, en el propio agente, y esta suite lo
fija. La contrapartida es que los `doc_id` de la muestra de un conteo son
documentos reales y NO pueden leerse como "citas fabricadas".
"""

from __future__ import annotations

import os

os.environ.setdefault("ARPIA_MODE", "live")

import re  # noqa: E402

import pytest  # noqa: E402
from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402

from src import config  # noqa: E402
from src.agents import card, executors, graph, memory, orchestrator  # noqa: E402
from src.agents.plan import Paso, Plan  # noqa: E402
from src.agents.verifier import diagnosticar, verificar  # noqa: E402
from src.api import chat as chat_service  # noqa: E402
from src.observability import turnlog, usage  # noqa: E402
from src.retrieval import aggregates  # noqa: E402
from src.tools import corpus  # noqa: E402
from tests.test_graph import FakeLLM  # noqa: E402

_ID = re.compile(r"\bF[123]-[A-Z0-9]+-\d+\b")


def _doc(doc_id: str, fen: str, org: str, anio: int | None, frag: int = 10) -> dict:
    return {
        "doc_id": doc_id,
        "fenomeno": fen,
        "organizacion": org,
        "formato": "pdf",
        "anio": anio,
        "n_fragmentos": frag,
    }


#: CSET tiene 4 documentos (mas que la muestra de 3), CSIS 2, ALERTAS 1 sin ano.
TABLA = [
    _doc("F1-CSET-001", "F1", "CSET", 2024),
    _doc("F1-CSET-002", "F1", "CSET", 2025),
    _doc("F1-CSET-003", "F1", "CSET", 2023),
    _doc("F1-CSET-004", "F1", "CSET", 2022),
    _doc("F2-CSIS-014", "F2", "CSIS", 2018),
    _doc("F2-CSIS-015", "F2", "CSIS", 2019),
    _doc("F3-ALERTAS-001", "F3", "ALERTAS", None),
]
ORG = {d["doc_id"]: d["organizacion"] for d in TABLA}


class IndiceFalso:
    """Indice ya cargado: devuelve el primer fragmento de cada documento."""

    def stats(self):
        return {"vectores": 1}

    def documents_meta(self, doc_ids):
        return {
            d: {
                "doc_id": d,
                "chunk_id": f"{d}__chunk_000000",
                "texto": f"texto inicial del documento {d}",
                "organizacion": ORG[d],
                "fuente": f"{ORG[d]}/{d}.pdf",
            }
            for d in doc_ids
            if d in ORG
        }


@pytest.fixture(autouse=True)
def _turno(monkeypatch):
    monkeypatch.setattr(aggregates, "tabla", lambda: TABLA)
    monkeypatch.setattr(corpus, "_index", IndiceFalso())
    usage.start_request()
    turnlog.start_turn()
    yield
    aggregates.reset()


def _contar(dimension: str = "organizacion"):
    return executors.analitico(
        Paso(agente="agente_analitico", consulta="cuantos documentos", group_by=dimension)
    )


def _lineas(texto: str) -> list[str]:
    return [linea for linea in texto.splitlines() if linea.startswith("- ")]


# -- el texto --------------------------------------------------------------


def test_cada_cifra_del_texto_cita_hasta_tres_documentos_que_la_sustentan():
    r = _contar()
    lineas = _lineas(r.texto)
    assert len(lineas) == 3
    for linea in lineas:
        ids = _ID.findall(linea)
        assert 1 <= len(ids) <= 3, linea
    cset = next(linea for linea in lineas if linea.startswith("- CSET"))
    assert len(_ID.findall(cset)) == 3, "CSET tiene 4 documentos: se cita una muestra de 3"
    assert "CSET: 4 documentos" in cset, "la cifra sigue siendo el conteo total, no la muestra"


def test_lo_citado_en_el_texto_existe_realmente_en_el_corpus():
    r = _contar()
    assert set(_ID.findall(r.texto)) <= set(ORG)


# -- la evidencia ----------------------------------------------------------


def test_la_evidencia_respalda_todas_las_filas_que_muestra_el_texto():
    """Antes el texto mostraba hasta 25 filas y la evidencia solo 10: las demas
    cifras quedaban sin respaldo."""
    r = _contar()
    lineas = _lineas(r.texto)
    assert len(r.evidencia) == len(lineas)
    for linea, e in zip(lineas, r.evidencia, strict=True):
        assert set(_ID.findall(linea)) == {p.strip() for p in e["doc_id"].split(",")}


def test_una_dimension_con_muchas_filas_no_pierde_evidencia(monkeypatch):
    tabla = [_doc(f"F1-ORG{i:02d}-001", "F1", f"ORG{i:02d}", 2024) for i in range(20)]
    monkeypatch.setattr(aggregates, "tabla", lambda: tabla)
    r = _contar()
    assert len(_lineas(r.texto)) == len(r.evidencia) == 20


# -- lo que recibe ADL -------------------------------------------------------


def test_deja_citas_estructuradas_con_chunk_fuente_y_fragmento_reales():
    _contar()
    citas = turnlog.citations()
    assert len(citas) == 3, "una cita por cifra"
    for c in citas:
        assert c["chunk_id"] == f"{c['doc_id']}__chunk_000000"
        assert c["fuente"] == ORG[c["doc_id"]]
        assert c["fragmento"].startswith("texto inicial del documento")


def test_llena_retrieval_context_con_una_linea_por_cifra():
    """Faithfulness se calcula contra este campo: sin el, cada cifra del texto
    se juzga como una afirmacion sin sustento."""
    _contar()
    contexto = turnlog.retrieval_context()
    assert len(contexto) == 3
    assert any("CSET: 4 documentos" in linea for linea in contexto)
    assert all(_ID.search(linea) for linea in contexto)


def test_la_cobertura_que_declara_el_texto_tambien_tiene_respaldo_en_el_contexto():
    _contar("anio")  # ALERTAS-001 no declara ano: el texto lo dice
    contexto = " ".join(turnlog.retrieval_context())
    assert "no declaran año" in contexto


# -- el verificador ----------------------------------------------------------


class ModeloQueNoDebeLlamarse:
    def invoke(self, *_a, **_k):  # pragma: no cover - solo falla si se llama
        raise AssertionError("el verificador llamo al modelo sobre un conteo sano")


def test_las_citas_de_la_muestra_no_se_leen_como_fabricadas():
    """Contrapartida de que el verificador ignore la evidencia agregada: si los
    `doc_id` de la muestra no contaran como disponibles, TODA respuesta
    cuantitativa (que ahora cita) se reescribiria por modelo."""
    r = _contar()
    d = diagnosticar(r.texto, r.evidencia)
    assert d.citadas, "el texto cita documentos"
    assert not d.fabricadas
    assert not d.requiere_verificacion
    assert verificar(r.texto, r.evidencia, modelo=ModeloQueNoDebeLlamarse()) == r.texto


def test_una_cita_inventada_en_un_conteo_sigue_detectandose():
    r = _contar()
    manipulado = r.texto + "\nSegun F1-INVENTADO-999 hay 50 documentos mas."
    d = diagnosticar(manipulado, r.evidencia)
    assert d.fabricadas == {"F1-INVENTADO-999"}
    assert d.requiere_verificacion


# -- degradacion: nunca tumba el conteo --------------------------------------


def test_sin_indice_cargado_no_se_fuerza_su_carga_y_el_conteo_sigue(monkeypatch):
    class Descargado:
        def stats(self):
            return {}

        def documents_meta(self, _ids):  # pragma: no cover
            raise AssertionError("no debe cargar 1,3 GB por una cita")

    monkeypatch.setattr(corpus, "_index", Descargado())
    r = _contar()
    assert _ID.findall(r.texto), "los doc_id salen de la tabla, no del indice"
    assert turnlog.citations() == []


def test_una_falla_del_indice_no_tumba_el_conteo(monkeypatch):
    class Roto:
        def stats(self):
            return {"vectores": 1}

        def documents_meta(self, _ids):
            raise RuntimeError("indice corrupto")

    monkeypatch.setattr(corpus, "_index", Roto())
    r = _contar()
    assert "CSET: 4 documentos" in r.texto and r.suficiente
    assert turnlog.citations() == []


# -- de punta a punta: lo que lee ADL ----------------------------------------


def test_una_pregunta_cuantitativa_entrega_a_adl_citas_y_contexto_sin_llamar_al_verificador(
    monkeypatch,
):
    monkeypatch.setenv("LLM_BASE_URL", "http://falso")
    monkeypatch.setenv("LLM_API_KEY", "falsa")
    monkeypatch.setenv("ARPIA_MODE", "live")
    config.get_settings.cache_clear()
    card.reset_cache()
    memory.cache.reset()

    plan = Plan(
        pasos=[Paso(agente="agente_analitico", consulta="documentos", group_by="organizacion")]
    )
    llm = FakeLLM(plan=plan)
    monkeypatch.setattr(orchestrator, "_llm", lambda: llm)
    monkeypatch.setattr(executors, "_llm", lambda agente: llm)
    monkeypatch.setattr(chat_service, "_graph", graph.build_graph(checkpointer=InMemorySaver()))

    resp = chat_service.run_chat("cuantos documentos hay por organizacion", "sesion-traz-001")

    assert resp.metadata.estado == "ok"
    assert len(resp.citations) == 3
    assert {c.doc_id for c in resp.citations} <= set(ORG)
    assert all(c.chunk_id.endswith("__chunk_000000") and c.fragmento for c in resp.citations)
    assert len(resp.evaluacion.retrieval_context) == 3
    assert _ID.search(resp.respuesta)
    assert llm.redacciones == 0, "el verificador no debe gastar una llamada en un conteo trazable"
    assert [a.agente for a in resp.metadata.tokens_por_agente] == ["orquestador"]

    config.get_settings.cache_clear()
    memory.cache.reset()
    chat_service.reset_graph()
