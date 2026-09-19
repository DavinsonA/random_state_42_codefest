"""Los estaticos se revalidan: un despliegue nuevo no puede quedar tapado por modulos JS en cache."""

from __future__ import annotations

import os

os.environ.setdefault("ARPIA_MODE", "stub")

from fastapi.testclient import TestClient  # noqa: E402

from src.api.main import app  # noqa: E402

client = TestClient(app)


def test_los_modulos_js_y_css_se_revalidan():
    for ruta in ("/js/viewspec.js", "/css/tablero.css"):
        r = client.get(ruta)
        assert r.status_code == 200 and r.headers["cache-control"] == "no-cache", ruta


def test_la_pagina_de_cada_dominio_se_revalida():
    assert (
        client.get("/", headers={"host": "dashboard.localhost"}).headers["cache-control"]
        == "no-cache"
    )
    assert (
        client.get("/", headers={"host": "agent.localhost"}).headers["cache-control"] == "no-cache"
    )


def test_la_api_no_toca_la_cache():
    assert "cache-control" not in client.get("/health").headers
    assert "cache-control" not in client.get("/api/components").headers
