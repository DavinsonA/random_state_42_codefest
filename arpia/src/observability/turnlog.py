"""Registro de lo que ocurrio en UN turno de chat, para el bloque `evaluacion`.

ADL pide, por cada respuesta, las tools llamadas (con argumentos y salida) y
los fragmentos recuperados. Esos datos deben ser del turno actual, nunca de
uno anterior de la misma sesion, ni de otra request concurrente: por eso
viven en un `ContextVar` con un objeto mutable (los threads de LangGraph
comparten el objeto aunque copien el contexto).
"""

from __future__ import annotations

import contextvars
import threading
from dataclasses import dataclass, field
from typing import Any

MAX_OUTPUT_CHARS = 1500

_lock = threading.Lock()


@dataclass
class TurnLog:
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    retrieval_context: list[str] = field(default_factory=list)
    #: Agentes que intervinieron en el turno, en orden de primera aparicion.
    #: Separado del consumo de tokens a proposito: el agente analitico gasta
    #: CERO por diseno, y derivar la lista del desglose de tokens lo dejaba
    #: invisible en `agentes_invocados` pese a haber trabajado.
    agentes: list[str] = field(default_factory=list)
    #: Procedencia estructurada de cada fragmento: `RETO.md` exige poder
    #: rastrear todo dato mostrado hasta su `doc_id` y su `chunk_id`.
    #: `retrieval_context` es el texto que vio el modelo; esto es de donde salio.
    citations: list[dict[str, Any]] = field(default_factory=list)
    #: Motivo por el que este turno no debe guardarse en el cache semantico
    #: (vacio = se puede cachear). Un turno degradado sigue con `estado: ok`, y
    #: cachearlo congelaria la respuesta mala hasta reiniciar el proceso.
    no_cacheable: str = ""


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


def record_agent(agente: str) -> None:
    """Anota que un agente intervino, gaste tokens o no."""
    log = _current.get()
    if log is not None and agente and agente not in log.agentes:
        log.agentes.append(agente)


def marcar_no_cacheable(motivo: str) -> None:
    """Impide que el turno se guarde en el cache. Sin turno activo, no hace nada."""
    log = _current.get()
    if log is not None and not log.no_cacheable:
        log.no_cacheable = motivo


def no_cacheable() -> str:
    """Motivo por el que el turno no se cachea; cadena vacia si se puede."""
    log = _current.get()
    return log.no_cacheable if log else ""


def agentes() -> list[str]:
    log = _current.get()
    return list(log.agentes) if log else []


def add_citations(rows: list[dict[str, Any]]) -> None:
    """Registra la procedencia de los fragmentos recuperados.

    Cada fila lleva al menos `doc_id` y `chunk_id`. Se descartan los duplicados
    por `chunk_id`: el corpus tiene fragmentos repetidos entre documentos y
    citar dos veces el mismo no agrega evidencia, solo ruido.
    """
    log = _current.get()
    if log is None:
        return
    # Candado: los pasos de un plan paralelo llaman aqui desde hilos distintos y
    # la deduplicacion es "mirar y luego agregar", que no es atomico.
    with _lock:
        vistos = {c.get("chunk_id") for c in log.citations}
        for row in rows:
            if row.get("chunk_id") not in vistos:
                log.citations.append(row)
                vistos.add(row.get("chunk_id"))


def citations() -> list[dict[str, Any]]:
    log = _current.get()
    return list(log.citations) if log else []


def tool_calls() -> list[dict[str, Any]]:
    log = _current.get()
    return list(log.tool_calls) if log else []


def retrieval_context() -> list[str]:
    log = _current.get()
    return list(log.retrieval_context) if log else []
