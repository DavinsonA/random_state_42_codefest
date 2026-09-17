"""Pruebas de la envoltura de respuesta congelada (`src/api/contracts.py`).

A diferencia de `test_contract.py` (payload de negocio, no congelado), este
archivo solo valida lo que `docs/architecture.md` marca como congelado:
`schema_version`, `mode`, `elapsed_ms`, `warnings` en toda respuesta, y la
forma exacta de `/health` y `/usage`. Corre en modo stub para no depender de
indice, credenciales ni gateway.
"""

from __future__ import annotations

import os

os.environ.setdefault("ARPIA_MODE", "stub")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from src.api.contracts import SCHEMA_VERSION  # noqa: E402
from src.api.main import app  # noqa: E402

client = TestClient(app)

ENVELOPE_KEYS = {"schema_version", "mode", "elapsed_ms", "warnings"}


@pytest.fixture(autouse=True)
def _stub_mode(monkeypatch):
    from src import config

    monkeypatch.setenv("ARPIA_MODE", "stub")
    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()


def _assert_envelope(body: dict) -> None:
    assert body.keys() >= ENVELOPE_KEYS
    assert body["schema_version"] == SCHEMA_VERSION
    assert body["mode"] in ("stub", "live")
    assert isinstance(body["elapsed_ms"], (int, float))
    assert isinstance(body["warnings"], list)


def test_health_cumple_la_envoltura():
    resp = client.get("/health")
    assert resp.status_code == 200
    _assert_envelope(resp.json())


def test_analyze_cumple_la_envoltura():
    resp = client.post("/analyze", json={"query": "cobertura radar"})
    assert resp.status_code == 200
    _assert_envelope(resp.json())


def test_retrieve_cumple_la_envoltura():
    resp = client.post("/retrieve", json={"query": "zona costera"})
    assert resp.status_code == 200
    _assert_envelope(resp.json())


def test_usage_cumple_la_envoltura_y_su_forma_congelada():
    resp = client.get("/usage")
    assert resp.status_code == 200
    body = resp.json()
    _assert_envelope(body)
    assert {"requests", "llm_calls", "input_tokens", "output_tokens", "trace_count"} <= body.keys()
    assert all(isinstance(body[k], int) for k in ("requests", "llm_calls", "trace_count"))


def test_health_cumple_su_forma_congelada():
    body = client.get("/health").json()
    assert {
        "status",
        "index_loaded",
        "gateway_reachable",
        "tools_registered",
        "version",
        "max_iterations",
    } <= body.keys()
    assert body["status"] in ("ok", "degraded", "down")


def test_analyze_nunca_devuelve_500_y_degrada_con_warnings():
    """Invariante congelada: fallo de dependencia externa -> 200 + warnings, nunca 500."""
    import src.config as config

    os.environ["ARPIA_MODE"] = "live"
    os.environ.pop("LLM_BASE_URL", None)
    os.environ.pop("LLM_API_KEY", None)
    config.get_settings.cache_clear()
    try:
        resp = client.post("/analyze", json={"query": "sin gateway configurado"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["warnings"], "una degradacion debe poblar warnings"
    finally:
        os.environ["ARPIA_MODE"] = "stub"
        config.get_settings.cache_clear()
