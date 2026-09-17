"""Pruebas de contrato de la API, en modo stub.

Protegen dos invariantes de `docs/architecture.md`: el jurado consume la
aplicacion desplegada, no el repositorio, asi que el contrato HTTP debe
cumplirse siempre; y `/analyze` nunca puede devolver 500, porque un fallo
interno debe degradarse, no tumbar la respuesta.

Corren en modo stub a proposito: no requieren indice, credenciales ni
gateway, igual que el despliegue inicial en Coolify.
"""

from __future__ import annotations

import os

os.environ.setdefault("ARPIA_MODE", "stub")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

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


def test_health_esquema_y_ok_en_stub():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "stub"
    assert body["status"] in ("ok", "degraded")
    assert isinstance(body["tools_registered"], list)
    assert isinstance(body["max_iterations"], int)


def test_analyze_esquema_valido_en_stub():
    resp = client.post("/analyze", json={"query": "satelites en orbita baja", "top_k": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "stub"
    assert body["query"] == "satelites en orbita baja"
    assert isinstance(body["answer"], str) and body["answer"]
    assert isinstance(body["evidence"], list) and body["evidence"]
    for ev in body["evidence"]:
        assert {"rank", "doc_id", "chunk_id", "text", "score"} <= ev.keys()
    assert isinstance(body["warnings"], list)
    assert isinstance(body["tokens_used"], dict)
    assert {"input_tokens", "output_tokens", "total_tokens", "calls"} <= body["tokens_used"].keys()
    assert isinstance(body["elapsed_ms"], (int, float))


def test_analyze_nunca_devuelve_500_sin_gateway():
    """Ni siquiera en modo live, sin LLM_BASE_URL/LLM_API_KEY configurados,
    /analyze debe degradar en vez de devolver un error de servidor."""
    import src.config as config

    os.environ["ARPIA_MODE"] = "live"
    os.environ.pop("LLM_BASE_URL", None)
    os.environ.pop("LLM_API_KEY", None)
    config.get_settings.cache_clear()
    try:
        resp = client.post("/analyze", json={"query": "sin gateway configurado"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] == "live"
        assert any("LLM_BASE_URL" in w or "gateway" in w.lower() for w in body["warnings"])
    finally:
        os.environ["ARPIA_MODE"] = "stub"
        config.get_settings.cache_clear()


def test_retrieve_esquema_valido_en_stub():
    resp = client.post("/retrieve", json={"query": "zona costera", "top_k": 4})
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "stub"
    assert body["query"] == "zona costera"
    assert isinstance(body["documents"], list)
    assert isinstance(body["fragments"], list) and body["fragments"]
    for frag in body["fragments"]:
        assert {"rank", "chunk_id", "doc_id", "text", "score"} <= frag.keys()


def test_usage_esquema_valido():
    resp = client.get("/usage")
    assert resp.status_code == 200
    body = resp.json()
    assert {"requests", "llm_calls", "input_tokens", "output_tokens", "trace_count"} <= body.keys()


def test_analyze_incluye_traza_con_spans_y_trace_id():
    resp = client.post("/analyze", json={"query": "cobertura radar"})
    assert resp.status_code == 200
    trace = resp.json()["trace"]
    assert trace["trace_id"]
    assert isinstance(trace["spans"], list) and len(trace["spans"]) >= 1
    span = trace["spans"][0]
    assert {"span_id", "parent_id", "type", "name", "input", "output", "start_ms", "end_ms"} <= (
        span.keys()
    )
    assert span["type"] in ("llm", "tool", "retrieval")
