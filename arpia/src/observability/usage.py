"""Contabilidad de tokens consumidos en el proveedor de modelos.

Lee UNICAMENTE lo que el proveedor devuelve en cada respuesta del LLM
(`usage_metadata` / `response_metadata["token_usage"]`). No estima ni inventa
cifras. Cada equipo tiene una bolsa de $100 USD: este modulo existe para vigilar
el consumo propio y para llenar `metadata.tokens_por_agente` del formato ADL.
"""

from __future__ import annotations

import contextvars
import threading
from dataclasses import dataclass, field
from typing import Any

_lock = threading.Lock()


@dataclass
class UsageRecord:
    """Acumulador de tokens y llamadas, con desglose por agente."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    calls: int = 0
    by_agent: dict[str, dict[str, Any]] = field(default_factory=dict)

    def add(self, input_tokens: int, output_tokens: int, agent: str = "", model: str = "") -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_tokens += input_tokens + output_tokens
        self.calls += 1
        if agent:
            row = self.by_agent.setdefault(
                agent, {"agente": agent, "modelo": model, "input": 0, "output": 0, "total": 0}
            )
            row["input"] += input_tokens
            row["output"] += output_tokens
            row["total"] += input_tokens + output_tokens

    def to_dict(self) -> dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "calls": self.calls,
        }


_session = UsageRecord()
_request_count = 0
_current_request: contextvars.ContextVar[UsageRecord | None] = contextvars.ContextVar(
    "_current_request", default=None
)


def start_request() -> None:
    """Reinicia el acumulador de la request actual. Llamar al entrar a `/chat`."""
    global _request_count
    _request_count += 1
    _current_request.set(UsageRecord())


def request_count() -> int:
    """Numero de requests procesadas por el proceso (contrato `/usage`)."""
    return _request_count


def record_usage(usage: dict[str, Any] | None, agent: str = "", model: str = "") -> None:
    """Registra UNA llamada al modelo, atribuida a `agent`.

    `usage` es el dict crudo del proveedor: `AIMessage.usage_metadata`
    (`input_tokens` / `output_tokens`) o `response_metadata["token_usage"]`
    (`prompt_tokens` / `completion_tokens`). La llamada se cuenta siempre
    (alimenta `num_interacciones`); si no trae cifras reconocibles, los tokens
    quedan en 0 — no se inventan.
    """
    usage = usage or {}
    input_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
    record = _current_request.get()
    # Candado: los pasos de un plan paralelo suman desde hilos distintos sobre el
    # MISMO acumulador del turno, y `+=` sobre un entero no es atomico.
    with _lock:
        _session.add(input_tokens, output_tokens)
        if record is not None:
            record.add(input_tokens, output_tokens, agent, model)


def request_usage() -> dict[str, int]:
    """Tokens consumidos durante la request actual."""
    record = _current_request.get()
    return record.to_dict() if record else UsageRecord().to_dict()


def request_breakdown() -> list[dict[str, Any]]:
    """Desglose por agente de la request actual, en orden de primera invocacion."""
    record = _current_request.get()
    return [dict(row) for row in record.by_agent.values()] if record else []


def usage_summary() -> dict[str, int]:
    """Consumo acumulado de toda la sesion del proceso (todas las requests)."""
    return _session.to_dict()
