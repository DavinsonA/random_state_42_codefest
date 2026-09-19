"""Pruebas del grafo de plan unico (`src/agents/`).

Ninguna llama al gateway: se usa un LLM falso que cuenta sus invocaciones. Lo
que mas se prueba aqui es el **coste del turno**, porque es lo que separa este
diseno del bucle ReAct que reemplaza: un turno normal cuesta DOS llamadas y el
peor caso TRES, y eso tiene que seguir siendo cierto cuando alguien toque el
grafo a las 4 de la manana.

El otro bloque cubre los tres fallos de estado que documento
`CONTRATO_GRAFO.md`, todos invisibles hasta que la memoria se activa.
"""

from __future__ import annotations

import os

os.environ.setdefault("ARPIA_MODE", "live")

from types import SimpleNamespace  # noqa: E402

import pytest  # noqa: E402
from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402

from src.agents import executors, graph, orchestrator  # noqa: E402
from src.agents.plan import Paso, Plan  # noqa: E402
from src.retrieval.index import Hit  # noqa: E402
from src.tools import corpus  # noqa: E402


class FakeLLM:
    """Cuenta llamadas y distingue planificacion de redaccion.

    Sin plan fijo, planifica una busqueda documental con la pregunta recibida.
    Eso importa: un plan estatico haria pasar pruebas que no comprueban nada
    sobre si el grafo ve la pregunta de ESTE turno.
    """

    def __init__(self, plan: Plan | None = None, texto: str = "respuesta redactada"):
        self.plan_fijo = plan
        self.texto = texto
        self.llamadas: list[str] = []
        self.fallar_plan = False
        self.fallar_redaccion = False

    # -- planificacion ---------------------------------------------------
    def with_structured_output(self, schema, include_raw: bool = False):  # noqa: ARG002
        return SimpleNamespace(invoke=self._plan)

    def _plan(self, mensajes):
        self.llamadas.append("plan")
        if self.fallar_plan:
            raise RuntimeError("gateway caido")
        plan = self.plan_fijo or Plan(
            pasos=[Paso(agente="agente_documental", consulta=self._pregunta(mensajes))]
        )
        crudo = SimpleNamespace(
            content="", usage_metadata={"input_tokens": 100, "output_tokens": 20}
        )
        return {"raw": crudo, "parsed": plan}

    @staticmethod
    def _pregunta(mensajes) -> str:
        """Primera linea del mensaje de usuario: la pregunta, sin el bloque de
        replanificacion que el orquestador anade debajo."""
        for m in reversed(mensajes):
            if m.get("role") == "user":
                return m["content"].splitlines()[0]
        return ""

    # -- redaccion -------------------------------------------------------
    def invoke(self, mensajes):
        self.llamadas.append("redaccion")
        if self.fallar_redaccion:
            raise RuntimeError("gateway caido")
        return SimpleNamespace(
            content=self.texto, usage_metadata={"input_tokens": 400, "output_tokens": 80}
        )

    @property
    def planes(self) -> int:
        return self.llamadas.count("plan")

    @property
    def redacciones(self) -> int:
        return self.llamadas.count("redaccion")


class FakeIndex:
    """Indice falso. `score` decide si la evidencia se considera suficiente."""

    def __init__(self, score: float = 0.7, n: int = 3):
        self.score = score
        self.n = n
        self.consultas: list[str] = []

    def search(self, query: str, k: int = 8):  # noqa: ARG002
        self.consultas.append(query)
        return [
            Hit(
                chunk_id=f"c{i}",
                doc_id=f"F1-DOC-{i}",
                text=f"texto {i} sobre {query}",
                score=self.score,
                metadata={"fenomeno": 1, "organizacion": "CSIS_Aerospace"},
            )
            for i in range(self.n)
        ]


@pytest.fixture
def entorno(monkeypatch):
    """LLM e indice falsos, y grafo con memoria en proceso.

    `make(...)` -> (grafo_compilado, llm, indice)
    """
    from src import config

    monkeypatch.setenv("LLM_BASE_URL", "http://falso")
    monkeypatch.setenv("LLM_API_KEY", "falsa")
    monkeypatch.setenv("ARPIA_MODE", "live")
    config.get_settings.cache_clear()

    def make(plan: Plan | None = None, score: float = 0.7):
        llm = FakeLLM(plan=plan)
        indice = FakeIndex(score=score)
        monkeypatch.setattr(orchestrator, "_llm", lambda: llm)
        monkeypatch.setattr(graph, "_llm", lambda agente: llm)
        monkeypatch.setattr(corpus, "_index", indice)
        return graph.build_graph(checkpointer=InMemorySaver()), llm, indice

    yield make
    config.get_settings.cache_clear()


def _config(hilo: str = "hilo-1") -> dict:
    return {"configurable": {"thread_id": hilo}}


# -- coste del turno ---------------------------------------------------------


def test_un_turno_normal_cuesta_exactamente_dos_llamadas(entorno):
    """Planificar y redactar. Ni una mas: el Bloque B se normaliza contra los
    otros equipos y un bucle ReAct gasta entre tres y siete."""
    g, llm, _ = entorno()
    out = g.invoke({"question": "que dice el corpus sobre satelites"}, _config())
    assert llm.planes == 1
    assert llm.redacciones == 1
    assert out["answer"] == "respuesta redactada"


def test_la_recuperacion_no_cuesta_llamadas(entorno):
    """FAISS y el encoder son locales: recuperar es gratis en tokens."""
    plan = Plan(
        pasos=[
            Paso(agente="agente_documental", consulta="satelites"),
            Paso(agente="agente_documental", consulta="orbitas"),
        ],
        paralelo=True,
    )
    g, llm, indice = entorno(plan=plan)
    g.invoke({"question": "dos temas"}, _config())
    assert len(indice.consultas) == 2  # dos busquedas
    assert llm.planes + llm.redacciones == 2  # y solo dos llamadas al modelo


def test_sin_evidencia_replanifica_una_sola_vez(entorno):
    """El peor caso son TRES llamadas: plan, replan, redaccion."""
    g, llm, indice = entorno(score=0.1)  # por debajo del umbral
    g.invoke({"question": "algo que no esta"}, _config())
    assert llm.planes == 2, "debe replanificar exactamente una vez"
    assert llm.redacciones == 1
    assert len(indice.consultas) == 2


def test_con_evidencia_no_replanifica(entorno):
    g, llm, _ = entorno(score=0.9)
    g.invoke({"question": "algo que si esta"}, _config())
    assert llm.planes == 1


# -- resiliencia -------------------------------------------------------------


def test_un_fallo_del_gateway_al_planificar_degrada_a_plan_de_respaldo(entorno):
    g, llm, indice = entorno()
    llm.fallar_plan = True
    out = g.invoke({"question": "capacidades antisatelite"}, _config())
    assert indice.consultas == ["capacidades antisatelite"]  # busco igual
    assert out["answer"] == "respuesta redactada"


def test_un_fallo_al_redactar_entrega_la_evidencia_cruda(entorno):
    """Una disculpa generica puntua cero en relevancia; unos fragmentos con su
    procedencia son evidencia real."""
    g, llm, _ = entorno()
    llm.fallar_redaccion = True
    out = g.invoke({"question": "satelites"}, _config())
    assert "Fragmentos mas relevantes" in out["answer"]
    assert "F1-DOC-0" in out["answer"]


def test_un_agente_no_implementado_no_tumba_el_turno(entorno):
    plan = Plan(pasos=[Paso(agente="agente_visualizador", consulta="grafica")])
    g, _, _ = entorno(plan=plan)
    out = g.invoke({"question": "muestrame una grafica"}, _config())
    assert out["answer"]  # responde igual, sin evidencia


def test_sin_evidencia_lo_dice_en_vez_de_inventar(entorno):
    plan = Plan(pasos=[Paso(agente="agente_visualizador", consulta="x")])
    g, llm, _ = entorno(plan=plan)
    out = g.invoke({"question": "algo"}, _config())
    assert "No encontre evidencia" in out["answer"]
    assert llm.redacciones == 0  # no se paga una redaccion sin nada que redactar


# -- los tres fallos de estado que documento CONTRATO_GRAFO.md ---------------


def test_el_turno_2_si_ve_la_pregunta_nueva(entorno):
    """Fallo 1: `reason` solo agregaba la pregunta con el historial vacio."""
    g, _, indice = entorno()
    g.invoke({"question": "primera pregunta"}, _config())
    g.invoke({"question": "segunda pregunta"}, _config())
    assert indice.consultas[-1] == "segunda pregunta"


def test_la_evidencia_no_se_arrastra_entre_turnos(entorno):
    """Fallo 2: `evidence` con `operator.add` citaba en el turno 5 lo del 1."""
    g, _, _ = entorno()
    g.invoke({"question": "primera"}, _config())
    out = g.invoke({"question": "segunda"}, _config())
    assert len(out["evidence"]) == 3  # los de este turno, no seis
    assert all("segunda" in e["texto"] for e in out["evidence"])


def test_el_contador_de_replanes_se_reinicia_cada_turno(entorno):
    """Fallo 2 bis: el tope se agotaba a los pocos mensajes de conversacion."""
    g, llm, _ = entorno(score=0.1)
    g.invoke({"question": "primera"}, _config())
    assert llm.planes == 2
    g.invoke({"question": "segunda"}, _config())
    assert llm.planes == 4, "el segundo turno vuelve a tener su replanificacion"


def test_el_historial_no_arrastra_mensajes_de_herramientas(entorno):
    """Fallo 3: subian los tokens de cada turno y contaminaban Faithfulness."""
    g, _, _ = entorno()
    for i in range(4):
        out = g.invoke({"question": f"pregunta {i}"}, _config())
    tipos = [getattr(m, "type", "") for m in out["messages"]]
    assert "tool" not in tipos
    assert len(out["messages"]) <= 13  # sistema + ventana de 6 turnos


# -- memoria conversacional --------------------------------------------------


def test_el_historial_persiste_dentro_del_mismo_hilo(entorno):
    g, _, _ = entorno()
    g.invoke({"question": "primera"}, _config("hilo-A"))
    out = g.invoke({"question": "segunda"}, _config("hilo-A"))
    humanos = [m.content for m in out["messages"] if getattr(m, "type", "") == "human"]
    assert humanos == ["primera", "segunda"]


def test_dos_sesiones_no_comparten_historial(entorno):
    """Sin esto, una pregunta de ADL arrastraria el contexto de otra —incluido
    un intento de inyeccion de la anterior."""
    g, _, _ = entorno()
    g.invoke({"question": "de la sesion A"}, _config("hilo-A"))
    out = g.invoke({"question": "de la sesion B"}, _config("hilo-B"))
    humanos = [m.content for m in out["messages"] if getattr(m, "type", "") == "human"]
    assert humanos == ["de la sesion B"]


# -- plan --------------------------------------------------------------------


def test_el_plan_de_respaldo_es_determinista_y_gratis():
    from src.agents.plan import plan_de_respaldo

    p = plan_de_respaldo("una pregunta")
    assert p.pasos[0].agente == "agente_documental"
    assert p.pasos[0].consulta == "una pregunta"


def test_el_plan_rechaza_agentes_que_no_estan_en_la_agent_card():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Plan.model_validate({"pasos": [{"agente": "agente_inventado", "consulta": "x"}]})


def test_el_plan_tiene_tope_de_pasos():
    """Sin tope, un modelo entusiasta convierte una pregunta en ocho delegaciones."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Plan.model_validate(
            {"pasos": [{"agente": "agente_documental", "consulta": f"q{i}"} for i in range(4)]}
        )


def test_el_filtro_por_fenomeno_no_deja_la_evidencia_en_nada(entorno):
    """Un filtro estricto es peor que uno impreciso si la alternativa es decir
    'no encontre nada' teniendo material."""
    plan = Plan(pasos=[Paso(agente="agente_documental", consulta="x", fenomeno="F3")])
    g, _, _ = entorno(plan=plan)  # el indice falso solo devuelve fenomeno 1
    out = g.invoke({"question": "algo"}, _config())
    assert len(out["evidence"]) == 3


def test_ejecutor_desconocido_devuelve_error_en_vez_de_lanzar():
    r = executors.ejecutar(Paso(agente="agente_analitico", consulta="x"))
    assert r.error and not r.evidencia
