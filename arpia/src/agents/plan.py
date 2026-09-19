"""El plan de un turno: que agentes se invocan y con que parametros.

Esquema cerrado a proposito. El orquestador no devuelve texto libre que luego
alguien interpreta: devuelve UNA estructura validada, y lo que no encaje en ella
no se ejecuta. Esa es la diferencia entre delegar y conversar.

Por que un plan y no un bucle ReAct: el bucle hace un numero impredecible de
llamadas al modelo —entre tres y siete por pregunta, sin cota util— y el Bloque
B de `RETO.md` normaliza la eficiencia CONTRA los otros equipos. Un plan unico
fija el coste del turno en dos llamadas: planificar y redactar.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.api.contracts import Fenomeno, GroupBy

#: Agentes que el orquestador puede invocar. Coinciden con los ids de
#: `agent_card.json`: lo que no esta en la card no se puede planificar.
AgenteEjecutor = Literal["agente_documental", "agente_analitico", "agente_visualizador"]

#: Tope de pasos por plan. Sin tope, un modelo que se entusiasma convierte una
#: pregunta en ocho delegaciones y el turno cuesta ocho veces lo que debia.
MAX_PASOS = 3

#: Replanificaciones permitidas por turno. UNA. Si tras la segunda pasada sigue
#: sin haber evidencia, la respuesta honesta es decir que no la hay.
MAX_REPLANES = 1


class Paso(BaseModel):
    """Una delegacion a un agente especializado."""

    model_config = ConfigDict(extra="forbid")

    agente: AgenteEjecutor
    consulta: str = Field(
        description="Una sola idea. Para comparar dos temas, dos pasos separados.",
        max_length=500,
    )
    fenomeno: Fenomeno | None = Field(
        None, description="Filtro por fenomeno si la pregunta lo acota. None = los tres."
    )
    group_by: GroupBy | None = Field(
        None,
        description=(
            "Solo para `agente_analitico`: por que dimension agrupar el conteo. "
            "Una de: fenomeno, organizacion, fuente, formato, anio."
        ),
    )


class Plan(BaseModel):
    """Lo que el orquestador decide en su unica llamada al modelo."""

    model_config = ConfigDict(extra="forbid")

    razonamiento: str = Field(
        "",
        description="Una frase: por que estos agentes. Va a la traza, no al usuario.",
        max_length=400,
    )
    pasos: list[Paso] = Field(default_factory=list, max_length=MAX_PASOS)
    paralelo: bool = Field(
        True,
        description=(
            "True si los pasos son independientes entre si. El documental y el "
            "visualizador casi siempre lo son: uno busca texto y el otro decide "
            "una vista, y ninguno necesita la salida del otro."
        ),
    )

    @property
    def agentes(self) -> list[str]:
        """Ids invocados, sin repetir, en orden de aparicion."""
        vistos: list[str] = []
        for paso in self.pasos:
            if paso.agente not in vistos:
                vistos.append(paso.agente)
        return vistos


def plan_de_respaldo(pregunta: str) -> Plan:
    """Plan determinista para cuando el modelo no devuelve uno valido.

    No es un caso raro que haya que tolerar: es la garantia de que un fallo del
    gateway o una salida malformada degraden a una busqueda documental util en
    vez de a una disculpa. Cuesta cero tokens.
    """
    return Plan(
        razonamiento="plan de respaldo: el orquestador no produjo un plan valido",
        pasos=[Paso(agente="agente_documental", consulta=pregunta)],
        paralelo=False,
    )
