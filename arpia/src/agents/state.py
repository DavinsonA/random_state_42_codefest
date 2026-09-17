"""Estado compartido del grafo agentico.

Regla de diseño: si un campo no lo lee ningun nodo ni ninguna arista
condicional, no pertenece al estado.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """Estado del grafo.

    Campos:
        messages: historial de la conversacion (reductor `add_messages`).
        question: consulta original del usuario, sin modificar.
        queries: consultas ya lanzadas a herramientas, para no repetirlas.
        evidence: fragmentos recuperados, con su procedencia.
        turns: contador de vueltas del bucle. Lo lee la arista condicional
            para cortar la ejecucion (AGENTS.md §8).
        answer: respuesta final redactada.
    """

    messages: Annotated[list, add_messages]
    question: str
    queries: Annotated[list[str], operator.add]
    evidence: Annotated[list[dict[str, Any]], operator.add]
    turns: Annotated[int, operator.add]
    answer: str
