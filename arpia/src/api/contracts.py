"""Esquemas Pydantic de la API. UNICO lugar donde se definen.

`src/api/main.py` importa de aqui, nunca declara un modelo propio.

Contrato del Reto 1 (especificacion tecnica ADL, Etapa 2, §2.4): la respuesta
de `POST /chat` lleva EXACTAMENTE los tres bloques `respuesta`, `evaluacion` y
`metadata`, con esos nombres y esos tipos. El evaluador los parsea tal cual.

Sobre los tres bloques se anaden campos propios (`mode`, `citations`,
`view_spec`): ADL exige que los tres esten, no prohibe que haya mas.
`mode` es el seguro contra el peor fallo posible del sabado — que el contenedor
arranque en `stub` durante la ventana de evaluacion y responda 200 con datos
simulados sin que nadie lo note (`RETO.md`: "no se aceptan datos simulados o
inventados en la version desplegada").

Invariante: ningun endpoint devuelve 500 ni 422 por un fallo de dependencia o
por una entrada rara. Se responde 200 y el fallo se reporta en
`metadata.estado`. Un 422 puntua cero en esa pregunta.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

# -- vocabulario cerrado ---------------------------------------------------
# Los `Literal` son la frontera de seguridad del agente visualizador: lo que no
# esta en estas listas no se puede emitir (`RETO.md` §Defensa, punto 6).

Fenomeno = Literal["F1", "F2", "F3"]

# El vocabulario esta podado a lo que la metadata del corpus soporta de verdad.
# El indice tiene OCHO campos —doc_id, chunk_id, fuente, formato, fenomeno,
# posicion, num_tokens, texto— y ni fecha, ni lugar, ni actor. Se retiraron
# `map`, `network`, `lugar`, `actor`, `mes` y `trimestre`: un agente que
# propone una vista que el tablero no puede poblar cuesta el 55% del Reto 2.
# Volver a anadirlos exige primero el dato, no al reves.
ChartType = Literal["timeline", "bar", "stacked_bar", "donut", "table", "kpi"]

# `organizacion` y `anio` son DERIVADAS, no inventadas (ver src/retrieval/enrich.py):
#   organizacion -> segundo nivel de la ruta `fuente` (CSIS_Aerospace, CSET_Georgetown...)
#   anio         -> ano en el nombre de archivo; cubre 622 de 1.826 documentos (34%)
GroupBy = Literal["fenomeno", "organizacion", "fuente", "formato", "anio"]

# Solo conteos y frecuencias. `RETO.md` prohibe presentar como medicion
# objetiva cualquier indice, score de riesgo o nivel de amenaza calculado
# ad-hoc: no existe metrica de "riesgo" en este vocabulario, y es deliberado.
# `conteo_menciones` tambien se retiro: no hay extraccion de entidades.
Metrica = Literal["conteo_documentos", "conteo_fragmentos"]

Mode = Literal["stub", "live"]

_ANIO = r"^\d{4}$"  # granularidad anual: es la unica que el corpus sostiene


# -- POST /chat: entrada ---------------------------------------------------


class ChatRequest(BaseModel):
    """Cuerpo JSON de `POST /chat`.

    Tolerante a proposito: la especificacion solo dice "texto plano o JSON" y
    no fija los nombres de campo, asi que se aceptan varios alias y se ignora
    lo desconocido. `texto` NO es obligatorio: un cuerpo vacio produce una
    respuesta cortes con 200, nunca un 422.
    """

    model_config = ConfigDict(extra="ignore")

    texto: str = Field(
        "",
        validation_alias=AliasChoices(
            "texto", "pregunta", "query", "input", "message", "question", "prompt"
        ),
        description="Lo que escribio el usuario.",
    )
    sesion_id: str | None = Field(
        None,
        validation_alias=AliasChoices("sesion_id", "session_id", "thread_id", "conversation_id"),
        description="Opcional. Hilo de la memoria conversacional (thread_id del checkpointer).",
    )


# -- POST /chat: salida (formato ADL §2.4) ---------------------------------


class ToolCall(BaseModel):
    """Una invocacion de herramienta, tal como la lee el evaluador."""

    name: str
    input_parameters: dict[str, Any] = Field(default_factory=dict)
    output: str


class Evaluacion(BaseModel):
    """Insumo de las metricas de calidad (40% del Reto 1).

    `faithfulness` se calcula CONTRA `retrieval_context`: si hubo recuperacion
    y este campo va vacio, se pierde el 30% del bloque mas pesado.
    """

    input: str
    actual_output: str
    retrieval_context: list[str] = Field(
        default_factory=list,
        description="Chunks recuperados en ESTE turno, textuales. Vacio si no hubo recuperacion.",
    )
    tools_called: list[ToolCall] = Field(default_factory=list)


class Tokens(BaseModel):
    """Consumo agregado del turno, sumando TODOS los modelos."""

    input: int = 0
    output: int = 0
    total: int = 0


class TokensPorAgente(Tokens):
    """Consumo desglosado. `agente` debe ser un id de la agent card."""

    agente: str
    modelo: str = ""


class Metadata(BaseModel):
    """Insumo de las metricas de eficiencia (20% del Reto 1, normalizado contra
    los demas equipos: menos es mejor)."""

    num_interacciones: int = Field(0, description="Llamadas a modelos ejecutadas en el turno.")
    agentes_invocados: list[str] = Field(default_factory=list)
    tokens: Tokens = Field(default_factory=Tokens)
    tokens_por_agente: list[TokensPorAgente] = Field(default_factory=list)
    latencia_ms: int = Field(0, description="Medida por nosotros, de extremo a extremo.")
    estado: str = Field("ok", description='"ok" o un codigo de degradacion.')

    @model_validator(mode="after")
    def _cuadrar_tokens(self) -> Metadata:
        """Fuerza `tokens` = suma de `tokens_por_agente` cuando hay desglose.

        ADL marca como inconsistencia reportar en `tokens.total` menos de lo que
        suma el desglose. Esto NO lanza: un descuadre aritmetico no puede
        convertirse en un 500 delante del evaluador. Se corrige y sigue, porque
        el desglose por agente es el dato con procedencia y el agregado es
        derivable de el.
        """
        if self.tokens_por_agente:
            self.tokens = Tokens(
                input=sum(a.input for a in self.tokens_por_agente),
                output=sum(a.output for a in self.tokens_por_agente),
                total=sum(a.total for a in self.tokens_por_agente),
            )
        return self


# -- campos propios sobre los tres bloques ---------------------------------


class Citation(BaseModel):
    """Procedencia de una afirmacion.

    `RETO.md` §Restricciones duras: todo dato mostrado debe rastrearse a su
    `doc_id` y su `chunk_id`. Este es el campo que el tablero usa para abrir la
    evidencia (`GET /api/evidence/{chunk_id}`).
    """

    doc_id: str
    chunk_id: str
    fuente: str | None = None
    fragmento: str = Field("", description="Texto citado, recortado.")


class ViewSpec(BaseModel):
    """Vista que el tablero debe renderizar.

    `extra="forbid"` + campos `Literal` = esquema cerrado. El agente
    visualizador nunca emite codigo ni SQL: solo puede elegir dentro de este
    vocabulario, y cualquier cosa fuera de el falla la validacion antes de
    llegar al frontend.

    Toda opcion de este esquema tiene datos reales detras. Si el tablero no
    puede renderizar una combinacion, el arreglo es quitarla de aqui, no
    ensenar al modelo a evitarla.
    """

    model_config = ConfigDict(extra="forbid")

    chart: ChartType
    metrica: Metrica = "conteo_documentos"
    fenomenos: list[Fenomeno] = Field(default_factory=list, description="Vacio = los tres.")
    desde: str | None = Field(None, pattern=_ANIO, description="Ano inclusive, YYYY.")
    hasta: str | None = Field(None, pattern=_ANIO, description="Ano inclusive, YYYY.")
    group_by: GroupBy | None = None
    titulo: str = ""
    nota: str = Field(
        "",
        description=(
            "Advertencia que el tablero DEBE mostrar junto a la vista. Obligatoria "
            "cuando la vista es temporal: solo el 34% de los documentos tiene ano "
            "identificable, y ocultarlo convierte un conteo honesto en una cifra enganosa."
        ),
    )


class AgentResponse(BaseModel):
    """Respuesta de `POST /chat`. Los tres primeros campos son el contrato ADL."""

    respuesta: str
    evaluacion: Evaluacion
    metadata: Metadata

    # -- campos propios (ADL exige los tres bloques; no prohibe mas) --------
    mode: Mode = Field("stub", description='"live" en despliegue real; "stub" son datos simulados.')
    citations: list[Citation] = Field(default_factory=list)
    view_spec: ViewSpec | None = Field(None, description="Presente solo si el turno pide vista.")
    trace_id: str = Field(
        "",
        description=(
            "Correlaciona esta respuesta con su arbol de ejecucion en "
            "GET /api/trace/{trace_id}. Es lo que permite explicar una respuesta "
            "rara despues de que ocurrio."
        ),
    )


#: Alias historicos. El nombre de la clase no viaja en el JSON, pero hay codigo
#: y pruebas que las importan asi. `TokenCount` era el nombre de `Tokens`.
ChatResponse = AgentResponse
TokenCount = Tokens


# -- GET /topics (uso interno del frontend; no lo evalua ADL) ---------------


class Topic(BaseModel):
    id: str
    nombre: str
    descripcion: str
    num_documentos: int | None = Field(
        None, description="Conteo real sobre la metadata; None si no se calculo."
    )
    preguntas_ejemplo: list[str] = Field(default_factory=list)


class TopicsResponse(BaseModel):
    topics: list[Topic]


# -- operacion -------------------------------------------------------------


class HealthResponse(BaseModel):
    """`status`: "ok" | "degraded" | "down" (nunca solo boolean).

    En `stub` el estado NUNCA es "ok": el despliegue del sabado debe correr con
    datos reales, y esta es la senal que lo hace visible sin leer una respuesta.
    """

    status: Literal["ok", "degraded", "down"]
    version: str
    mode: Mode
    max_iterations: int
    index_loaded: bool
    gateway_reachable: bool
    agent_card_loaded: bool
    debug_trace: bool = Field(
        False, description="GET /api/trace publica entradas y salidas de los turnos."
    )
    memoria_persistente: bool = Field(
        False,
        description=(
            "Memoria conversacional en disco. False = vive en RAM y se pierde en "
            "cada redespliegue: el hilo de una conversacion no sobrevive."
        ),
    )
    encoder_listo: bool = Field(
        False, description="Encoder local en memoria: el cache semantico solo opera si es True."
    )
    agentes_registrados: list[str] = Field(default_factory=list)
    tools_registered: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class UsageResponse(BaseModel):
    """Consumo observado por el propio proceso; sirve para vigilar la bolsa."""

    requests: int
    llm_calls: int
    input_tokens: int
    output_tokens: int
    trace_count: int
    cache: dict[str, Any] = Field(
        default_factory=dict,
        description="Eficacia del cache semantico: entradas y tasa de acierto.",
    )
    verificador: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Cuantas veces se activo el verificador. Si la tasa se acerca a 1, el "
            "disparador esta mal puesto y se paga una llamada extra por turno."
        ),
    )
