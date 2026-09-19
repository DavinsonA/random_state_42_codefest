"""Orquestacion de `POST /chat`: del texto del usuario al JSON de ADL (§2.4).

`main.py` solo enruta; aqui vive el turno completo. Regla dura: nunca lanza. Si
el grafo o el proveedor de modelos fallan, se responde con lo que si se pudo
—los fragmentos recuperados— y el fallo queda en `metadata.estado`.

Orden del turno, y el orden importa:

    guardian -> memoria -> ejecucion -> guardian de salida -> memoria

1. **Guardian** primero, porque rechazar un ataque cuesta cero tokens y no debe
   llegar ni al cache ni al modelo.
2. **Memoria** despues, porque un acierto ahorra el turno entero.
3. **Ejecucion**: stub, o el grafo con el `sesion_id` como `thread_id`.
4. **Guardian de salida**, ultima barrera antes de devolver.
5. **Memoria**, que guarda lo que costo producir.

Este modulo es el LADO API de la frontera con el grafo. Lo que el API espera del
grafo esta en `src/api/CONTRATO_GRAFO.md`. No conoce nodos, prompts ni memoria
del grafo: eso es del grafo.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any

from pydantic import ValidationError

from src.agents import budget, guardian, memory, voz
from src.api import stub
from src.api.contracts import (
    AgentResponse,
    ChatRequest,
    Citation,
    Evaluacion,
    Metadata,
    Tokens,
    TokensPorAgente,
    ToolCall,
    ViewSpec,
)
from src.config import get_logger, get_settings
from src.observability import tracing, turnlog, usage

log = get_logger(__name__)

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


# -- entrada ----------------------------------------------------------------


def parse_body(raw: bytes) -> ChatRequest | None:
    """Interpreta el cuerpo: JSON con la pregunta, o texto plano.

    La agent card declara `input_modes: ["text/plain"]` y la especificacion
    admite "texto plano o JSON". Devuelve None si no hay pregunta reconocible;
    el endpoint lo convierte en un 200 cortes, nunca en un 422.
    """
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


# -- salida -----------------------------------------------------------------


def _secretos() -> tuple[str, ...]:
    """Valores que jamas pueden aparecer en una respuesta."""
    s = get_settings()
    return tuple(v for v in (s.llm_api_key, s.llm_base_url) if v)


def _build(
    texto: str,
    respuesta: str,
    estado: str,
    start: float,
    *,
    agentes_extra: tuple[str, ...] = (),
    view_spec: ViewSpec | None = None,
) -> AgentResponse:
    """Arma el JSON de ADL con lo que el turno realmente registro.

    Nada de esto se fabrica: `tools_called`, `retrieval_context` y `citations`
    salen de `turnlog`, y los tokens de `usage`. Si un agente no anoto su
    consumo, aparece en cero — que es la verdad observable, no una estimacion.
    """
    totals = usage.request_usage()
    breakdown = usage.request_breakdown()

    # Los que gastaron tokens, mas los que actuaron sin gastarlos. Derivar esta
    # lista solo del desglose de tokens dejaba invisible al agente analitico,
    # que por diseno cuesta cero: un agente que trabaja y no aparece es credito
    # perdido, y es justo el que da puntos extra.
    agentes = [b["agente"] for b in breakdown]
    for extra in (*turnlog.agentes(), *agentes_extra):
        if extra not in agentes:
            agentes.append(extra)

    return AgentResponse(
        respuesta=respuesta,
        evaluacion=Evaluacion(
            input=texto,
            actual_output=respuesta,
            retrieval_context=turnlog.retrieval_context(),
            tools_called=[ToolCall(**c) for c in turnlog.tool_calls()],
        ),
        metadata=Metadata(
            num_interacciones=totals["calls"],
            agentes_invocados=agentes,
            tokens=Tokens(
                input=totals["input_tokens"],
                output=totals["output_tokens"],
                total=totals["total_tokens"],
            ),
            tokens_por_agente=[TokensPorAgente(**b) for b in breakdown],
            latencia_ms=int((time.perf_counter() - start) * 1000),
            estado=estado,
        ),
        mode=get_settings().arpia_mode,  # type: ignore[arg-type]
        citations=[Citation(**c) for c in turnlog.citations()],
        view_spec=view_spec,
        trace_id=tracing.current_trace_id() or "",
    )


def _leer_view_spec(crudo: Any) -> ViewSpec | None:
    """Valida la vista que emitio el grafo. Una vista invalida no se devuelve.

    El esquema cerrado de `ViewSpec` es una frontera de seguridad, no una
    formalidad: si el visualizador produce algo fuera del vocabulario, se
    descarta aqui y la respuesta de texto sigue siendo util.
    """
    if not crudo:
        return None
    try:
        return ViewSpec.model_validate(crudo)
    except ValidationError as exc:
        log.warning("el grafo emitio un view_spec invalido, se descarta: %s", exc.errors()[:2])
        return None


def _retrieval_fallback(texto: str) -> str:
    """Sin modelo, lo honesto y util es entregar los fragmentos relevantes.

    Una disculpa generica puntua cero en relevancia; unos fragmentos con su
    procedencia son evidencia real, aunque no esten redactados.
    """
    try:
        from src.tools.corpus import _get_index

        hits = _get_index().search(texto, k=5)
    except Exception as exc:  # noqa: BLE001 - degradacion, nunca 500
        log.warning("recuperacion de respaldo fallo: %s", exc)
        return voz.SERVICIO_DEGRADADO

    turnlog.add_context([f"({h.citation()}) {h.text}" for h in hits])
    turnlog.add_citations(
        [
            {
                "doc_id": h.doc_id,
                "chunk_id": h.chunk_id,
                "fuente": h.metadata.get("organizacion") or h.metadata.get("fuente"),
                "fragmento": h.text[:240],
            }
            for h in hits
        ]
    )
    if not hits:
        return voz.SIN_RESULTADOS
    cuerpo = "\n\n".join(f"[{i}] ({h.citation()}) {h.text[:500]}" for i, h in enumerate(hits, 1))
    return f"{voz.SIN_REDACCION}\n\n{cuerpo}"


def invalid_input_response() -> AgentResponse:
    """Cuerpo sin pregunta reconocible: 200 con `estado`, no un 422."""
    start = time.perf_counter()
    tracing.start_trace()
    usage.start_request()
    turnlog.start_turn()
    return _build(
        "",
        voz.SIN_CONSULTA,
        "error_entrada_invalida",
        start,
    )


# -- turno ------------------------------------------------------------------


def run_chat(texto: str, session_id: str) -> AgentResponse:
    """Ejecuta un turno completo. Bloqueante: llamar desde un thread."""
    start = time.perf_counter()
    s = get_settings()
    tracing.start_trace()
    usage.start_request()
    turnlog.start_turn()
    budget.start_turn(s.turn_budget_s)

    # 1. Guardian de entrada. Cero tokens.
    veredicto = guardian.revisar_entrada(texto)
    if not veredicto.permitido:
        return _build(
            texto,
            veredicto.texto,
            f"rechazado:{veredicto.categoria}",
            start,
            agentes_extra=(guardian.AGENTE,),
        )
    texto = veredicto.texto

    # 2. Memoria. Un acierto ahorra el turno entero.
    cacheada = memory.cache.buscar(texto, session_id)
    if cacheada is not None:
        cacheada.metadata.latencia_ms = int((time.perf_counter() - start) * 1000)
        return cacheada

    # 3. Ejecucion.
    view_spec: ViewSpec | None = None
    if s.is_stub:
        respuesta, view_spec, estado = stub.stub_turn(texto)
    else:
        estado, respuesta = "ok", ""
        if not s.llm_configured:
            estado = "error_llm_no_configurado"
        else:
            try:
                # el sesion_id viaja como thread_id: si el grafo tiene memoria, la usa
                config = {"configurable": {"thread_id": session_id}}
                result = _get_graph().invoke({"question": texto}, config=config)
                respuesta = result.get("answer") or ""
                view_spec = _leer_view_spec(result.get("view_spec"))
                if not respuesta:
                    estado = "error_respuesta_vacia"
            except Exception:
                log.exception("el grafo fallo; se degrada a recuperacion pura")
                estado = "error_grafo"
        if estado != "ok":
            respuesta = _retrieval_fallback(texto)

    # 4. Guardian de salida.
    salida = guardian.revisar_salida(respuesta, _secretos())
    if not salida.permitido:
        return _build(
            texto,
            salida.texto,
            f"rechazado:{salida.categoria}",
            start,
            agentes_extra=(guardian.AGENTE,),
        )

    construida = _build(texto, respuesta, estado, start, view_spec=view_spec)

    # 5. Memoria: se guarda lo que costo producir. No se cachea un error ni un
    #    rechazo: repetirlos sale gratis y cachearlos congelaria un fallo
    #    transitorio durante toda la ventana de evaluacion.
    if not estado.startswith(("error", "rechazado")):
        memory.cache.guardar(texto, construida, session_id)
    return construida
