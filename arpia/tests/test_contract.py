"""Pruebas del contrato de la API (`src/api/contracts.py`).

El evaluador de ADL consume la aplicacion desplegada, no el repositorio: el
formato de `POST /chat` (especificacion §2.4) debe cumplirse siempre. Corren
en modo stub para no depender de indice, credenciales ni Bedrock.
"""

from __future__ import annotations

import os

os.environ.setdefault("ARPIA_MODE", "stub")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from src.api.contracts import (  # noqa: E402
    ChatRequest,
    ChatResponse,
    Evaluacion,
    Metadata,
    TokenCount,
    TokensPorAgente,
)
from src.api.main import app  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def _stub_mode(monkeypatch):
    """Fuerza modo stub y limpia la cache de settings para cada prueba."""
    from src import config

    monkeypatch.setenv("ARPIA_MODE", "stub")
    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()


# -- entrada de /chat --------------------------------------------------------


@pytest.mark.parametrize("clave", ["texto", "pregunta", "query", "input", "message", "question"])
def test_chat_request_acepta_alias_de_la_pregunta(clave):
    assert ChatRequest.model_validate({clave: "hola"}).texto == "hola"


@pytest.mark.parametrize("clave", ["sesion_id", "session_id", "thread_id"])
def test_chat_request_acepta_alias_de_sesion(clave):
    req = ChatRequest.model_validate({"texto": "hola", clave: "abc12345"})
    assert req.sesion_id == "abc12345"


def test_chat_request_sesion_es_opcional_e_ignora_campos_extra():
    req = ChatRequest.model_validate({"texto": "hola", "campo_desconocido": 1})
    assert req.sesion_id is None


def test_chat_request_rechaza_texto_vacio():
    with pytest.raises(ValidationError):
        ChatRequest.model_validate({"texto": ""})


# -- salida de /chat (formato ADL §2.4) --------------------------------------


def _metadata(**kw) -> Metadata:
    base = dict(
        num_interacciones=2,
        agentes_invocados=["orquestador", "agente_qa"],
        tokens=TokenCount(input=100, output=40, total=140),
        tokens_por_agente=[
            TokensPorAgente(
                agente="orquestador", modelo="gpt-oss-120b", input=60, output=10, total=70
            ),
            TokensPorAgente(
                agente="agente_qa", modelo="llama-3.3-70b", input=40, output=30, total=70
            ),
        ],
        latencia_ms=1200,
    )
    base.update(kw)
    return Metadata(**base)


def test_chat_response_tiene_los_tres_bloques_de_adl():
    resp = ChatResponse(
        respuesta="x",
        evaluacion=Evaluacion(input="q", actual_output="x"),
        metadata=_metadata(),
    )
    body = resp.model_dump()
    assert body.keys() == {"respuesta", "evaluacion", "metadata"}
    assert body["evaluacion"].keys() == {
        "input",
        "actual_output",
        "retrieval_context",
        "tools_called",
    }
    assert body["metadata"].keys() == {
        "num_interacciones",
        "agentes_invocados",
        "tokens",
        "tokens_por_agente",
        "latencia_ms",
        "estado",
    }
    assert body["metadata"]["estado"] == "ok"


def test_tokens_total_debe_sumar_todos_los_agentes():
    """Requisito obligatorio de ADL: no basta con contar el orquestador."""
    with pytest.raises(ValidationError):
        _metadata(tokens=TokenCount(input=60, output=10, total=70))


# -- operacion ---------------------------------------------------------------


def test_health_esquema_y_ok_en_stub():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "stub"
    assert body["status"] in ("ok", "degraded", "down")
    assert isinstance(body["tools_registered"], list)
    assert isinstance(body["max_iterations"], int)
    assert isinstance(body["warnings"], list)


def test_usage_esquema_valido():
    resp = client.get("/usage")
    assert resp.status_code == 200
    body = resp.json()
    assert {"requests", "llm_calls", "input_tokens", "output_tokens", "trace_count"} == body.keys()
