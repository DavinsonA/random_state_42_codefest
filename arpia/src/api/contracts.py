"""Esquemas Pydantic de la API. ÚNICO lugar donde se definen.

`src/api/main.py` importa de aquí, nunca declara un modelo propio.

Congelado (no cambia sin autorización del arquitecto, ver
`docs/architecture.md` § Romper un contrato congelado):
- `ResponseEnvelope`: campos comunes a toda respuesta.
- `HealthResponse`, `UsageResponse`, `TraceSpan`/`TraceModel`.
- Invariante de error: ningún endpoint devuelve 500 por un fallo de
  dependencia externa (gateway, índice). Se responde 200 con `warnings`
  poblado y el contenido vacío o degradado.

No congelado:
- `AnalyzePayload` y `RetrievePayload`: dependen del reto, se redefinen
  el 18 de septiembre.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0"

# -- envoltura congelada ---------------------------------------------------


class ResponseEnvelope(BaseModel):
    """Campos presentes en toda respuesta de la API, sin excepción."""

    schema_version: str = SCHEMA_VERSION
    mode: str
    elapsed_ms: float
    warnings: list[str] = Field(default_factory=list)


class HealthResponse(ResponseEnvelope):
    status: str
    version: str
    max_iterations: int
    index_loaded: bool
    gateway_reachable: bool
    tools_registered: list[str]


class UsageResponse(ResponseEnvelope):
    requests: int
    llm_calls: int
    input_tokens: int
    output_tokens: int
    trace_count: int


class TraceSpan(BaseModel):
    span_id: str
    parent_id: str | None
    type: str
    name: str
    input: Any
    output: Any
    start_ms: float
    end_ms: float


class TraceModel(BaseModel):
    """Traza jerárquica de la trayectoria, en formato consumible por DeepEval."""

    trace_id: str
    spans: list[TraceSpan]


# -- payloads de negocio: NO congelados, se redefinen el 18 ---------------


class AnalyzeRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Consulta en lenguaje natural")
    top_k: int = Field(8, ge=1, le=50)


class Evidence(BaseModel):
    rank: int
    doc_id: str
    chunk_id: str
    text: str
    score: float


class Fragment(BaseModel):
    rank: int
    chunk_id: str
    doc_id: str
    text: str
    score: float


class AnalyzePayload(BaseModel):
    """Payload de negocio de `/analyze`. SE REDEFINE EL 18 al conocer el reto.

    Solo la forma de este modelo cambia con el reto; `ResponseEnvelope` no.
    """

    query: str
    answer: str
    evidence: list[Evidence]
    trace: TraceModel
    tokens_used: dict[str, int]


class AnalyzeResponse(ResponseEnvelope, AnalyzePayload):
    pass


class RetrievePayload(BaseModel):
    """Payload de negocio de `/retrieve`. SE REDEFINE EL 18 al conocer el reto."""

    query: str
    documents: list[str]
    fragments: list[Fragment]


class RetrieveResponse(ResponseEnvelope, RetrievePayload):
    pass
