"""Generadores de respuestas simuladas para `ARPIA_MODE=stub`.

El objetivo es poder desplegar en Coolify y validar el contrato HTTP antes de
tener indice, gateway o reto definido. Las respuestas son deterministas por
consulta (mismo input -> mismo output) y con forma identica a la de modo
`live`, pero NUNCA tocan `src.retrieval` ni el gateway del evento.
"""

from __future__ import annotations

import hashlib
from typing import Any


def _seed(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)


def stub_fragments(query: str, k: int) -> list[dict[str, Any]]:
    """Fragmentos simulados, con la misma forma que `Hit` en `src/retrieval/index.py`."""
    n = max(1, min(k, 5))
    seed = _seed(query)
    return [
        {
            "rank": i,
            "chunk_id": f"stub-chunk-{seed % 1000}-{i}",
            "doc_id": f"stub-doc-{(seed + i) % 100}",
            "text": (
                f"[dato simulado] fragmento {i} generado en modo stub para la "
                f"consulta {query!r}. No proviene de un indice real."
            ),
            "score": round(max(0.0, 0.95 - 0.07 * i), 3),
        }
        for i in range(1, n + 1)
    ]


def stub_retrieve(query: str, k: int) -> dict[str, Any]:
    """Payload simulado para `/retrieve`."""
    fragments = stub_fragments(query, k)
    documents = sorted({f["doc_id"] for f in fragments})[:3]
    return {"query": query, "documents": documents, "fragments": fragments, "mode": "stub"}


def stub_analyze(query: str, k: int) -> dict[str, Any]:
    """Payload simulado para `/analyze`."""
    fragments = stub_fragments(query, min(k, 3))
    answer = (
        f"[respuesta simulada, modo stub] no hay LLM ni indice real conectados; "
        f"esta es una respuesta con forma valida para la consulta {query!r}."
    )
    return {
        "answer": answer,
        "evidence": fragments,
        "warnings": ["modo stub activo: respuesta simulada, sin recuperacion ni LLM real"],
        "mode": "stub",
    }
