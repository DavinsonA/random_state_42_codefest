"""Un turno completo por `run_chat` con el grafo REAL y un plan paralelo.

Es la prueba que faltaba: las de `test_graph.py` ejecutan el grafo y cuentan
llamadas del LLM falso, pero no leen el JSON que recibe ADL. Aqui se lee.

Plan de dos pasos en paralelo (documental + visualizador) —el caso de "dame la
respuesta y ademas grafica"— con tres llamadas al modelo: planificar, emitir la
vista y redactar. Lo que ADL debe ver:

- `retrieval_context` y `citations`: los anota el documental desde su hilo.
- `tools_called` con `emitir_view_spec`: lo anota el visualizador desde su hilo.
- `tokens_por_agente` con los TRES agentes y el nombre de modelo de la CARD (el que
  ADL cruza contra la ficha), no el id que se envia a LiteLLM.
"""

from __future__ import annotations

import os

os.environ.setdefault("ARPIA_MODE", "live")

import pytest  # noqa: E402
from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402

from src import config  # noqa: E402
from src.agents import card, executors, graph, memory, orchestrator  # noqa: E402
from src.agents.plan import Paso, Plan  # noqa: E402
from src.api import chat as chat_service  # noqa: E402
from src.retrieval import aggregates  # noqa: E402
from src.tools import corpus  # noqa: E402
from tests.test_graph import TABLA_FALSA, FakeIndex, FakeLLM  # noqa: E402


@pytest.fixture
def turno_paralelo(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://falso")
    monkeypatch.setenv("LLM_API_KEY", "falsa")
    monkeypatch.setenv("ARPIA_MODE", "live")
    config.get_settings.cache_clear()
    card.reset_cache()
    memory.cache.reset()

    plan = Plan(
        pasos=[
            Paso(agente="agente_documental", consulta="capacidades antisatelite"),
            Paso(agente="agente_visualizador", consulta="comparame las fuentes"),
        ],
        paralelo=True,
    )
    llm = FakeLLM(plan=plan)
    monkeypatch.setattr(orchestrator, "_llm", lambda: llm)
    monkeypatch.setattr(executors, "_llm", lambda agente: llm)
    monkeypatch.setattr(corpus, "_index", FakeIndex())
    monkeypatch.setattr(aggregates, "tabla", lambda: TABLA_FALSA)
    aggregates.reset()
    monkeypatch.setattr(chat_service, "_graph", graph.build_graph(checkpointer=InMemorySaver()))

    yield llm
    config.get_settings.cache_clear()
    memory.cache.reset()
    chat_service.reset_graph()


def test_un_plan_paralelo_entrega_a_adl_toda_su_metadata(turno_paralelo):
    resp = chat_service.run_chat("capacidades antisatelite y comparame las fuentes", "sesion-e2e-1")

    assert resp.metadata.estado == "ok"
    assert resp.mode == "live"

    # -- bloque evaluacion: lo anotan los hilos del plan paralelo ----------
    assert len(resp.evaluacion.retrieval_context) == 3, "Faithfulness se calcula contra esto"
    assert len(resp.citations) == 3
    assert "emitir_view_spec" in [t.name for t in resp.evaluacion.tools_called]
    assert resp.view_spec is not None and resp.view_spec.chart == "bar"

    # -- bloque metadata: plan (100+20) + vista (150+25) + redaccion (400+80) ----
    m = resp.metadata
    assert m.num_interacciones == 3
    assert (m.tokens.input, m.tokens.output, m.tokens.total) == (650, 125, 775)
    porcion = {a.agente: a for a in m.tokens_por_agente}
    assert set(porcion) == {"orquestador", "agente_visualizador", "agente_documental"}
    assert sum(a.total for a in m.tokens_por_agente) == m.tokens.total

    # ADL cruza el modelo REPORTADO contra la card; LiteLLM recibe otro id.
    assert porcion["agente_documental"].modelo == "llama-3.3-70b-instruct"
    assert porcion["orquestador"].modelo == "gpt-oss-120b"
    assert porcion["agente_visualizador"].modelo == "gpt-oss-120b"
    assert set(m.agentes_invocados) >= {"orquestador", "agente_visualizador", "agente_documental"}
