"""Estado compartido del grafo agentico.

Regla de diseno: si un campo no lo lee ningun nodo ni ninguna arista
condicional, no pertenece al estado.

**Que se persiste y que no.** Con checkpointer, el estado sobrevive entre turnos
de una misma sesion. Eso es deseable para `messages` —es la memoria de la
conversacion— y es un error para todo lo demas. Los campos del turno NO llevan
reductor acumulativo: se sobrescriben en cada vuelta.

Tres fallos concretos que esto corrige (documentados en `CONTRATO_GRAFO.md` y
verificados con un LLM falso):

1. `turns` con `operator.add` acumulaba entre turnos: al cuarto mensaje de una
   conversacion el tope de iteraciones ya estaba agotado y el agente dejaba de
   buscar sin decir por que.
2. `evidence` y `queries` igual: el turno 5 arrastraba la evidencia del turno 1
   y la citaba como si fuera de esta pregunta.
3. El historial conservaba los mensajes de herramientas de turnos anteriores:
   subia los tokens de cada turno (Bloque B) y contaminaba el
   `retrieval_context` que ADL mide en Faithfulness.
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """Estado del grafo.

    Campos persistentes entre turnos:
        messages: historial de la conversacion (reductor `add_messages`). Es lo
            unico que debe sobrevivir al turno.

    Campos del turno (se sobrescriben en cada vuelta, sin reductor):
        question: consulta del usuario, ya saneada por el guardian.
        plan: plan producido por el orquestador, serializado.
        evidence: fragmentos recuperados en ESTE turno, con su procedencia.
        findings: salida de cada ejecutor, indexada por id de agente.
        view_spec: vista emitida por el visualizador, si la hubo.
        replans: replanificaciones ya gastadas. Lo lee la arista condicional
            para cortar (AGENTS.md §8).
        suficiente: si los ejecutores reportaron evidencia bastante.
        answer: respuesta final redactada.
    """

    messages: Annotated[list, add_messages]

    question: str
    plan: dict[str, Any]
    evidence: list[dict[str, Any]]
    findings: dict[str, str]
    view_spec: dict[str, Any] | None
    replans: int
    suficiente: bool
    answer: str


#: Valores con los que `begin` reinicia el turno. Explicito y en un solo lugar:
#: un campo que se olvide aqui es un campo que filtra datos del turno anterior.
TURNO_LIMPIO: dict[str, Any] = {
    "plan": {},
    "evidence": [],
    "findings": {},
    "view_spec": None,
    "replans": 0,
    "suficiente": False,
    "answer": "",
}
