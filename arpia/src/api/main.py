"""API de A.R.P.I.A.

Este es el artefacto que consume el pipeline de evaluacion de ADL: se mide la
aplicacion desplegada, no el repositorio. El contrato de `POST /chat` esta en
`src/api/contracts.py` y sigue la especificacion tecnica de la Etapa 2 (§2.4).

Regla dura de esta API: **ningun camino devuelve 500 ni 422**. Un fallo interno,
una dependencia caida o un cuerpo malformado se reportan como degradacion
(`status`, `metadata.estado`) dentro de una respuesta 200 bien formada. Un 422
delante del evaluador puntua cero en esa pregunta; una respuesta degradada y
explicada, no.

Los esquemas viven en `src/api/contracts.py`, no aqui.
"""

from __future__ import annotations

import json
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.agents import guardian, memory
from src.agents.card import agent_ids, load_card
from src.api import routing, stub
from src.api.contracts import (
    AgentResponse,
    ChatRequest,
    Evaluacion,
    HealthResponse,
    Metadata,
    UsageResponse,
)
from src.config import get_logger, get_settings
from src.observability import tracing, usage
from src.retrieval import encoder
from src.tools.registry import registry

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Calienta el encoder local al arrancar, en segundo plano.

    La primera carga de bge-m3 descarga ~2 GB y tarda minutos. Si eso ocurre
    dentro de la peticion de un evaluador, se le cobra como latencia —o se cae
    por timeout—. Aqui se paga una vez, mientras el contenedor arranca, y en un
    hilo aparte para que `/health` responda de inmediato: Coolify necesita saber
    que el servicio esta vivo antes de que el modelo termine de cargar.

    En modo stub no se carga nada: no hay nada real que codificar.
    """
    s = get_settings()
    if not s.is_stub:
        threading.Thread(target=encoder.warmup, name="encoder-warmup", daemon=True).start()
    yield


app = FastAPI(title="A.R.P.I.A.", version="0.1.0", lifespan=lifespan)


# -- helpers ---------------------------------------------------------------


def _check_index() -> tuple[bool, str | None]:
    """Indice cargado y alineado con su metadata. Nunca lanza."""
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


def _degradada(
    texto: str,
    estado: str,
    mensaje: str,
    latencia_ms: int,
    agentes: list[str] | None = None,
) -> AgentResponse:
    """Respuesta valida cuando no se produjo una real. Mantiene los tres
    bloques: el evaluador siempre recibe algo que puede parsear y calificar.

    `num_interacciones` y `tokens` quedan en cero, que es la verdad: no hubo
    llamada al modelo.
    """
    return AgentResponse(
        respuesta=mensaje,
        evaluacion=Evaluacion(input=texto, actual_output=mensaje),
        metadata=Metadata(estado=estado, latencia_ms=latencia_ms, agentes_invocados=agentes or []),
        mode=get_settings().arpia_mode,  # type: ignore[arg-type]
    )


def _secretos() -> tuple[str, ...]:
    """Valores que jamas pueden aparecer en una respuesta."""
    s = get_settings()
    return tuple(v for v in (s.llm_api_key, s.llm_base_url) if v)


async def _leer_consulta(request: Request) -> ChatRequest:
    """Extrae la consulta del cuerpo, venga como venga. Nunca lanza.

    La agent card declara `input_modes: ["text/plain"]` y la especificacion
    admite "texto plano o JSON", asi que el endpoint acepta las dos formas y
    varios alias de campo. Cualquier cuerpo que no se entienda produce una
    consulta vacia, que el endpoint convierte en una respuesta cortes con 200.
    """
    try:
        crudo = await request.body()
    except Exception:  # noqa: BLE001 - frontera: leer el cuerpo nunca tumba /chat
        return ChatRequest()
    if not crudo:
        return ChatRequest()

    try:
        datos = json.loads(crudo)
    except (ValueError, UnicodeDecodeError):
        return ChatRequest(texto=crudo.decode("utf-8", errors="replace"))

    if isinstance(datos, str):  # JSON que es solo una cadena
        return ChatRequest(texto=datos)
    if isinstance(datos, dict):
        try:
            return ChatRequest.model_validate(datos)
        except Exception:  # noqa: BLE001 - un esquema inesperado no puede ser un 422
            log.warning("cuerpo JSON con forma inesperada: %s", sorted(datos)[:6])
            return ChatRequest()
    return ChatRequest()


# -- nunca un 422 ----------------------------------------------------------


@app.exception_handler(RequestValidationError)
async def _sin_422(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Cuerpo malformado -> 200 con respuesta degradada, no 422.

    El evaluador envia el cuerpo que decida su pipeline. Si no lo entendemos,
    el fallo es nuestro y se reporta en `metadata.estado`, no se castiga la
    pregunta con un error de esquema.
    """
    log.warning("cuerpo no parseable en %s: %s", request.url.path, exc.errors()[:2])
    respuesta = _degradada(
        "",
        "entrada_no_parseable",
        "No pude leer el cuerpo de la peticion. Envia un JSON con el campo "
        '"texto" (o "message"/"query") con tu consulta.',
        0,
    )
    return JSONResponse(status_code=200, content=respuesta.model_dump())


# -- endpoints -------------------------------------------------------------


@app.post("/chat", response_model=AgentResponse)
async def chat(request: Request) -> AgentResponse:
    """Endpoint que evalua ADL. Devuelve los tres bloques del contrato §2.4.

    Acepta JSON (`{"texto": ...}` y alias) o `text/plain`, como declara la
    agent card. En `ARPIA_MODE=stub` responde con datos simulados y marcados,
    sin tocar indice ni gateway: cero tokens del presupuesto. En `live`
    (Fase 3 en adelante) delega en el orquestador.
    """
    inicio = time.perf_counter()
    req = await _leer_consulta(request)
    tracing.start_trace()
    usage.start_request()
    registry.reset()
    texto = (req.texto or "").strip()

    def _ms() -> int:
        return int((time.perf_counter() - inicio) * 1000)

    if not texto:
        return _degradada(
            texto,
            "entrada_vacia",
            "No recibi ninguna consulta. Preguntame sobre inteligencia artificial "
            "en entornos militares, seguridad del entorno espacial o dinamicas "
            "territoriales, y te respondo con la evidencia del corpus.",
            _ms(),
        )

    s = get_settings()
    try:
        # 1. Guardian. Determinista y primero: un ataque no debe llegar ni al
        #    cache ni al modelo. Cuesta cero tokens rechazarlo aqui.
        veredicto = guardian.revisar_entrada(texto)
        if not veredicto.permitido:
            return _degradada(
                texto,
                f"rechazado:{veredicto.categoria}",
                veredicto.texto,
                _ms(),
                agentes=[guardian.AGENTE],
            )
        texto = veredicto.texto

        # 2. Memoria. Un acierto ahorra el turno completo.
        cacheada = memory.cache.buscar(texto)
        if cacheada is not None:
            cacheada.metadata.latencia_ms = _ms()
            return cacheada

        # 3. Ejecucion.
        if s.is_stub:
            respuesta = await run_in_threadpool(stub.stub_response, texto, latencia_ms=_ms())
        else:
            # Fase 3: aqui entra el orquestador. Hasta entonces `live` no tiene
            # nada que ejecutar y lo dice, en vez de fingir una respuesta real.
            return _degradada(
                texto,
                "live_no_implementado",
                "El modo real aun no esta habilitado en esta version del servicio.",
                _ms(),
            )

        # 4. Guardian de salida: ultima barrera antes de devolver.
        salida = guardian.revisar_salida(respuesta.respuesta, _secretos())
        if not salida.permitido:
            return _degradada(
                texto,
                f"rechazado:{salida.categoria}",
                salida.texto,
                _ms(),
                agentes=[guardian.AGENTE],
            )

        memory.cache.guardar(texto, respuesta)
        respuesta.metadata.latencia_ms = _ms()
        return respuesta
    except Exception as exc:  # noqa: BLE001 - frontera: /chat nunca propaga
        log.exception("fallo no controlado en /chat")
        return _degradada(
            texto,
            f"error_interno:{type(exc).__name__}",
            "Ocurrio un fallo interno procesando la consulta. El servicio sigue "
            "operativo; intenta de nuevo o reformula la pregunta.",
            _ms(),
        )


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
    summary = usage.usage_summary()
    return UsageResponse(
        requests=usage.request_count(),
        llm_calls=summary["calls"],
        input_tokens=summary["input_tokens"],
        output_tokens=summary["output_tokens"],
        trace_count=tracing.trace_count(),
        cache=memory.cache.stats(),
    )


# Al final a proposito: el montaje de `static/` debe quedar DESPUES de las
# rutas de la API para no capturarlas.
routing.install(app)
