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
from pydantic.json_schema import SkipJsonSchema

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

#: Que admite cada componente. UNA sola fuente para el validador de `ViewSpec`,
#: para `POST /api/view` y para `GET /api/components`: el tablero lee de aqui en
#: vez de repetir estas reglas en JavaScript (donde ya divergieron: forzaba
#: cada dona a agrupar por fenomeno). `group_by` vacio = el componente no agrupa.
REGLAS_GRAFICO: dict[str, dict[str, Any]] = {
    "timeline": {
        "group_by": ["anio"],
        "serie_por": True,
        "nota_obligatoria": True,
        "por_defecto": "anio",
    },
    "bar": {
        "group_by": ["fenomeno", "organizacion", "fuente", "formato", "anio"],
        "serie_por": True,
        "nota_obligatoria": False,
        "por_defecto": "fenomeno",
    },
    "stacked_bar": {
        "group_by": ["fenomeno", "organizacion", "fuente", "formato", "anio"],
        "serie_por": True,
        "nota_obligatoria": False,
        "por_defecto": "organizacion",
    },
    "donut": {
        "group_by": ["fenomeno", "organizacion", "fuente", "formato"],
        "serie_por": False,
        "nota_obligatoria": False,
        "por_defecto": "fenomeno",
    },
    "table": {
        "group_by": ["fenomeno", "organizacion", "fuente", "formato", "anio"],
        "serie_por": False,
        "nota_obligatoria": False,
        "por_defecto": "fenomeno",
    },
    "kpi": {"group_by": [], "serie_por": False, "nota_obligatoria": False, "por_defecto": None},
}

#: Graficos que pueden separar sus series por una segunda dimension.
SERIE_POR_CHARTS = tuple(c for c, r in REGLAS_GRAFICO.items() if r["serie_por"])


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

    Los campos opcionales de abajo alimentan el tooltip de una referencia
    ("CSIS · 2019 · pdf · fragmento 12 de 87") sin otra peticion. Son opcionales
    porque no toda cita los tiene (una cifra agregada, el modo stub).
    """

    doc_id: str
    chunk_id: str
    fuente: str | None = None
    fragmento: str = Field("", description="Texto citado, recortado.")
    formato: str | None = Field(None, description="pdf, csv, json, xlsx, jpg, pbf, txt...")
    posicion: int | None = Field(None, description="Posicion del fragmento en su documento (0).")
    total_fragmentos: int | None = Field(None, description="Fragmentos del documento.")
    anio: int | None = Field(None, description="Ano, solo si el documento lo declara.")
    organizacion: str | None = Field(
        None,
        description=(
            "Quien publica, en su forma legible. `fuente` trae la ruta del archivo "
            "cuando la organizacion no se conoce; este campo, solo el nombre."
        ),
    )
    fenomeno: str | None = Field(None, description="F1, F2 o F3.")
    fenomeno_nombre: str | None = Field(
        None, description="El fenomeno en la forma en que se nombra al usuario."
    )


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

    @model_validator(mode="before")
    @classmethod
    def _normalizar_claves(cls, datos: Any) -> Any:
        """Tolera la capitalizacion del esquema en la salida del modelo.

        Medido contra el gateway real: `gpt-oss-20b` devuelve `{"Chart": ...,
        "Group By": ...}` —los `title` que pydantic pone en el JSON Schema que
        se le envia— en parte de las respuestas. Con `extra="forbid"` eso no es
        un campo mal escrito sino uno DESCONOCIDO, y tumbaba la vista entera:
        cinco errores de validacion, `view_spec: null`, y una pregunta que pedia
        una grafica respondida sin grafica.

        El esquema sigue cerrado: una clave que no exista sigue siendo un error.
        Solo se absorbe una variacion de formato, que es lo que era.

        `src/agents/plan.py` lleva el gemelo de esto para `Plan`. Estan
        separados a proposito por ahora: `plan.py` importa de este modulo, asi
        que compartir el helper exigiria moverlo aqui y tocar un archivo que
        otra sesion esta editando.
        """
        if not isinstance(datos, dict):
            return datos
        normalizado: dict[str, Any] = {}
        for clave, valor in datos.items():
            limpia = str(clave).strip().lower().replace(" ", "_")
            if limpia not in normalizado or clave == limpia:
                normalizado[limpia] = valor
        return normalizado

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

    # Oculta del esquema que ve el visualizador (`SkipJsonSchema`) a proposito.
    # Medido con gpt-oss-20b: con el campo visible, la misma pregunta de dona de
    # F3 pasaba de F3 a F1 en 4 de 4 corridas (con o sin usarlo), es decir, un
    # dato mal filtrado. Se valida y funciona en el API, el tablero y el
    # compositor; darselo al modelo es una decision que se toma midiendo.
    serie_por: SkipJsonSchema[GroupBy | None] = None
    # Tope de categorias ("las 5 organizaciones"). Oculto al modelo por la misma razon que
    # `serie_por`: lo pone el codigo que lee la pregunta, no el visualizador.
    limite: SkipJsonSchema[int | None] = Field(None, ge=1, le=25)

    @model_validator(mode="after")
    def _serie_por_coherente(self) -> ViewSpec:
        """Ajusta la vista a las reglas de su propio componente. Nunca la invalida.

        Dos correcciones, y ambas siguen el mismo criterio: **una vista
        degradada es util; una vista descartada deja al analista sin grafico**.

        1. **La dimension se ajusta al componente.** `REGLAS_GRAFICO` declara que
           agrupaciones admite cada grafico —una dona reparte proporciones de
           pocas categorias y no se lee por año; una serie temporal se lee sobre
           el eje del tiempo— pero el esquema no las aplicaba, y el tablero
           recibia combinaciones que sus propias reglas declaran imposibles.
           Manda el componente y cede la dimension, no al reves: el modelo
           acierta que forma pide la pregunta mucho mas a menudo que sobre que
           dimension agruparla.

        2. **Un cruce que no se puede pintar se quita.** Medido con el modelo
           real: el cruce solo tiene sentido si es distinto del eje y si el
           componente lo usa.
        """
        regla = REGLAS_GRAFICO.get(self.chart)
        if regla and self.group_by is not None and self.group_by not in regla["group_by"]:
            self.group_by = regla["por_defecto"]

        eje = "anio" if self.chart == "timeline" else self.group_by
        if self.serie_por is not None and (
            self.serie_por == eje or self.chart not in SERIE_POR_CHARTS
        ):
            self.serie_por = None
        return self


class HallazgoDetalle(BaseModel):
    """Un hallazgo con lo que permite rastrearlo: sobre que categorias se calculo
    y que documentos lo sustentan (RETO.md §3.3: toda afirmacion, hasta su fuente)."""

    texto: str
    soporte: list[str] = Field(
        default_factory=list, description="Categorias de la agregacion sobre las que se calculo."
    )
    doc_ids: list[str] = Field(
        default_factory=list,
        description="Muestra de documentos que lo sustentan; abren en /api/document/{doc_id}.",
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
    view_specs: list[ViewSpec] = Field(
        default_factory=list,
        description=(
            "La vista pedida y las que la explican. La primera es SIEMPRE `view_spec`, "
            "que se mantiene por separado para no romper a ningun cliente que ya lo lea."
        ),
    )
    hallazgos: list[str] = Field(
        default_factory=list,
        description=(
            "Lo que las cifras de la vista dicen, calculado sin modelo: frecuencias y "
            "proporciones reales. Nunca indices, scores ni pronosticos (RETO.md "
            "§Restricciones duras)."
        ),
    )
    hallazgos_detalle: list[HallazgoDetalle] = Field(
        default_factory=list,
        description=(
            "Los mismos `hallazgos`, en el mismo orden, con su soporte y sus `doc_id`. "
            "`hallazgos` se conserva tal cual para no romper a ningun cliente."
        ),
    )
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


# -- operacion -------------------------------------------------------------


class HealthResponse(BaseModel):
    """`status`: "ok" | "degraded" | "down" (nunca solo boolean).

    En `stub` el estado NUNCA es "ok": el despliegue del sabado debe correr con
    datos reales, y esta es la senal que lo hace visible sin leer una respuesta.
    """

    status: Literal["ok", "degraded", "down"]
    version: str
    mode: Mode
    max_llamadas_por_turno: int = Field(
        0,
        description=(
            "Peor caso de llamadas al modelo en un turno, calculado desde los topes "
            "reales del grafo. Acotado por construccion: el Bloque B se normaliza "
            "contra los otros equipos."
        ),
    )
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
