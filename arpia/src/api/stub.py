"""Respuestas simuladas para `ARPIA_MODE=stub`.

El objetivo es poder desplegar en Coolify y validar el contrato HTTP antes de
tener indice o credenciales. Las respuestas son deterministas por consulta y
con la misma forma que en modo `live`, pero NUNCA tocan `src.retrieval` ni el
proveedor de modelos.
"""

from __future__ import annotations

import hashlib


def _seed(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)


def stub_fragments(query: str, k: int = 3) -> list[str]:
    """Fragmentos simulados, en el formato de `retrieval_context`."""
    seed = _seed(query)
    return [
        f"(stub-doc-{(seed + i) % 100}) [dato simulado] fragmento {i} generado en modo "
        f"stub para la consulta {query!r}. No proviene de un indice real."
        for i in range(1, max(1, min(k, 5)) + 1)
    ]


def stub_answer(query: str) -> str:
    return (
        "[respuesta simulada, modo stub] no hay modelo ni indice real conectados; "
        f"esta es una respuesta con forma valida para la consulta {query!r}."
    )
