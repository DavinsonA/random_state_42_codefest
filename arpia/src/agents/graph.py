"""Grafo agentico base de A.R.P.I.A.

Arquitectura deliberadamente minima: un bucle razonar -> herramienta ->
observar, con un nodo de redaccion SEPARADO y sin herramientas. Separar la
redaccion del bucle de busqueda mejora notablemente la calidad del texto final.

Este grafo es una plantilla. El dia del evento se adapta segun la linea de
trabajo elegida (`docs/architecture.md`), no se reescribe desde cero.
"""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from src.agents.state import AgentState
from src.config import get_logger, get_settings
from src.observability import tracing, usage
from src.tools.registry import registry

log = get_logger(__name__)

SYSTEM_PROMPT = """Eres un analista de fuentes abiertas.

Reglas:
- Busca evidencia antes de afirmar cualquier hecho.
- Cita siempre el identificador del documento del que proviene cada afirmacion.
- Si tras varias busquedas no encuentras evidencia, dilo explicitamente.
  No inventes, no completes con conocimiento general.
- No repitas una consulta que ya lanzaste.
"""


def _llm():
    """Cliente del gateway de modelos del evento (OpenAI-compatible)."""
    from langchain_openai import ChatOpenAI

    s = get_settings()
    if not s.llm_configured:
        raise RuntimeError("LLM_BASE_URL y LLM_API_KEY no configurados. Copia .env.example a .env.")
    return ChatOpenAI(
        base_url=s.llm_base_url,
        api_key=s.llm_api_key,
        model=s.llm_model,
        timeout=s.request_timeout_s,
        temperature=0,
    )


def _invoke_llm(model: Any, messages: list, span_name: str) -> AIMessage:
    """Invoca el LLM dentro de un span `llm`, y registra el consumo de tokens
    que devuelva el gateway (si lo devuelve)."""
    last_input = messages[-1].content if messages else ""
    with tracing.span("llm", span_name, input=str(last_input)[:2000]) as sp:
        response = model.invoke(messages)
        usage.record_usage(getattr(response, "usage_metadata", None))
        sp.set_output(str(getattr(response, "content", ""))[:2000])
        return response


# -- nodos ---------------------------------------------------------------


def reason(state: AgentState) -> dict:
    """Decide si hace falta otra herramienta o si ya hay evidencia suficiente."""
    messages = state.get("messages") or [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=state["question"]),
    ]
    model = _llm().bind_tools(registry.all())
    response = _invoke_llm(model, messages, "reason")
    return {"messages": [response], "turns": 1}


def compose(state: AgentState) -> dict:
    """Redacta la respuesta final. Nodo SIN herramientas, a proposito."""
    evidencia = "\n\n".join(
        m.content for m in state.get("messages", []) if getattr(m, "type", "") == "tool"
    )
    prompt = [
        SystemMessage(
            content=(
                "Redacta la respuesta final usando SOLO la evidencia recuperada. "
                "Cita el identificador de documento de cada afirmacion. Si la "
                "evidencia es insuficiente, dilo de forma explicita."
            )
        ),
        HumanMessage(content=f"Pregunta: {state['question']}\n\nEvidencia:\n{evidencia}"),
    ]
    answer = _invoke_llm(_llm(), prompt, "compose")
    return {"answer": answer.content, "messages": [AIMessage(content=answer.content)]}


# -- aristas -------------------------------------------------------------


def route(state: AgentState) -> Literal["tools", "compose"]:
    """Decide el siguiente paso. Aqui vive el diseño real del agente.

    Corta el bucle por tope de iteraciones aunque el modelo quiera seguir:
    un agente que no encuentra lo que busca puede reintentar indefinidamente
    sin lanzar ningun error, solo consumiendo presupuesto.
    """
    limit = get_settings().max_agent_iterations
    if state.get("turns", 0) >= limit:
        log.warning("tope de %s iteraciones alcanzado; se pasa a redaccion", limit)
        return "compose"

    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "tools"
    return "compose"


def build_graph():
    """Construye y compila el grafo. Llamar una vez al arrancar."""
    g = StateGraph(AgentState)
    g.add_node("reason", reason)
    g.add_node("tools", ToolNode(registry.all()))
    g.add_node("compose", compose)

    g.add_edge(START, "reason")
    g.add_conditional_edges("reason", route, {"tools": "tools", "compose": "compose"})
    g.add_edge("tools", "reason")  # esta arista es lo que lo hace un agente
    g.add_edge("compose", END)
    return g.compile()
