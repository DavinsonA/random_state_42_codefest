"""App dummy para validar la cadena GitHub -> Coolify -> URL publica.

Sin base de datos, sin modelo, sin indice, sin variables de entorno
obligatorias. Debe arrancar en cualquier parte. Si esto no despliega, el
problema es Coolify o su configuracion, no el aplicativo real.
"""

from __future__ import annotations

import os

from fastapi import FastAPI

app = FastAPI(title="deploy-test")


@app.get("/")
def root() -> dict:
    return {
        "status": "ok",
        "service": "deploy-test",
        "commit": os.getenv("COMMIT_SHA", "unknown"),
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
