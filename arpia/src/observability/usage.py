"""Contabilidad de tokens consumidos en el gateway.

Lee UNICAMENTE lo que el gateway devuelve en cada respuesta del LLM
(`usage_metadata` / `response_metadata["token_usage"]`). No estima ni inventa
precios ni cifras: el dashboard de LiteLLM es la fuente de verdad de costo
real y no es autorreportado, asi que este modulo existe para contrastar
contra el, no para reemplazarlo.
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass
from typing import Any


@dataclass
class UsageRecord:
    """Acumulador de tokens de entrada/salida y numero de llamadas al modelo."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    calls: int = 0

    def add(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_tokens += input_tokens + output_tokens
        self.calls += 1

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
    """Reinicia el acumulador de la request actual. Llamar al entrar a `/analyze`."""
    global _request_count
    _request_count += 1
    _current_request.set(UsageRecord())


def request_count() -> int:
    """Numero de requests procesadas por el proceso (contrato `/usage`)."""
    return _request_count


def record_usage(usage: dict[str, Any] | None) -> None:
    """Registra el consumo de una llamada al gateway, si trajo datos de uso.

    `usage` es el dict crudo que expone el proveedor: `AIMessage.usage_metadata`
    (`input_tokens` / `output_tokens`) o `response_metadata["token_usage"]`
    (`prompt_tokens` / `completion_tokens`). Si no trae nada reconocible, no
    hace nada — no se inventan cifras que el gateway no devolvio.
    """
    if not usage:
        return
    input_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
    if not input_tokens and not output_tokens:
        return
    _session.add(input_tokens, output_tokens)
    record = _current_request.get()
    if record is not None:
        record.add(input_tokens, output_tokens)


def request_usage() -> dict[str, int]:
    """Tokens consumidos durante la request actual."""
    record = _current_request.get()
    return record.to_dict() if record else UsageRecord().to_dict()


def usage_summary() -> dict[str, int]:
    """Consumo acumulado de toda la sesion del proceso (todas las requests)."""
    return _session.to_dict()
