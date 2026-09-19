"""Pruebas de `POST /chat` (lado API del Reto 1).

Se prueba lo que es del API: el formato de ADL (§2.4), la resolucion de sesion,
la degradacion cuando algo falla y el aislamiento entre requests simultaneas.
El grafo real NO se ejecuta: se usa un `FakeGraph` que cumple el contrato de
`src/api/CONTRATO_GRAFO.md`. Asi las pruebas no dependen de un modelo ni del
indice, y no gastan presupuesto.
"""

from __future__ import annotations

import os

os.environ.setdefault("ARPIA_MODE", "stub")

import threading  # noqa: E402
from concurrent.futures import ThreadPoolExecutor  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from src import config  # noqa: E402
from src.agents import memory  # noqa: E402
from src.api import chat as chat_service  # noqa: E402
from src.api.main import app  # noqa: E402
from src.observability import usage  # noqa: E402
from src.retrieval.index import Hit  # noqa: E402
from src.tools import corpus  # noqa: E402  (registra `buscar_corpus` en el registry)
from src.tools.registry import registry  # noqa: E402


class FakeGraph:
    """Cumple el contrato con el API: busca con una tool, anota sus llamadas al
    LLM y devuelve `{"answer": ...}`."""

    def __init__(
        self, answer: str = "respuesta falsa", fail: bool = False, agent: str = "agente_qa"
    ):
        self.answer = answer
        self.fail = fail
        self.agent = agent
        self.configs: list[dict] = []
        self.barrier: threading.Barrier | None = None

    def invoke(self, state: dict, config: dict | None = None) -> dict:
        self.configs.append(config)
        if self.fail:
            raise RuntimeError("proveedor caido")
        if self.barrier:
            self.barrier.wait(timeout=5)  # fuerza que dos requests se solapen
        registry.get("buscar_corpus")(query=state["question"])
        for _ in range(2):
            usage.record_usage(
                {"input_tokens": 10, "output_tokens": 5}, agent=self.agent, model="modelo-falso"
            )
        return {"answer": f"{self.answer}: {state['question']}" if self.answer else ""}


class FakeIndex:
    def search(self, query: str, k: int = 8):  # noqa: ARG002
        return [Hit(chunk_id="c1", doc_id=f"doc-{query}", text=f"texto sobre {query}", score=0.9)]


def _env(monkeypatch, **extra: str) -> None:
    for key, value in extra.items():
        monkeypatch.setenv(key, value)
    config.get_settings.cache_clear()
    chat_service.reset_graph()
    memory.cache.reset()


@pytest.fixture(autouse=True)
def _cache_limpio():
    """Sin esto, la segunda consulta identica de una prueba mide el cache
    semantico en vez de lo que la prueba cree estar midiendo."""
    memory.cache.reset()
    yield
    memory.cache.reset()


@pytest.fixture
def stub_client(monkeypatch):
    _env(monkeypatch, ARPIA_MODE="stub")
    yield TestClient(app)
    config.get_settings.cache_clear()


@pytest.fixture
def live(monkeypatch):
    """Modo live con grafo e indice falsos: `make(graph)` -> (cliente, grafo)."""

    def make(graph: FakeGraph | None = None):
        graph = graph or FakeGraph()
        _env(
            monkeypatch,
            ARPIA_MODE="live",
            LLM_BASE_URL="http://falso",
            LLM_API_KEY="falsa",
            LLM_MODEL="modelo-falso",
        )
        monkeypatch.setattr(chat_service, "_graph", graph)
        monkeypatch.setattr(corpus, "_index", FakeIndex())
        return TestClient(app), graph

    yield make
    config.get_settings.cache_clear()
    chat_service.reset_graph()


def _chat(client, texto: str, sesion_id: str | None = None):
    body = {"texto": texto, **({"sesion_id": sesion_id} if sesion_id else {})}
    return client.post("/chat", json=body)


# -- contrato HTTP (stub) ----------------------------------------------------


def test_chat_devuelve_el_formato_de_adl(stub_client):
    resp = _chat(stub_client, "que es la orbita baja")
    assert resp.status_code == 200
    body = resp.json()
    assert {"respuesta", "evaluacion", "metadata"} <= body.keys()
    assert body["mode"] == "stub"
    assert body["evaluacion"]["input"] == "que es la orbita baja"
    assert body["evaluacion"]["actual_output"] == body["respuesta"]
    assert body["evaluacion"]["retrieval_context"]
    assert body["evaluacion"]["tools_called"][0]["name"] == "buscar_corpus"
    assert body["metadata"]["estado"] == "stub"
    assert body["metadata"]["tokens"].keys() == {"input", "output", "total"}


def test_chat_acepta_texto_plano(stub_client):
    resp = stub_client.post(
        "/chat", content="hola en texto plano", headers={"content-type": "text/plain"}
    )
    assert resp.status_code == 200
    assert resp.json()["evaluacion"]["input"] == "hola en texto plano"


def test_chat_acepta_alias_de_la_pregunta(stub_client):
    resp = stub_client.post("/chat", json={"pregunta": "hola"})
    assert resp.json()["evaluacion"]["input"] == "hola"


def test_chat_sin_pregunta_no_es_un_error_http(stub_client):
    resp = stub_client.post("/chat", content="")
    assert resp.status_code == 200
    assert resp.json()["metadata"]["estado"] == "error_entrada_invalida"


# -- sesiones ----------------------------------------------------------------


def test_sin_sesion_el_servidor_genera_una_y_la_devuelve(stub_client):
    resp = _chat(stub_client, "hola")
    sid = resp.headers["x-session-id"]
    assert len(sid) == 32
    assert sid in resp.headers["set-cookie"]


def test_sesion_del_cliente_se_respeta_y_no_se_setea_cookie(stub_client):
    resp = _chat(stub_client, "hola", sesion_id="sesion-12345")
    assert resp.headers["x-session-id"] == "sesion-12345"
    assert "set-cookie" not in resp.headers


def test_sesion_con_forma_invalida_se_reemplaza(stub_client):
    resp = _chat(stub_client, "hola", sesion_id="../../etc")
    assert resp.headers["x-session-id"] != "../../etc"


def test_sesion_por_header(stub_client):
    resp = stub_client.post(
        "/chat", json={"texto": "hola"}, headers={"X-Session-Id": "desde-header-1"}
    )
    assert resp.headers["x-session-id"] == "desde-header-1"


# -- frontera con el grafo (live, con FakeGraph) -----------------------------


def test_el_sesion_id_llega_al_grafo_como_thread_id(live):
    client, graph = live()
    _chat(client, "hola", "sesion-aaaa1")
    assert graph.configs == [{"configurable": {"thread_id": "sesion-aaaa1"}}]


def test_evaluacion_refleja_solo_el_turno_actual(live):
    client, _ = live()
    _chat(client, "primera", "sesion-aaaa1")
    body = _chat(client, "segunda", "sesion-aaaa1").json()
    assert body["evaluacion"]["retrieval_context"] == ["(doc-segunda) texto sobre segunda"]
    tools = body["evaluacion"]["tools_called"]
    assert [t["name"] for t in tools] == ["buscar_corpus"]
    assert tools[0]["input_parameters"] == {"query": "segunda"}
    assert body["respuesta"] == "respuesta falsa: segunda"


def test_metadata_suma_todos_los_llamados_y_atribuye_por_agente(live):
    client, _ = live()
    meta = _chat(client, "hola", "sesion-aaaa1").json()["metadata"]
    assert meta["num_interacciones"] == 2
    assert meta["tokens"] == {"input": 20, "output": 10, "total": 30}
    assert meta["agentes_invocados"] == ["agente_qa"]
    assert meta["tokens_por_agente"] == [
        {"agente": "agente_qa", "modelo": "modelo-falso", "input": 20, "output": 10, "total": 30}
    ]


def test_grafo_que_no_atribuye_agente_no_rompe_la_respuesta(live):
    """El total sigue siendo correcto aunque el grafo no informe agente/modelo."""
    client, _ = live(FakeGraph(agent=""))
    resp = _chat(client, "hola", "sesion-aaaa1")
    assert resp.status_code == 200
    meta = resp.json()["metadata"]
    assert meta["tokens"]["total"] == 30
    assert meta["tokens_por_agente"] == []


def test_fallo_del_grafo_degrada_a_recuperacion_y_no_es_500(live):
    client, _ = live(FakeGraph(fail=True))
    resp = _chat(client, "algo", "sesion-aaaa1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["metadata"]["estado"] == "error_grafo"
    assert body["evaluacion"]["retrieval_context"] == ["(doc-algo) texto sobre algo"]


def test_respuesta_vacia_del_grafo_se_reporta(live):
    client, _ = live(FakeGraph(answer=""))
    body = _chat(client, "algo", "sesion-aaaa1").json()
    assert body["metadata"]["estado"] == "error_respuesta_vacia"
    assert body["respuesta"]


def test_sin_credenciales_en_live_degrada_y_no_es_500(monkeypatch):
    _env(monkeypatch, ARPIA_MODE="live", LLM_BASE_URL="", LLM_API_KEY="")
    monkeypatch.setattr(corpus, "_index", FakeIndex())
    resp = _chat(TestClient(app), "algo")
    assert resp.status_code == 200
    assert resp.json()["metadata"]["estado"] == "error_llm_no_configurado"
    config.get_settings.cache_clear()


def test_requests_simultaneas_no_mezclan_su_evaluacion(live):
    """ADL puede mandar preguntas en paralelo: cada respuesta debe traer solo lo suyo."""
    _, graph = live()
    graph.barrier = threading.Barrier(2)  # ambas requests estan dentro del grafo a la vez

    def ask(q: str) -> dict:
        return _chat(TestClient(app), q, f"sesion-{q}-000").json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.map(ask, ["alfa", "beta"])

    assert a["evaluacion"]["retrieval_context"] == ["(doc-alfa) texto sobre alfa"]
    assert b["evaluacion"]["retrieval_context"] == ["(doc-beta) texto sobre beta"]
    assert a["metadata"]["tokens"]["total"] == b["metadata"]["tokens"]["total"] == 30


# -- agentes_invocados incluye a los que no gastan tokens -------------------


def test_agentes_invocados_incluye_a_los_que_no_gastan_tokens(live):
    """Se arma desde el desglose de tokens MAS el registro del turno. Un agente
    que trabaja y no aparece es credito perdido ante ADL."""
    from src.observability import turnlog

    class GrafoConAnalitico(FakeGraph):
        def invoke(self, state, config=None):
            turnlog.record_agent("agente_analitico")  # cuesta cero tokens
            return super().invoke(state, config)

    client, _ = live(GrafoConAnalitico())
    meta = _chat(client, "cuantos documentos hay").json()["metadata"]
    assert "agente_qa" in meta["agentes_invocados"]  # gasto tokens
    assert "agente_analitico" in meta["agentes_invocados"]  # no gasto ninguno
    assert [a["agente"] for a in meta["tokens_por_agente"]] == ["agente_qa"]
