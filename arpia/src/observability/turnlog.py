"""Registro de lo que ocurrio en UN turno de chat, para el bloque `evaluacion`.

ADL pide, por cada respuesta, las tools llamadas (con argumentos y salida) y
los fragmentos recuperados. Esos datos deben ser del turno actual, nunca de
uno anterior de la misma sesion, ni de otra request concurrente: por eso
viven en un `ContextVar` con un objeto mutable (los threads de LangGraph
comparten el objeto aunque copien el contexto).
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass, field
from typing import Any

MAX_OUTPUT_CHARS = 1500


@dataclass
class TurnLog:
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    retrieval_context: list[str] = field(default_factory=list)


_current: contextvars.ContextVar[TurnLog | None] = contextvars.ContextVar(
    "_current_turn", default=None
)


def start_turn() -> None:
    """Abre un registro vacio. Llamar una vez al entrar a `/chat`."""
    _current.set(TurnLog())


def record_tool_call(name: str, input_parameters: dict[str, Any], output: str) -> None:
    """Registra una invocacion de tool. Sin turno activo, no hace nada."""
    log = _current.get()
    if log is not None:
        log.tool_calls.append(
            {
                "name": name,
                "input_parameters": input_parameters,
                "output": output[:MAX_OUTPUT_CHARS],
            }
        )


def add_context(chunks: list[str]) -> None:
    """Agrega fragmentos recuperados (texto tal cual se le dio al modelo)."""
    log = _current.get()
    if log is not None:
        log.retrieval_context.extend(chunks)


def tool_calls() -> list[dict[str, Any]]:
    log = _current.get()
    return list(log.tool_calls) if log else []


def retrieval_context() -> list[str]:
    log = _current.get()
    return list(log.retrieval_context) if log else []
