"""Orquestacion de `POST /chat`: del texto del usuario al JSON de ADL (§2.4).

`main.py` solo enruta; aqui vive la logica. Regla dura: nunca lanza. Si el
grafo o el proveedor de modelos fallan, se responde con lo que si se pudo
(fragmentos recuperados) y el fallo queda en `metadata.estado`.

Este modulo es el LADO API de la frontera con el grafo. Lo que el API espera
del grafo esta en `src/api/CONTRATO_GRAFO.md`; en corto:
- `build_graph()` devuelve algo con `.invoke({"question": ...}, config=...)`;
- el resultado trae `answer`;
- el `sesion_id` llega como `config["configurable"]["thread_id"]`;
- tools y llamadas al LLM se anotan en `observability` (turnlog / usage).
Este modulo no conoce nodos, prompts ni memoria: eso es del grafo.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any

from pydantic import ValidationError

from src.api import stub
from src.api.contracts import (
    ChatRequest,
    ChatResponse,
    Evaluacion,
    Metadata,
    TokenCount,
    TokensPorAgente,
    ToolCall,
)
from src.config import get_logger, get_settings
from src.observability import tracing, turnlog, usage

log = get_logger(__name__)

_STUB_AGENT_ID = "agente_qa"

_graph_lock = threading.Lock()
_graph: Any = None


def _get_graph() -> Any:
    """El grafo unico del proceso, construido al primer uso."""
    global _graph
    with _graph_lock:
        if _graph is None:
            from src.agents.graph import build_graph

            _graph = build_graph()
        return _graph


def reset_graph() -> None:
    """Descarta el grafo construido (pruebas)."""
    global _graph
    with _graph_lock:
        _graph = None


def parse_body(raw: bytes) -> ChatRequest | None:
    """Interpreta el cuerpo: JSON con la pregunta o texto plano. None si no hay pregunta."""
    text = raw.decode("utf-8", errors="replace").strip()
    if not text:
        return None
    try:
        data: Any = json.loads(text)
    except ValueError:
        data = text
    try:
        if isinstance(data, dict):
            return ChatRequest.model_validate(data)
        return ChatRequest(texto=data if isinstance(data, str) else text)
    except ValidationError:
        return None


def _retrieval_fallback(texto: str) -> str:
    """Sin modelo, lo honesto y util es entregar los fragmentos relevantes."""
    try:
        from src.tools.corpus import _get_index

        hits = _get_index().search(texto, k=5)
    except Exception as exc:  # noqa: BLE001 - degradacion, nunca 500
        log.warning("recuperacion de respaldo fallo: %s", exc)
        return "No fue posible procesar la consulta en este momento."
    turnlog.add_context([f"({h.citation()}) {h.text}" for h in hits])
    if not hits:
        return "No encontre informacion sobre esa consulta en el corpus."
    cuerpo = "\n\n".join(f"[{i}] ({h.citation()}) {h.text[:500]}" for i, h in enumerate(hits, 1))
    return f"No pude redactar una respuesta con el modelo. Fragmentos mas relevantes:\n\n{cuerpo}"


def _build(texto: str, respuesta: str, estado: str, start: float) -> ChatResponse:
    totals = usage.request_usage()
    breakdown = usage.request_breakdown()
    return ChatResponse(
        respuesta=respuesta,
        evaluacion=Evaluacion(
            input=texto,
            actual_output=respuesta,
            retrieval_context=turnlog.retrieval_context(),
            tools_called=[ToolCall(**c) for c in turnlog.tool_calls()],
        ),
        metadata=Metadata(
            num_interacciones=totals["calls"],
            agentes_invocados=[b["agente"] for b in breakdown],
            tokens=TokenCount(
                input=totals["input_tokens"],
                output=totals["output_tokens"],
                total=totals["total_tokens"],
            ),
            tokens_por_agente=[TokensPorAgente(**b) for b in breakdown],
            latencia_ms=int((time.perf_counter() - start) * 1000),
            estado=estado,
        ),
    )


def invalid_input_response() -> ChatResponse:
    """Cuerpo sin pregunta reconocible: 200 con `estado`, no un 422."""
    start = time.perf_counter()
    tracing.start_trace()
    usage.start_request()
    turnlog.start_turn()
    return _build("", "No recibi ninguna pregunta.", "error_entrada_invalida", start)


def run_chat(texto: str, session_id: str) -> ChatResponse:
    """Ejecuta un turno de conversacion. Bloqueante: llamar desde un thread."""
    start = time.perf_counter()
    s = get_settings()
    tracing.start_trace()
    usage.start_request()
    turnlog.start_turn()

    if s.is_stub:
        usage.record_usage(None, agent=_STUB_AGENT_ID, model="stub")
        context = stub.stub_fragments(texto)
        turnlog.add_context(context)
        turnlog.record_tool_call("search_corpus", {"query": texto}, "\n\n".join(context))
        return _build(texto, stub.stub_answer(texto), "ok", start)

    estado, respuesta = "ok", ""
    if not s.llm_configured:
        estado = "error_llm_no_configurado"
    else:
        try:
            # el sesion_id viaja como thread_id: si el grafo tiene memoria, la usa
            config = {"configurable": {"thread_id": session_id}}
            result = _get_graph().invoke({"question": texto}, config=config)
            respuesta = result.get("answer") or ""
            if not respuesta:
                estado = "error_respuesta_vacia"
        except Exception:
            log.exception("el grafo fallo; se degrada a recuperacion pura")
            estado = "error_grafo"

    if estado != "ok":
        respuesta = _retrieval_fallback(texto)
    return _build(texto, respuesta, estado, start)
