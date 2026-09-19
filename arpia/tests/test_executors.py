"""Pruebas de los tres agentes ejecutores (`src/agents/executors.py`).

Ninguna toca el gateway ni el corpus real: indice y LLM son falsos, y la tabla
de agregacion se inyecta. Lo que se vigila aqui es el **coste por turno** —que
es donde se pierde el Bloque B— y las dos fronteras de seguridad: el analitico
no acepta dimensiones libres y el visualizador no emite nada fuera del esquema.
"""

from __future__ import annotations

import os

os.environ.setdefault("ARPIA_MODE", "live")

from types import SimpleNamespace  # noqa: E402

import pytest  # noqa: E402

from src.agents import executors  # noqa: E402
from src.agents.plan import Paso  # noqa: E402
from src.api.contracts import ViewSpec  # noqa: E402
from src.observability import turnlog  # noqa: E402
from src.retrieval import aggregates  # noqa: E402
from src.retrieval.index import Hit  # noqa: E402

TABLA = [
    {
        "doc_id": "F1-A-1",
        "fenomeno": "F1",
        "organizacion": "CSET",
        "formato": "pdf",
        "anio": 2024,
        "n_fragmentos": 10,
    },
    {
        "doc_id": "F1-A-2",
        "fenomeno": "F1",
        "organizacion": "CSET",
        "formato": "pdf",
        "anio": 2025,
        "n_fragmentos": 20,
    },
    {
        "doc_id": "F2-B-1",
        "fenomeno": "F2",
        "organizacion": "CSIS",
        "formato": "csv",
        "anio": None,
        "n_fragmentos": 5,
    },
    {
        "doc_id": "F3-C-1",
        "fenomeno": "F3",
        "organizacion": "ILIA",
        "formato": "pdf",
        "anio": 2023,
        "n_fragmentos": 7,
    },
]


@pytest.fixture(autouse=True)
def _tabla(monkeypatch):
    monkeypatch.setattr(aggregates, "tabla", lambda: TABLA)
    turnlog.start_turn()
    yield
    aggregates.reset()


@pytest.fixture
def indice(monkeypatch):
    class FakeIndex:
        def __init__(self, score=0.7):
            self.score = score

        def search(self, query, k=8):  # noqa: ARG002
            return [
                Hit(
                    chunk_id=f"c{i}",
                    doc_id=f"F1-DOC-{i}",
                    text=f"texto {i} de {query}",
                    score=self.score,
                    metadata={"fenomeno": 1, "organizacion": "CSET"},
                )
                for i in range(3)
            ]

    from src.tools import corpus

    def make(score=0.7):
        monkeypatch.setattr(corpus, "_index", FakeIndex(score))

    return make


@pytest.fixture
def llm(monkeypatch):
    """LLM falso que cuenta llamadas de redaccion y de view_spec."""

    class FakeLLM:
        def __init__(self):
            self.redacciones = 0
            self.vistas = 0
            self.spec = ViewSpec(chart="bar", group_by="organizacion")
            self.devolver_basura = False

        def invoke(self, mensajes):
            self.redacciones += 1
            return SimpleNamespace(
                content="respuesta redactada",
                usage_metadata={"input_tokens": 300, "output_tokens": 60},
            )

        def with_structured_output(self, schema, include_raw=False):  # noqa: ARG002
            def _invoke(mensajes):
                self.vistas += 1
                crudo = SimpleNamespace(
                    content="", usage_metadata={"input_tokens": 200, "output_tokens": 30}
                )
                return {"raw": crudo, "parsed": None if self.devolver_basura else self.spec}

            return SimpleNamespace(invoke=_invoke)

    fake = FakeLLM()
    monkeypatch.setattr(executors, "_llm", lambda agente: fake)
    return fake


# -- documental --------------------------------------------------------------


def test_el_documental_solo_recupera_y_no_gasta_tokens(indice, llm):
    """Recuperar es local. Si esto empieza a llamar al modelo, el coste del
    turno deja de ser acotado."""
    indice()
    r = executors.documental(Paso(agente="agente_documental", consulta="satelites"))
    assert len(r.evidencia) == 3
    assert r.suficiente
    assert llm.redacciones == 0


def test_la_recuperacion_llena_el_contexto_que_evalua_adl(indice, llm):
    """Faithfulness se calcula contra `retrieval_context`: si hubo RAG y ese
    campo va vacio, se pierde el 30% del bloque de calidad."""
    indice()
    executors.documental(Paso(agente="agente_documental", consulta="satelites"))
    assert len(turnlog.retrieval_context()) == 3
    assert all(c["doc_id"] and c["chunk_id"] for c in turnlog.citations())


def test_evidencia_debil_se_marca_insuficiente(indice, llm):
    indice(score=0.2)
    r = executors.documental(Paso(agente="agente_documental", consulta="nada"))
    assert not r.suficiente


def test_redactar_es_una_sola_llamada(llm):
    evidencia = [{"chunk_id": f"c{i}", "texto": f"t{i}", "citacion": f"doc-{i}"} for i in range(8)]
    texto = executors.redactar("pregunta", evidencia)
    assert texto == "respuesta redactada"
    assert llm.redacciones == 1


def test_redactar_sin_evidencia_no_gasta_nada(llm):
    assert executors.redactar("pregunta", []) == ""
    assert llm.redacciones == 0


def test_si_falla_la_redaccion_se_entrega_la_evidencia(monkeypatch):
    def explota(agente):
        raise RuntimeError("gateway caido")

    monkeypatch.setattr(executors, "_llm", explota)
    texto = executors.redactar("p", [{"chunk_id": "c1", "texto": "dato", "citacion": "doc-1"}])
    assert "doc-1" in texto and "dato" in texto


def test_la_evidencia_entra_envuelta_como_dato(llm, monkeypatch):
    """El corpus es de fuentes externas: un documento puede traer instrucciones
    escritas para un modelo."""
    capturado = {}
    original = llm.invoke

    def espia(mensajes):
        capturado["prompt"] = mensajes[-1]["content"]
        return original(mensajes)

    monkeypatch.setattr(llm, "invoke", espia)
    executors.redactar("p", [{"chunk_id": "c1", "texto": "dato", "citacion": "doc-1"}])
    assert "<documento_recuperado" in capturado["prompt"]


# -- analitico (0 tokens) ----------------------------------------------------


def test_el_analitico_no_gasta_tokens_y_cuenta_exacto(llm):
    r = executors.analitico(Paso(agente="agente_analitico", consulta="cuantos documentos por tema"))
    assert llm.redacciones == 0 and llm.vistas == 0
    assert "F1: 2 documentos" in r.texto
    assert r.suficiente


def test_el_analitico_elige_la_dimension_sin_preguntarle_al_modelo(llm):
    r = executors.analitico(
        Paso(agente="agente_analitico", consulta="que organizacion publica mas")
    )
    assert "CSET: 2" in r.texto


def test_el_analitico_declara_lo_que_deja_fuera(llm):
    """Un conteo por ano que ignora en silencio los documentos sin ano es una
    cifra enganosa."""
    r = executors.analitico(Paso(agente="agente_analitico", consulta="evolucion por ano"))
    assert "no declaran anio" in r.texto


def test_el_analitico_registra_su_tool_en_la_traza(llm):
    executors.analitico(Paso(agente="agente_analitico", consulta="cuantos por tema"))
    assert [t["name"] for t in turnlog.tool_calls()] == ["consultar_agregado"]


def test_las_cifras_traen_los_doc_ids_que_las_sustentan(llm):
    """`RETO.md`: todo dato mostrado debe rastrearse hasta su documento."""
    r = executors.analitico(Paso(agente="agente_analitico", consulta="cuantos por tema"))
    assert all(e["doc_id"] for e in r.evidencia)


# -- visualizador ------------------------------------------------------------


def test_el_visualizador_emite_una_vista_valida(llm):
    r = executors.visualizador(Paso(agente="agente_visualizador", consulta="comparame fuentes"))
    assert r.view_spec["chart"] == "bar"
    assert llm.vistas == 1
    assert llm.redacciones == 0


def test_una_vista_invalida_se_descarta_y_el_turno_sigue(llm):
    llm.devolver_basura = True
    r = executors.visualizador(Paso(agente="agente_visualizador", consulta="x"))
    assert r.view_spec is None and r.error


def test_toda_vista_temporal_declara_su_cobertura(llm):
    """Solo el 34% de los documentos tiene ano. No se confia en que el modelo lo
    recuerde: se impone."""
    llm.spec = ViewSpec(chart="timeline", group_by="anio")
    r = executors.visualizador(Paso(agente="agente_visualizador", consulta="evolucion"))
    assert "34%" in r.view_spec["nota"]


def test_la_vista_hereda_el_fenomeno_que_acoto_el_plan(llm):
    """Medido contra el gateway real: el visualizador solo recibe `consulta`, no
    ve `paso.fenomeno`. Sin imponerlo, el titulo decia "seguridad del entorno
    espacial" y el tablero pintaba los tres fenomenos."""
    llm.spec = ViewSpec(chart="timeline", group_by="anio", titulo="Evolucion anual")
    r = executors.visualizador(
        Paso(agente="agente_visualizador", consulta="evolucion anual", fenomeno="F2")
    )
    assert r.view_spec["fenomenos"] == ["F2"]


def test_el_fenomeno_que_eligio_el_modelo_manda_sobre_el_del_plan(llm):
    """Se impone solo cuando el modelo no decidio: si eligio, su eleccion es mas
    especifica que el filtro del plan y sobrescribirla seria perder informacion."""
    llm.spec = ViewSpec(chart="bar", fenomenos=["F1", "F3"])
    r = executors.visualizador(
        Paso(agente="agente_visualizador", consulta="compara", fenomeno="F2")
    )
    assert r.view_spec["fenomenos"] == ["F1", "F3"]


def test_el_visualizador_consulta_el_catalogo_antes_de_emitir(llm):
    """Proponer un componente que el tablero no puede poblar cuenta como fallo
    de ejecucion, no como vista imperfecta."""
    executors.visualizador(Paso(agente="agente_visualizador", consulta="x"))
    assert [t["name"] for t in turnlog.tool_calls()] == [
        "componentes_disponibles",
        "emitir_view_spec",
    ]


# -- agregaciones ------------------------------------------------------------


def test_agregar_filtra_por_fenomeno():
    r = aggregates.agregar(group_by="organizacion", fenomenos=["F1"])
    assert [f["clave"] for f in r["filas"]] == ["CSET"]
    assert r["total"] == 2


def test_agregar_cuenta_fragmentos_distinto_que_documentos():
    docs = aggregates.agregar(metrica="conteo_documentos", group_by="fenomeno")
    frags = aggregates.agregar(metrica="conteo_fragmentos", group_by="fenomeno")
    assert docs["total"] == 4
    assert frags["total"] == 42


def test_agregar_reporta_la_cobertura_de_la_dimension():
    r = aggregates.agregar(group_by="anio")
    assert r["cobertura"]["sin_dato_en_la_dimension"] == 1  # el documento sin anio


def test_agregar_respeta_el_rango_de_anos():
    r = aggregates.agregar(group_by="anio", desde=2024)
    assert sorted(f["clave"] for f in r["filas"]) == ["2024", "2025"]


def test_las_dimensiones_disponibles_salen_de_datos_reales():
    d = aggregates.dimensiones_disponibles()
    assert d["organizaciones"] == ["CSET", "CSIS", "ILIA"]
    assert d["anios"] == {"min": 2023, "max": 2025}
    assert d["cobertura_anio_pct"] == 34


# -- los tres huecos que descubrio la primera prueba contra el gateway -------


def test_la_recuperacion_deja_rastro_en_tools_called(indice, llm):
    """Con el gateway real, un turno documental reporto 8 fragmentos y
    `tools_called: []`. ADL evalua la trayectoria a partir de ese campo: una
    recuperacion sin rastro se lee como una respuesta salida de la nada."""
    indice()
    executors.documental(Paso(agente="agente_documental", consulta="satelites"))
    llamadas = turnlog.tool_calls()
    assert [t["name"] for t in llamadas] == ["buscar_corpus"]
    assert llamadas[0]["input_parameters"]["query"] == "satelites"


def test_la_tool_registrada_no_duplica_el_registro(indice, llm):
    """`buscar_corpus` ya lo anota el registry: dos entradas por una sola
    busqueda falsearian la trayectoria."""
    indice()
    from src.tools.corpus import buscar_corpus

    buscar_corpus(query="satelites")
    assert [t["name"] for t in turnlog.tool_calls()] == ["buscar_corpus"]


def test_los_ejecutores_se_anotan_aunque_no_gasten_tokens(llm):
    """El analitico cuesta cero por diseno. Derivar `agentes_invocados` del
    desglose de tokens lo dejaba invisible pese a haber trabajado, y es
    justamente el agente de puntos extra."""
    executors.ejecutar(Paso(agente="agente_analitico", consulta="cuantos por tema"))
    assert turnlog.agentes() == ["agente_analitico"]


def test_un_ejecutor_que_falla_tambien_aparece_en_la_trayectoria(monkeypatch):
    monkeypatch.setitem(
        executors.EJECUTORES,
        "agente_analitico",
        lambda paso: 1 / 0,  # noqa: ARG005
    )
    executors.ejecutar(Paso(agente="agente_analitico", consulta="x"))
    assert turnlog.agentes() == ["agente_analitico"]


def test_el_analitico_obedece_la_dimension_del_plan(llm):
    """Con el gateway real, el orquestador reformulo el paso y perdio la palabra
    'organizacion': el texto contesto por fenomeno mientras el grafico agrupaba
    por organizacion. El plan manda; la heuristica es solo el respaldo."""
    paso = Paso(agente="agente_analitico", consulta="volumen documental", group_by="organizacion")
    r = executors.analitico(paso)
    assert "CSET: 2" in r.texto


def test_sin_dimension_en_el_plan_se_recurre_a_la_heuristica(llm):
    paso = Paso(agente="agente_analitico", consulta="cuantos documentos por tema")
    assert "F1: 2 documentos" in executors.analitico(paso).texto


# -- la delegacion del orquestador queda en la trayectoria -------------------


def _card() -> dict:
    import json
    from pathlib import Path

    return json.loads(Path("agent_card.json").read_text("utf-8"))


def test_la_delegacion_aparece_en_tools_called(indice, llm):
    """ADL evalua el bloque de diseno cruzando la agent card contra la traza. El
    orquestador delega emitiendo un paso del plan, no llamando a una tool: sin
    anotarlo, su funcion principal nunca aparecia en `tools_called`."""
    indice()
    executors.ejecutar(Paso(agente="agente_documental", consulta="satelites", fenomeno="F2"))
    llamadas = turnlog.tool_calls()
    assert [t["name"] for t in llamadas] == ["delegar_documental", "buscar_corpus"]
    assert llamadas[0]["input_parameters"] == {"consulta": "satelites", "fenomeno": "F2"}


def test_cada_agente_usa_el_nombre_de_delegacion_que_declara_la_card():
    card = _card()
    declaradas = {t["name"] for t in card["orquestador"]["tools"]}
    usadas = {nombre for nombre, _ in executors.DELEGACIONES.values()}
    assert usadas == declaradas, "la card y el codigo deben nombrar igual la delegacion"


def test_los_argumentos_anotados_son_los_que_declara_la_card():
    card = _card()
    por_nombre = {t["name"]: set(t["input_parameters"]) for t in card["orquestador"]["tools"]}
    for nombre, campos in executors.DELEGACIONES.values():
        assert set(campos) == por_nombre[nombre], nombre


def test_la_delegacion_al_visualizador_usa_instruccion(llm):
    executors.ejecutar(Paso(agente="agente_visualizador", consulta="grafica esto"))
    primera = turnlog.tool_calls()[0]
    assert primera["name"] == "delegar_visualizacion"
    assert primera["input_parameters"] == {"instruccion": "grafica esto"}
