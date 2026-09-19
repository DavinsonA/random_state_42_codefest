"""API de A.R.P.I.A.

Este es el artefacto que consume el pipeline de evaluacion de ADL: se mide la
aplicacion desplegada en Coolify a traves de este endpoint HTTP, no el
repositorio. El contrato de `POST /chat` esta en `src/api/contracts.py` y sigue
la especificacion tecnica de la Etapa 2 (§2.4).

Regla dura de esta API: ningun endpoint propaga una excepcion sin capturar.
Un fallo interno se reporta como degradacion (`status`, `metadata.estado`),
nunca como 500 ni como una caida silenciosa del proceso.

Los esquemas viven en `src/api/contracts.py`, no aqui.
"""

from __future__ import annotations

from fastapi import FastAPI, Response

from src.api.contracts import HealthResponse, UsageResponse
from src.config import get_logger, get_settings
from src.observability import tracing, usage
from src.tools.registry import registry

log = get_logger(__name__)
app = FastAPI(title="A.R.P.I.A.", version="0.1.0")


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


# -- endpoints -----------------------------------------------------------


@app.get("/health", response_model=HealthResponse)
def health(response: Response) -> HealthResponse:
    """Disponibilidad real del servicio. Coolify y el jurado lo usan para saber
    si el servicio esta arriba, y con que capacidades.

    200 con `status="degraded"` si algo no esta disponible pero el servicio
    responde; 503 solo si NADA funciona. Un jurado que recibe 503 no puede
    distinguir "caido" de "aun arrancando" de "degradado pero util".
    """
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
        status=status,
        version=app.version,
        mode=s.arpia_mode,
        max_iterations=s.max_agent_iterations,
        index_loaded=index_loaded,
        gateway_reachable=gateway_reachable,
        tools_registered=tools,
        warnings=warnings,
    )


@app.get("/usage", response_model=UsageResponse)
def usage_endpoint() -> UsageResponse:
    """Consumo acumulado de la sesion del proceso.

    Cada equipo tiene una bolsa de $100 USD en Bedrock: al superarla la API key
    deja de funcionar. Este numero es solo lo que el propio proceso observo, no
    la facturacion real.
    """
    summary = usage.usage_summary()
    return UsageResponse(
        requests=usage.request_count(),
        llm_calls=summary["calls"],
        input_tokens=summary["input_tokens"],
        output_tokens=summary["output_tokens"],
        trace_count=tracing.trace_count(),
    )
