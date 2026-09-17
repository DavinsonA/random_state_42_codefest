"""API de A.R.P.I.A.

Este es el artefacto que consume el pipeline de evaluacion del jurado: un
pipeline automatizado (DeepEval) mide la aplicacion desplegada en Coolify a
traves de este endpoint HTTP, no el repositorio. El contrato de
entrada/salida debe coincidir EXACTAMENTE con el que especifique el handbook
tecnico del reto; desviarse genera friccion en la evaluacion automatica.

Regla dura de esta API: ningun endpoint propaga una excepcion sin capturar.
Un fallo interno se reporta como degradacion (`warnings`, `status`), nunca
como 500 ni como una caida silenciosa del proceso.

Los esquemas viven en `src/api/contracts.py`, no aqui. Al conocer el reto:
ajustar `AnalyzePayload`/`RetrievePayload` en `contracts.py` y nada mas.
"""

from __future__ import annotations

import time

from fastapi import FastAPI, Response

from src.api import stub
from src.api.contracts import (
    AnalyzeRequest,
    AnalyzeResponse,
    Evidence,
    Fragment,
    HealthResponse,
    RetrieveResponse,
    TraceModel,
    UsageResponse,
)
from src.config import get_logger, get_settings
from src.observability import tracing, usage
from src.tools.registry import registry

log = get_logger(__name__)
app = FastAPI(title="A.R.P.I.A.", version="0.1.0")

_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        from src.agents.graph import build_graph

        _graph = build_graph()
    return _graph


# -- helpers ---------------------------------------------------------------


def _check_index() -> tuple[bool, str | None]:
    """Indice cargado y alineado con su metadata. Nunca lanza."""
    try:
        from src.tools.corpus import _get_index

        idx = _get_index()
        idx._load()  # noqa: SLF001 - chequeo deliberado del estado interno
        ok = idx._index is not None and idx._index.ntotal == len(idx._meta or [])
        return ok, None if ok else "desalineacion indice<->metadata"
    except Exception as exc:  # noqa: BLE001 - /health nunca lanza
        return False, f"{type(exc).__name__}: {exc}"


def _check_gateway(base_url: str) -> tuple[bool, str | None]:
    """Alcanzabilidad del gateway con timeout corto. Nunca lanza."""
    if not base_url:
        return False, "LLM_BASE_URL no configurado"
    try:
        import httpx

        httpx.get(base_url, timeout=2.0)
        return True, None
    except Exception as exc:  # noqa: BLE001 - /health nunca lanza
        return False, f"{type(exc).__name__}: {exc}"


def _pure_retrieval(query: str, k: int) -> list[Evidence]:
    """Recuperacion sin LLM, usada como degradacion cuando el grafo falla."""
    from src.tools.corpus import _get_index

    with tracing.span("retrieval", "fallback_retrieval", input={"query": query, "k": k}) as sp:
        hits = _get_index().search(query, k=k)
        sp.set_output(f"{len(hits)} fragmentos")
    return [
        Evidence(rank=i, doc_id=h.doc_id, chunk_id=h.chunk_id, text=h.text, score=h.score)
        for i, h in enumerate(hits, start=1)
    ]


# -- endpoints -----------------------------------------------------------


@app.get("/health", response_model=HealthResponse)
def health(response: Response) -> HealthResponse:
    """Disponibilidad real del servicio. Coolify y el jurado lo usan para saber
    si el servicio esta arriba, y con que capacidades.

    200 con `status="degraded"` si algo no esta disponible pero el servicio
    responde; 503 solo si NADA funciona. Un jurado que recibe 503 no puede
    distinguir "caido" de "aun arrancando" de "degradado pero util".
    """
    start = time.perf_counter()
    s = get_settings()
    warnings: list[str] = []

    index_loaded, index_err = _check_index()
    if index_err:
        warnings.append(f"indice: {index_err}")

    gateway_reachable, gateway_err = _check_gateway(s.llm_base_url)
    if gateway_err:
        warnings.append(f"gateway: {gateway_err}")

    tools = registry.names()
    if not tools:
        warnings.append("no hay tools registradas")

    # en modo stub el indice y el gateway no son requisito: la app esta
    # deliberadamente desconectada de ambos.
    required_ok = [bool(tools)] if s.is_stub else [index_loaded, gateway_reachable, bool(tools)]

    if all(required_ok):
        status = "ok"
    elif any(required_ok):
        status = "degraded"
    else:
        status = "down"
        response.status_code = 503

    return HealthResponse(
        mode=s.arpia_mode,
        elapsed_ms=round((time.perf_counter() - start) * 1000, 1),
        status=status,
        version=app.version,
        max_iterations=s.max_agent_iterations,
        index_loaded=index_loaded,
        gateway_reachable=gateway_reachable,
        tools_registered=tools,
        warnings=warnings,
    )


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    """Ejecuta el grafo agentico sobre una consulta y devuelve respuesta + evidencia.

    Nunca devuelve 500: ante fallo del gateway o del grafo, degrada a
    recuperacion pura (o a una respuesta vacia) y explica el porque en
    `warnings`. Una respuesta degradada y honesta puntua mejor que un error.
    """
    start = time.perf_counter()
    s = get_settings()
    trace_id = tracing.start_trace()
    usage.start_request()
    registry.reset()

    if s.is_stub:
        with tracing.span(
            "tool", "stub_analyze", input={"query": req.query, "top_k": req.top_k}
        ) as sp:
            result = stub.stub_analyze(req.query, req.top_k)
            sp.set_output(result["answer"][:200])
        return AnalyzeResponse(
            mode="stub",
            elapsed_ms=round((time.perf_counter() - start) * 1000, 1),
            warnings=result["warnings"],
            query=req.query,
            answer=result["answer"],
            evidence=[Evidence(**e) for e in result["evidence"]],
            trace=TraceModel(trace_id=trace_id, spans=tracing.to_spans()),
            tokens_used=usage.request_usage(),
        )

    warnings: list[str] = []
    answer = ""
    evidence: list[Evidence] = []

    if not s.llm_configured:
        warnings.append(
            "LLM_BASE_URL/LLM_API_KEY no configurados: se devuelve solo recuperacion pura."
        )
        try:
            evidence = _pure_retrieval(req.query, req.top_k)
        except Exception as exc:  # noqa: BLE001 - degradacion elegante, nunca 500
            log.warning("recuperacion pura fallo: %s", exc)
            warnings.append(f"recuperacion tambien fallo: {type(exc).__name__}: {exc}")
    else:
        try:
            result = _get_graph().invoke({"question": req.query, "turns": 0})
            answer = result.get("answer", "")
            evidence = [Evidence(**e) for e in result.get("evidence", [])]
        except Exception as exc:  # noqa: BLE001 - degradacion elegante, nunca 500
            log.exception("el grafo agentico fallo; se degrada a recuperacion pura")
            warnings.append(
                f"el grafo agentico fallo ({type(exc).__name__}: {exc}); "
                "se degrada a recuperacion pura"
            )
            try:
                evidence = _pure_retrieval(req.query, req.top_k)
            except Exception as exc2:  # noqa: BLE001 - degradacion elegante, nunca 500
                warnings.append(f"recuperacion tambien fallo: {type(exc2).__name__}: {exc2}")

    return AnalyzeResponse(
        mode="live",
        elapsed_ms=round((time.perf_counter() - start) * 1000, 1),
        warnings=warnings,
        query=req.query,
        answer=answer,
        evidence=evidence,
        trace=TraceModel(trace_id=trace_id, spans=tracing.to_spans()),
        tokens_used=usage.request_usage(),
    )


@app.post("/retrieve", response_model=RetrieveResponse)
def retrieve(req: AnalyzeRequest) -> RetrieveResponse:
    """Recuperacion pura, sin LLM. Util para depurar y para medir el retriever aislado."""
    start = time.perf_counter()
    s = get_settings()
    if s.is_stub:
        payload = stub.stub_retrieve(req.query, req.top_k)
        return RetrieveResponse(
            mode="stub",
            elapsed_ms=round((time.perf_counter() - start) * 1000, 1),
            query=payload["query"],
            documents=payload["documents"],
            fragments=[Fragment(**f) for f in payload["fragments"]],
        )

    from src.tools.corpus import _get_index

    hits = _get_index().search(req.query, k=req.top_k)
    return RetrieveResponse(
        mode="live",
        elapsed_ms=round((time.perf_counter() - start) * 1000, 1),
        query=req.query,
        documents=_get_index().top_documents(hits, n=3),
        fragments=[
            Fragment(rank=i, chunk_id=h.chunk_id, doc_id=h.doc_id, text=h.text, score=h.score)
            for i, h in enumerate(hits, start=1)
        ],
    )


@app.get("/usage", response_model=UsageResponse)
def usage_endpoint() -> UsageResponse:
    """Consumo acumulado de la sesion del proceso.

    Sirve para contrastar contra el dashboard de LiteLLM y detectar
    desviaciones temprano: el consumo real no es autorreportado, este numero
    es solo lo que el propio proceso observo en las respuestas del gateway.
    """
    start = time.perf_counter()
    s = get_settings()
    summary = usage.usage_summary()
    return UsageResponse(
        mode=s.arpia_mode,
        elapsed_ms=round((time.perf_counter() - start) * 1000, 1),
        requests=usage.request_count(),
        llm_calls=summary["calls"],
        input_tokens=summary["input_tokens"],
        output_tokens=summary["output_tokens"],
        trace_count=tracing.trace_count(),
    )
