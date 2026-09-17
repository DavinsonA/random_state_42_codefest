"""Traza jerarquica de spans, consumible por un evaluador externo (DeepEval).

DeepEval mide trayectoria, no solo respuesta final: que se llamo, con que
argumentos, en que orden, cuantas iteraciones. Un span es la unidad minima de
esa trayectoria. La jerarquia (`parent_id`) permite reconstruir el arbol de
ejecucion de una request completa.

Ambito por request: `start_trace()` se llama una vez al entrar a un endpoint
HTTP y crea un `trace_id` nuevo. Usa `contextvars` para que requests
concurrentes (FastAPI las corre en threads separados) no mezclen spans.
"""

from __future__ import annotations

import contextvars
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

SpanType = Literal["llm", "tool", "retrieval"]


@dataclass
class Span:
    """Un nodo de la traza: una llamada con su entrada, salida y duracion."""

    span_id: str
    parent_id: str | None
    type: SpanType
    name: str
    input: Any
    output: Any
    start_ms: float
    end_ms: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "type": self.type,
            "name": self.name,
            "input": self.input,
            "output": self.output,
            "start_ms": round(self.start_ms, 3),
            "end_ms": round(self.end_ms, 3),
        }


@dataclass
class Trace:
    """Traza completa de una request: un `trace_id` y sus spans."""

    trace_id: str
    spans: list[Span] = field(default_factory=list)

    def to_spans(self) -> list[dict[str, Any]]:
        return [s.to_dict() for s in self.spans]


_current_trace: contextvars.ContextVar[Trace | None] = contextvars.ContextVar(
    "_current_trace", default=None
)
_current_parent: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "_current_parent", default=None
)
_trace_count = 0


def start_trace() -> str:
    """Inicia una traza nueva. Llamar una vez al entrar a un endpoint HTTP."""
    global _trace_count
    _trace_count += 1
    trace = Trace(trace_id=uuid.uuid4().hex)
    _current_trace.set(trace)
    _current_parent.set(None)
    return trace.trace_id


def trace_count() -> int:
    """Numero de trazas iniciadas por el proceso (contrato `/usage`)."""
    return _trace_count


def current_trace_id() -> str | None:
    trace = _current_trace.get()
    return trace.trace_id if trace else None


def to_spans() -> list[dict[str, Any]]:
    """Spans de la traza activa, en formato serializable."""
    trace = _current_trace.get()
    return trace.to_spans() if trace else []


class span:  # noqa: N801 - nombre en minuscula deliberado, uso como `with tracing.span(...)`
    """Context manager que registra un span en la traza activa.

    Si no hay traza activa (por ejemplo, codigo llamado fuera de un request
    HTTP, como en pruebas unitarias de un nodo aislado), no falla: solo no
    registra nada. Un span nunca debe propagar una excepcion adicional.
    """

    def __init__(self, span_type: SpanType, name: str, input: Any = None) -> None:  # noqa: A002
        self.type = span_type
        self.name = name
        self.input = input
        self.output: Any = None
        self._span_id = uuid.uuid4().hex
        self._parent_id: str | None = None
        self._token: contextvars.Token | None = None
        self._start = 0.0

    def set_output(self, output: Any) -> None:
        self.output = output

    def __enter__(self) -> span:
        self._start = time.perf_counter() * 1000
        self._parent_id = _current_parent.get()
        self._token = _current_parent.set(self._span_id)
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        end = time.perf_counter() * 1000
        trace = _current_trace.get()
        if trace is not None:
            trace.spans.append(
                Span(
                    span_id=self._span_id,
                    parent_id=self._parent_id,
                    type=self.type,
                    name=self.name,
                    input=self.input,
                    output=self.output,
                    start_ms=self._start,
                    end_ms=end,
                )
            )
        if self._token is not None:
            _current_parent.reset(self._token)
        return False
