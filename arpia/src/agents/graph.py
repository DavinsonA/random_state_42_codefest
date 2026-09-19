"""Grafo agentico de A.R.P.I.A.: plan unico, delegacion y una replanificacion.

    START -> begin -> planificar -> ejecutar -> (replanificar una vez)
          -> componer -> verificar -> END

**Por que esto y no ReAct.** El bucle razonar-herramienta-observar hace un numero
impredecible de llamadas al modelo por pregunta. El Bloque B de `RETO.md`
normaliza la eficiencia contra los otros equipos y mide tokens, interacciones y
latencia: un coste que no se puede acotar es un riesgo que no se puede
presupuestar.

Coste del turno, acotado por construccion:

    pregunta documental              2 llamadas  (plan + redaccion)
    pregunta cuantitativa            1 llamada   (plan; el analitico no gasta)
    pregunta con vista               3 llamadas  (plan + redaccion + view_spec)
    sin evidencia en la 1a pasada   +1 llamada   (una replanificacion, y solo una)

La recuperacion y la agregacion son locales y no cuestan tokens. La
consolidacion final tampoco: cada ejecutor ya redacto lo suyo.

La recuperacion no cuesta tokens: FAISS y el encoder corren en la CPU del
contenedor. Esa asimetria es la ventaja competitiva del sistema.
"""

from __future__ import annotations

import contextvars
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
from langgraph.graph import END, START, StateGraph

from src.agents import budget, executors, orchestrator, verifier, voz
from src.agents.memory import VENTANA_TURNOS, conversacion_previa
from src.agents.plan import MAX_REPLANES, Paso, Plan
from src.agents.state import TURNO_LIMPIO, AgentState
from src.config import get_logger

log = get_logger(__name__)

# -- nodos ------------------------------------------------------------------


def begin(state: AgentState) -> dict[str, Any]:
    """Abre el turno: agrega la pregunta y limpia lo que no debe sobrevivir.

    Tres cosas, y las tres arreglan un fallo real (ver `state.py`):

    1. La pregunta se agrega SIEMPRE, no solo cuando el historial esta vacio.
       Sin esto, con memoria activada el turno 2 nunca veria la pregunta nueva.
    2. Los campos del turno se reinician: sin esto, la evidencia del turno 1 se
       cita en el turno 5 como si fuera de esta pregunta.
    3. Se borran del historial los mensajes de herramientas de turnos
       anteriores y se recorta la ventana. Arrastrarlos sube los tokens de cada
       turno y contamina el `retrieval_context` que ADL mide en Faithfulness.
    """
    mensajes = state.get("messages") or []
    borrar = [
        RemoveMessage(id=m.id)
        for m in mensajes
        if getattr(m, "id", None)
        and (getattr(m, "type", "") == "tool" or getattr(m, "tool_calls", None))
    ]

    conservar = [m for m in mensajes if m not in borrar]
    limite = VENTANA_TURNOS * 2
    if len(conservar) > limite:
        borrar += [
            RemoveMessage(id=m.id)
            for m in conservar[:-limite]
            if getattr(m, "id", None) and getattr(m, "type", "") != "system"
        ]

    nuevos: list[Any] = list(borrar)
    nuevos.append(HumanMessage(content=state["question"]))

    return {"messages": nuevos, **TURNO_LIMPIO}


def planificar(state: AgentState) -> dict[str, Any]:
    """Unica llamada del orquestador. En la replanificacion, la segunda."""
    replans = state.get("replans", 0)
    motivo, intentadas = "", []
    if state.get("evidence") is not None and state.get("plan") and not state.get("suficiente"):
        replans += 1
        motivo = "ningun fragmento supero el umbral de similitud"
        intentadas = [p.get("consulta", "") for p in state.get("plan", {}).get("pasos", [])]

    plan = orchestrator.planificar(
        state["question"],
        motivo=motivo,
        intentadas=intentadas,
        conversacion=conversacion_previa(state.get("messages") or [], state["question"]),
    )
    return {"plan": plan.model_dump(), "replans": replans}


def ejecutar(state: AgentState) -> dict[str, Any]:
    """Corre los pasos del plan. En paralelo si el plan lo pidio.

    El paralelismo es real y barato: el documental recupera sobre FAISS y el
    visualizador decide una vista; ninguno necesita la salida del otro.
    """
    plan = Plan.model_validate(state["plan"])
    pasos = plan.pasos

    # En una replanificacion solo se repite lo que fallo. El visualizador no
    # depende de la evidencia: volver a emitir su vista seria pagar una segunda
    # llamada por el mismo JSON.
    if state.get("view_spec"):
        pasos = [p for p in pasos if p.agente != executors.AGENTE_VISUALIZADOR]
    if not pasos:
        return {}

    if plan.paralelo and len(pasos) > 1:
        # Un ThreadPoolExecutor NO hereda los `ContextVar` del hilo que lo lanza, y
        # `turnlog`, `usage` y `tracing` guardan en uno el estado del turno. Sin
        # esta copia, lo que un ejecutor anota desde su hilo se pierde: ADL veria
        # `tools_called=[]`, `retrieval_context` vacio (Faithfulness, 30% del bloque
        # de calidad) y `tokens_por_agente=[]`. Una copia POR tarea, porque un
        # `Context` no puede entrarse desde dos hilos a la vez; todas apuntan a los
        # mismos acumuladores mutables del turno.
        with ThreadPoolExecutor(max_workers=len(pasos)) as pool:
            futuros = [
                pool.submit(contextvars.copy_context().run, executors.ejecutar, p) for p in pasos
            ]
            resultados = [f.result() for f in futuros]
    else:
        resultados = [executors.ejecutar(p) for p in pasos]

    evidencia: list[dict[str, Any]] = []
    vistos: set[str] = set()
    findings: dict[str, str] = {}
    view_spec = None
    for r in resultados:
        if r.error:
            findings[r.agente] = f"[error] {r.error}"
        elif r.texto:
            findings[r.agente] = r.texto
        if r.view_spec:
            view_spec = r.view_spec
        for e in r.evidencia:
            # El corpus tiene fragmentos repetidos entre documentos: citarlos dos
            # veces no agrega evidencia, solo gasta contexto.
            if e["chunk_id"] not in vistos:
                vistos.add(e["chunk_id"])
                evidencia.append(e)

    evidencia.sort(key=lambda e: -e.get("score", 0.0))

    # La suficiencia la deciden SOLO los agentes que buscan evidencia. Una vista
    # emitida no dice nada sobre si encontramos material: contarla como exito
    # cancelaba la replanificacion de una busqueda que habia vuelto vacia.
    # Y si ningun agente de evidencia corrio, no hay nada que replanificar:
    # insistir costaria una llamada sin ninguna posibilidad de mejorar.
    buscadores = [
        r
        for r in resultados
        if r.agente in (executors.AGENTE_DOCUMENTAL, executors.AGENTE_ANALITICO)
    ]
    suficiente = not buscadores or any(r.suficiente for r in buscadores)

    return {
        "evidence": evidencia,
        "findings": findings,
        "view_spec": view_spec,
        "suficiente": suficiente,
    }


def componer(state: AgentState) -> dict[str, Any]:
    """Redacta y consolida. UNA llamada al modelo, y solo si hubo evidencia.

    El analitico ya trae sus cifras redactadas sin gastar nada; el visualizador
    ya emitio su vista. Lo unico que falta es convertir la evidencia documental
    en prosa, y eso se hace aqui, una vez, con el texto final.

    El orden es deliberado: primero la respuesta documental, que es la que
    contesta la pregunta; despues las cifras, que la respaldan; al final el
    aviso de la vista, que es una accion sobre el tablero y no parte de la
    respuesta.
    """
    findings = dict(state.get("findings") or {})
    evidencia = state.get("evidence") or []

    # La UNICA redaccion del turno, sobre la evidencia ya consolidada. Aqui y no
    # en el ejecutor: un plan de tres busquedas cuesta una redaccion, no tres, y
    # tras una replanificacion la evidencia definitiva solo se conoce ahora.
    documental = [e for e in evidencia if not str(e.get("chunk_id", "")).startswith("agregado:")]
    if documental:
        if budget.alcanza():
            findings[executors.AGENTE_DOCUMENTAL] = executors.redactar(
                state["question"],
                documental,
                conversacion_previa(state.get("messages") or [], state["question"]),
            )
        else:
            log.warning("presupuesto de tiempo agotado; se entrega la evidencia sin redactar")
            findings[executors.AGENTE_DOCUMENTAL] = ""

    partes: list[str] = []
    for agente in (executors.AGENTE_DOCUMENTAL, executors.AGENTE_ANALITICO):
        texto = findings.get(agente, "")
        if texto and not texto.startswith("[error]"):
            partes.append(texto)

    if not partes and evidencia:
        partes.append(
            f"{voz.SIN_REDACCION}\n\n"
            + "\n\n".join(
                f"[{i}] ({e['citacion']}) {e['texto'][:500]}"
                for i, e in enumerate(evidencia[:5], 1)
            )
        )

    if state.get("view_spec"):
        titulo = (state["view_spec"] or {}).get("titulo") or "La vista solicitada"
        partes.append(f"{titulo}: disponible en el tablero.")

    if not partes:
        partes.append(voz.SIN_RESULTADOS)

    texto = "\n\n".join(partes)
    return {"answer": texto, "messages": [AIMessage(content=texto)]}


def verificar(state: AgentState) -> dict[str, Any]:
    """Contrasta la respuesta contra su evidencia. CERO tokens si esta sana.

    La deteccion es una comparacion de conjuntos entre los identificadores
    citados y los recuperados: no cuesta nada. Solo se paga una llamada cuando
    esa comparacion falla, que es el unico caso en que hay algo que arreglar.
    """
    original = state.get("answer") or ""
    if not budget.alcanza():
        # La correccion cuesta una llamada. Sin tiempo, la respuesta sale tal
        # cual: el verificador mejora una respuesta, no la sustituye.
        log.info("presupuesto de tiempo agotado; se omite la verificacion")
        return {}
    corregida = verifier.verificar(original, state.get("evidence") or [])
    if corregida == original:
        return {}

    mensajes = state.get("messages") or []
    borrar = []
    if mensajes and getattr(mensajes[-1], "id", None):
        borrar = [RemoveMessage(id=mensajes[-1].id)]
    return {"answer": corregida, "messages": [*borrar, AIMessage(content=corregida)]}


# -- aristas ----------------------------------------------------------------


def tras_ejecutar(state: AgentState) -> Literal["planificar", "componer"]:
    """Replanifica como maximo una vez, y solo si no hubo evidencia.

    El tope es la diferencia entre un sistema que insiste y uno que se queda
    dando vueltas gastando presupuesto sin lanzar ningun error.
    """
    if state.get("suficiente"):
        return "componer"
    if not budget.alcanza(budget.MARGEN_REDACCION_S):
        # Replanificar son dos llamadas mas (plan y ejecucion) y el turno ya va
        # tarde. Se prefiere redactar con lo que hay: el evaluador puntua una
        # respuesta imperfecta, no una que no llego.
        log.info("sin presupuesto de tiempo para replanificar; se redacta con lo que hay")
        return "componer"
    if state.get("replans", 0) >= MAX_REPLANES:
        log.info(
            "evidencia insuficiente tras %s replanificacion(es); se redacta igual", MAX_REPLANES
        )
        return "componer"
    return "planificar"


def build_graph(checkpointer: Any = None):
    """Construye y compila el grafo. Llamar una vez al arrancar.

    Args:
        checkpointer: memoria conversacional. Por defecto, la de
            `src/agents/checkpoint.py` (SQLite). Pasar `False` para compilar sin
            memoria.
    """
    if checkpointer is None:
        from src.agents.checkpoint import get_checkpointer

        checkpointer = get_checkpointer()

    g = StateGraph(AgentState)
    g.add_node("begin", begin)
    g.add_node("planificar", planificar)
    g.add_node("ejecutar", ejecutar)
    g.add_node("componer", componer)
    g.add_node("verificar", verificar)

    g.add_edge(START, "begin")
    g.add_edge("begin", "planificar")
    g.add_edge("planificar", "ejecutar")
    g.add_conditional_edges(
        "ejecutar", tras_ejecutar, {"planificar": "planificar", "componer": "componer"}
    )
    g.add_edge("componer", "verificar")
    g.add_edge("verificar", END)

    return g.compile(checkpointer=checkpointer or None)


__all__ = ["Paso", "build_graph"]
