"""Esquemas Pydantic de la API. ÚNICO lugar donde se definen.

`src/api/main.py` importa de aquí, nunca declara un modelo propio.

Contrato del Reto 1 (especificación técnica ADL, Etapa 2, §2.4): la respuesta de
`POST /chat` sigue EXACTAMENTE el JSON de tres bloques (`respuesta`,
`evaluacion`, `metadata`). El evaluador de ADL parsea esos nombres tal cual:
no renombrar campos ni cambiar tipos.

Invariante: ningún endpoint devuelve 500 por un fallo de dependencia externa
(Bedrock, índice). Se responde 200 y el fallo se reporta en `metadata.estado`.
"""

from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

# -- POST /chat: entrada ---------------------------------------------------


class ChatRequest(BaseModel):
    """Cuerpo JSON de `POST /chat`.

    Tolerante a propósito: la especificación de ADL solo dice "texto plano o
    JSON" y no fija los nombres de campo, así que se aceptan varios alias y se
    ignora lo desconocido. Un 422 aquí puntuaría cero en cada pregunta.
    """

    model_config = ConfigDict(extra="ignore")

    texto: str = Field(
        ...,
        min_length=1,
        validation_alias=AliasChoices("texto", "pregunta", "query", "input", "message", "question"),
        description="Lo que escribió el usuario.",
    )
    sesion_id: str | None = Field(
        None,
        validation_alias=AliasChoices("sesion_id", "session_id", "thread_id"),
        description="Opcional. Clave de la memoria del grafo (ver src/api/session.py).",
    )


# -- POST /chat: salida (formato ADL §2.4) ---------------------------------


class ToolCall(BaseModel):
    name: str
    input_parameters: dict[str, Any]
    output: str


class Evaluacion(BaseModel):
    """Insumo de las métricas de calidad (Bloque A)."""

    input: str
    actual_output: str
    retrieval_context: list[str] = Field(
        default_factory=list,
        description="Chunks recuperados en ESTE turno, textuales. Vacío si no hubo recuperación.",
    )
    tools_called: list[ToolCall] = Field(default_factory=list)


class TokenCount(BaseModel):
    input: int
    output: int
    total: int


class TokensPorAgente(TokenCount):
    agente: str = Field(description="Debe coincidir con un id de la agent card.")
    modelo: str


class Metadata(BaseModel):
    """Insumo de las métricas de eficiencia (Bloque B)."""

    num_interacciones: int = Field(description="Llamadas a modelos ejecutadas en el turno.")
    agentes_invocados: list[str]
    tokens: TokenCount
    tokens_por_agente: list[TokensPorAgente] = Field(default_factory=list)
    latencia_ms: int = Field(description="De principio a fin de toda la solución.")
    estado: str = Field("ok", description='"ok" o un código de error.')

    @model_validator(mode="after")
    def _tokens_suman_todos_los_agentes(self) -> Metadata:
        """Requisito obligatorio de ADL: `tokens.total` cubre TODOS los modelos."""
        if self.tokens_por_agente:
            suma = sum(a.total for a in self.tokens_por_agente)
            if self.tokens.total != suma:
                raise ValueError(f"tokens.total={self.tokens.total} != suma por agente={suma}")
        return self


class ChatResponse(BaseModel):
    respuesta: str
    evaluacion: Evaluacion
    metadata: Metadata


# -- GET /topics (uso interno del frontend; no lo evalúa ADL) ---------------


class Topic(BaseModel):
    id: str
    nombre: str
    descripcion: str
    num_documentos: int | None = Field(
        None, description="Conteo real sobre la metadata; None si no se calculó."
    )
    preguntas_ejemplo: list[str] = Field(default_factory=list)


class TopicsResponse(BaseModel):
    topics: list[Topic]


# -- operación -------------------------------------------------------------


class HealthResponse(BaseModel):
    """`status`: "ok" | "degraded" | "down" (nunca solo boolean)."""

    status: str
    version: str
    mode: str
    max_iterations: int
    index_loaded: bool
    gateway_reachable: bool
    tools_registered: list[str]
    warnings: list[str] = Field(default_factory=list)


class UsageResponse(BaseModel):
    """Consumo observado por el propio proceso; sirve para vigilar la bolsa"""

    requests: int
    llm_calls: int
    input_tokens: int
    output_tokens: int
    trace_count: int
