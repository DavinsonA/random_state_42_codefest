"""Un plan de varios pasos no puede perder lo que anotan los ejecutores.

`graph.ejecutar` corre los pasos en un `ThreadPoolExecutor` cuando el plan es
paralelo. Un `ContextVar` NO se propaga a esos hilos: `turnlog`, `usage` y
`tracing` guardan el estado del turno en uno, asi que lo que un ejecutor anotaba
desde su hilo se perdia. Con dos pasos: `tools_called=[]`, `tokens_por_agente=[]`,
`num_interacciones=0` y `retrieval_context` vacio.

`retrieval_context` es lo que ADL usa para Faithfulness (30% del bloque de
calidad) y los tokens del visualizador son parte del bloque de eficiencia.

Las pruebas de `test_graph.py` no lo detectan porque cuentan llamadas con
contadores del LLM falso: no leen `turnlog` ni `usage`. Estas si.
"""

from __future__ import annotations

import contextvars
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from src.agents import executors, graph
from src.agents.executors import Resultado
from src.agents.plan import Paso, Plan
from src.observability import tracing, turnlog, usage


def _ejecutor(agente: str):
    """Ejecutor falso que anota en el registro del turno lo mismo que los reales."""

    def _fn(paso: Paso) -> Resultado:
        chunk = f"c-{paso.consulta}"
        turnlog.add_context([f"(doc-{paso.consulta}) texto de {paso.consulta}"])
        turnlog.add_citations(
            [{"doc_id": f"doc-{paso.consulta}", "chunk_id": chunk, "fuente": None, "fragmento": ""}]
        )
        turnlog.record_tool_call("buscar_corpus", {"query": paso.consulta}, "ok")
        usage.record_usage(
            {"input_tokens": 10, "output_tokens": 5}, agent=agente, model="modelo-falso"
        )
        return Resultado(
            agente=agente,
            evidencia=[
                {
                    "chunk_id": chunk,
                    "doc_id": f"doc-{paso.consulta}",
                    "texto": paso.consulta,
                    "score": 0.9,
                    "citacion": f"doc-{paso.consulta}",
                }
            ],
            suficiente=True,
        )

    return _fn


@pytest.fixture
def turno(monkeypatch):
    for agente in ("agente_documental", "agente_analitico"):
        monkeypatch.setitem(executors.EJECUTORES, agente, _ejecutor(agente))
    usage.start_request()
    turnlog.start_turn()
    tracing.start_trace()


def _plan(paralelo: bool) -> dict:
    return Plan(
        pasos=[
            Paso(agente="agente_documental", consulta="uno"),
            Paso(agente="agente_analitico", consulta="dos"),
            Paso(agente="agente_documental", consulta="tres"),
        ],
        paralelo=paralelo,
    ).model_dump()


@pytest.mark.parametrize("paralelo", [False, True])
def test_el_registro_del_turno_es_igual_en_secuencial_y_en_paralelo(turno, paralelo):
    graph.ejecutar({"plan": _plan(paralelo)})

    assert sorted(
        c["input_parameters"]["query"] for c in turnlog.tool_calls() if c["name"] == "buscar_corpus"
    ) == [
        "dos",
        "tres",
        "uno",
    ]
    assert len(turnlog.retrieval_context()) == 3, "Faithfulness se calcula contra esto"
    assert len(turnlog.citations()) == 3
    assert usage.request_usage()["calls"] == 3
    assert usage.request_usage()["total_tokens"] == 45
    assert {a["agente"] for a in usage.request_breakdown()} == {
        "agente_documental",
        "agente_analitico",
    }


def test_los_spans_de_los_hilos_quedan_en_la_traza_del_turno(turno):
    graph.ejecutar({"plan": _plan(paralelo=True)})
    nombres = [s["name"] for s in tracing.to_spans()]
    assert sum(n.startswith("ejecutar.") for n in nombres) == 3


def test_dos_turnos_simultaneos_no_mezclan_su_registro(monkeypatch):
    """La copia del contexto es POR TAREA: dos requests en paralelo, cada una con
    su plan paralelo, no se ven entre si."""
    monkeypatch.setitem(executors.EJECUTORES, "agente_documental", _ejecutor("agente_documental"))
    monkeypatch.setitem(executors.EJECUTORES, "agente_analitico", _ejecutor("agente_analitico"))
    barrera = threading.Barrier(2)

    def turno_completo(prefijo: str) -> list[str]:
        usage.start_request()
        turnlog.start_turn()
        plan = Plan(
            pasos=[
                Paso(agente="agente_documental", consulta=f"{prefijo}-a"),
                Paso(agente="agente_analitico", consulta=f"{prefijo}-b"),
            ],
            paralelo=True,
        ).model_dump()
        barrera.wait(timeout=5)  # ambos turnos estan dentro de ejecutar a la vez
        graph.ejecutar({"plan": plan})
        return sorted(
            c["input_parameters"]["query"]
            for c in turnlog.tool_calls()
            if c["name"] == "buscar_corpus"
        )

    with ThreadPoolExecutor(2) as pool:
        # cada turno corre en su propio hilo, con su propio contexto
        a, b = (pool.submit(contextvars.copy_context().run, turno_completo, p) for p in ("A", "B"))
    assert a.result() == ["A-a", "A-b"]
    assert b.result() == ["B-a", "B-b"]


def test_el_acumulador_de_tokens_es_seguro_entre_hilos():
    """Los hilos de un plan paralelo suman sobre el MISMO acumulador del turno.
    `+=` sobre un entero no es atomico: sin candado se pierden sumas."""
    usage.start_request()
    n_hilos, n_llamadas = 16, 300

    def trabajar():
        for _ in range(n_llamadas):
            usage.record_usage({"input_tokens": 3, "output_tokens": 1}, agent="a", model="m")

    # una copia del contexto POR hilo (un Context no puede entrarse dos veces a la
    # vez); todas comparten el mismo acumulador mutable del turno
    hilos = [
        threading.Thread(target=contextvars.copy_context().run, args=(trabajar,))
        for _ in range(n_hilos)
    ]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    esperado = n_hilos * n_llamadas
    assert usage.request_usage()["calls"] == esperado
    assert usage.request_usage()["total_tokens"] == esperado * 4
