"""Registro de tools del agente.

Una tool = una funcion con un proposito claro. El docstring ES el prompt que
lee el modelo para decidir si invocarla: describe cuando usarla, cuando NO, y
la forma exacta de los argumentos (AGENTS.md §8).

Regla dura: una tool nunca lanza una excepcion hacia el grafo. Ante un fallo
devuelve un texto de error legible, para que el agente pueda decidir que hacer.
"""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from src.config import get_logger
from src.observability import tracing

log = get_logger(__name__)


@dataclass
class ToolCall:
    """Registro de una invocacion, para trazabilidad y costo."""

    name: str
    args: dict[str, Any]
    duration_ms: float
    ok: bool
    error: str = ""


@dataclass
class ToolRegistry:
    """Coleccion de tools disponibles para el agente."""

    _tools: dict[str, Callable] = field(default_factory=dict)
    calls: list[ToolCall] = field(default_factory=list)

    def register(
        self, fn: Callable | None = None, *, span_type: tracing.SpanType = "tool"
    ) -> Callable:
        """Decorador que registra una tool y la envuelve con traza y captura.

        Uso normal: `@registry.register`. Para tools de recuperacion, que
        DeepEval quiere distinguir de otras tools en la trayectoria, usar
        `@registry.register(span_type="retrieval")`.
        """
        if fn is None:
            return functools.partial(self.register, span_type=span_type)

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            call_input = kwargs or {"positional": [str(a)[:80] for a in args]}
            with tracing.span(span_type, fn.__name__, input=call_input) as sp:
                try:
                    result = fn(*args, **kwargs)
                    ok, error = True, ""
                    sp.set_output(str(result)[:2000])
                    return result
                except Exception as exc:  # noqa: BLE001 - frontera deliberada
                    ok, error = False, f"{type(exc).__name__}: {exc}"
                    log.warning("tool '%s' fallo: %s", fn.__name__, error)
                    message = f"[error en la herramienta '{fn.__name__}': {error}]"
                    sp.set_output(message)
                    return message
                finally:
                    self.calls.append(
                        ToolCall(
                            name=fn.__name__,
                            args=call_input,
                            duration_ms=(time.perf_counter() - start) * 1000,
                            ok=ok,
                            error=error,
                        )
                    )

        self._tools[fn.__name__] = wrapper
        return wrapper

    def get(self, name: str) -> Callable:
        if name not in self._tools:
            raise KeyError(f"tool '{name}' no registrada; disponibles: {sorted(self._tools)}")
        return self._tools[name]

    def all(self) -> list[Callable]:
        """Lista de tools, en el formato que consumen LangGraph / ADK."""
        return list(self._tools.values())

    def names(self) -> list[str]:
        return sorted(self._tools)

    def trace(self) -> list[dict[str, Any]]:
        """Traza de invocaciones de la ejecucion actual."""
        return [
            {
                "tool": c.name,
                "ms": round(c.duration_ms, 1),
                "ok": c.ok,
                **({"error": c.error} if c.error else {}),
            }
            for c in self.calls
        ]

    def reset(self) -> None:
        self.calls.clear()


registry = ToolRegistry()
