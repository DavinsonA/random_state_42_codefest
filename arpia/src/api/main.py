"""API de A.R.P.I.A.

Este es el artefacto que consume el pipeline de evaluacion de ADL: se mide la
aplicacion desplegada, no el repositorio. El contrato de `POST /chat` esta en
`src/api/contracts.py` y sigue la especificacion tecnica de la Etapa 2 (§2.4).

Este modulo solo enruta y reporta estado. El turno de conversacion vive en
`src/api/chat.py`; la frontera con el grafo, en `src/api/CONTRATO_GRAFO.md`.

Regla dura: **ningun camino devuelve 500 ni 422**. Un fallo interno, una
dependencia caida o un cuerpo malformado se reportan como degradacion
(`status`, `metadata.estado`) dentro de una respuesta 200 bien formada. Un 422
delante del evaluador puntua cero en esa pregunta; una respuesta degradada y
explicada, no.
"""

from __future__ import annotations

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.agents import checkpoint
from src.agents.card import agent_ids, load_card
from src.api import chat as chat_mod
from src.api import dashboard, routing, session
from src.api.contracts import AgentResponse, HealthResponse, UsageResponse
from src.config import get_logger, get_settings
from src.observability import tracing, usage
from src.retrieval import encoder
from src.tools.registry import registry

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Calienta el encoder local al arrancar, en segundo plano.

    La primera carga de bge-m3 descarga ~2 GB y tarda ~90 s. Si eso ocurre
    dentro de la peticion de un evaluador, se le cobra como latencia —o se cae
    por timeout—. Aqui se paga una vez, mientras el contenedor arranca, y en un
    hilo aparte para que `/health` responda de inmediato: Coolify necesita saber
    que el servicio esta vivo antes de que el modelo termine de cargar.

    En modo stub no se carga nada: no hay nada real que codificar.
    """
    if not get_settings().is_stub:
        threading.Thread(target=encoder.warmup, name="encoder-warmup", daemon=True).start()
    yield


app = FastAPI(title="A.R.P.I.A.", version="0.1.0", lifespan=lifespan)


# -- helpers de estado ------------------------------------------------------


def _check_index() -> tuple[bool, str | None]:
    """Indice cargado y alineado con su metadata. Nunca lanza.

    En modo stub NO se carga: el indice ocupa 1,3 GB y en stub no se usa para
    nada. Coolify llama a `/health` cada 30 s, y la primera llamada dejaria esa
    memoria reservada para siempre sin que nadie la aproveche.
    """
    if get_settings().is_stub:
        return False, "modo stub: el indice no se carga"
    try:
        from src.tools.corpus import _get_index

        return _get_index().check()
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


# -- nunca un 422 -----------------------------------------------------------


@app.exception_handler(RequestValidationError)
async def _sin_422(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Cuerpo malformado -> 200 con respuesta degradada, no 422.

    Es una red de seguridad: `chat.parse_body` ya acepta JSON y texto plano, asi
    que en la practica no deberia dispararse. Si se dispara, el fallo es
    nuestro y se reporta en `metadata.estado`, no se castiga la pregunta.
    """
    log.warning("cuerpo no parseable en %s: %s", request.url.path, exc.errors()[:2])
    return JSONResponse(status_code=200, content=chat_mod.invalid_input_response().model_dump())


# -- endpoints --------------------------------------------------------------


@app.post("/chat", response_model=AgentResponse)
async def chat(request: Request, response: Response) -> AgentResponse:
    """Endpoint que evalua ADL. Devuelve los tres bloques del contrato §2.4.

    Acepta JSON (`{"texto": ...}` y alias) o `text/plain`, como declara la agent
    card. El `sesion_id` se resuelve por cuerpo, header `X-Session-Id` o cookie,
    y si no hay ninguno el servidor emite uno nuevo (ver `src/api/session.py`).

    El turno corre en un hilo del pool: el grafo y el encoder son bloqueantes y
    no pueden ocupar el bucle de eventos mientras ADL manda preguntas en
    paralelo.
    """
    raw = await request.body()
    req = chat_mod.parse_body(raw)

    sid, es_nueva = session.resolve_session(req.sesion_id if req else None, request)
    session.attach_session(response, sid, es_nueva, get_settings().session_ttl_s)

    if req is None or not req.texto.strip():
        return chat_mod.invalid_input_response()
    return await run_in_threadpool(chat_mod.run_chat, req.texto, sid)


@app.get("/agent-card")
def agent_card() -> JSONResponse:
    """Agent card en formato ADL §2.3 (no es el estandar A2A).

    Se sirve el JSON tal cual esta en `agent_card.json`: es un entregable del
    Reto 1 y no debe reformatearse al pasar por aqui.
    """
    card = load_card()
    if not card:
        return JSONResponse(status_code=200, content={"error": "agent_card.json no disponible"})
    return JSONResponse(content=card)


@app.get("/health", response_model=HealthResponse)
def health(response: Response) -> HealthResponse:
    """Disponibilidad real del servicio, con sus capacidades.

    En modo `stub` el estado nunca es "ok": el despliegue evaluado debe correr
    con datos reales (`RETO.md` §Restricciones duras), asi que un `stub` en
    produccion tiene que verse a simple vista.
    """
    s = get_settings()
    warnings: list[str] = []

    index_loaded, index_err = _check_index()
    if index_err:
        warnings.append(f"indice: {index_err}")

    gateway_reachable, gateway_err = _check_gateway(s.llm_base_url)
    if gateway_err:
        warnings.append(f"gateway: {gateway_err}")

    card_loaded = bool(load_card())
    if not card_loaded:
        warnings.append("agent card: agent_card.json no disponible")

    tools = registry.names()
    if not tools:
        warnings.append("no hay tools registradas")

    if s.debug_trace:
        warnings.append("ARPIA_DEBUG_TRACE activo: /api/trace publica el contenido de los turnos")
    if s.is_stub:
        warnings.append("modo stub: las respuestas son simuladas, NO aptas para evaluacion")
        status = "degraded"
    elif index_loaded and gateway_reachable and card_loaded and tools:
        status = "ok"
    elif index_loaded or gateway_reachable:
        status = "degraded"
    else:
        status = "down"
        response.status_code = 503

    return HealthResponse(
        status=status,  # type: ignore[arg-type]
        version=app.version,
        mode=s.arpia_mode,  # type: ignore[arg-type]
        max_iterations=s.max_agent_iterations,
        index_loaded=index_loaded,
        gateway_reachable=gateway_reachable,
        agent_card_loaded=card_loaded,
        debug_trace=s.debug_trace,
        memoria_persistente=checkpoint.es_persistente(),
        encoder_listo=encoder.loaded(),
        agentes_registrados=agent_ids(),
        tools_registered=tools,
        warnings=warnings,
    )


@app.get("/usage", response_model=UsageResponse)
def usage_endpoint() -> UsageResponse:
    """Consumo acumulado de la sesion del proceso.

    Cada equipo tiene una bolsa de 100 USD: al superarla la API key deja de
    funcionar. Este numero es solo lo que el propio proceso observo, no la
    facturacion real (esa la manda el dashboard de LiteLLM).
    """
    from src.agents import memory, verifier

    summary = usage.usage_summary()
    return UsageResponse(
        requests=usage.request_count(),
        llm_calls=summary["calls"],
        input_tokens=summary["input_tokens"],
        output_tokens=summary["output_tokens"],
        trace_count=tracing.trace_count(),
        cache=memory.cache.stats(),
        verificador=verifier.contador.stats(),
    )


# Endpoints del tablero (Reto 2). Antes del montaje estatico, que captura todo
# lo que no case con una ruta declarada.
app.include_router(dashboard.router)

# Al final a proposito: el montaje de `static/` debe quedar DESPUES de las
# rutas de la API para no capturarlas.
routing.install(app)
