"""Orquestador: decide a que agentes delegar. UNA sola llamada al modelo.

Las seis preguntas de AGENTS.md §8:

1. **Proposito.** Convertir la consulta del usuario en un `Plan` estructurado:
   que agentes especializados se invocan, con que consulta y si van en paralelo.
2. **Entrada.** La pregunta saneada y, si el turno es una replanificacion, el
   motivo por el que la evidencia anterior no basto.
3. **Salida.** Un `Plan` validado. Nunca texto libre.
4. **Criterio de exito.** Que el plan se pueda ejecutar tal cual, sin
   interpretacion, y que el turno cueste dos llamadas al modelo en vez de las
   tres a siete impredecibles de un bucle ReAct.
5. **Autoridad.** Decide a quien se llama. No busca, no redacta, no toca el
   corpus ni el tablero.
6. **Que NO debe saber.** El contenido del corpus. Si tuviera que leer
   documentos para planificar, el plan dejaria de ser una decision de
   enrutamiento y volveria a ser una conversacion con las herramientas.

Coste fijo: una llamada. Si esa llamada falla, devuelve un plan de respaldo
determinista (`plan.plan_de_respaldo`) en vez de propagar el error: un fallo del
gateway degrada a busqueda documental, no a una disculpa.
"""

from __future__ import annotations

from typing import Any

from src.agents import voz
from src.agents.card import gateway_model_for, model_for
from src.agents.plan import MAX_PASOS, Plan, plan_de_respaldo
from src.config import get_logger, get_settings
from src.observability import tracing, turnlog, usage

log = get_logger(__name__)

AGENTE = "orquestador"

SYSTEM_PROMPT = f"""Eres el orquestador de A.R.P.I.A., un sistema de analisis de
fuentes abiertas. Tu unica tarea es decidir a que agentes especializados delegar
la consulta del usuario. No respondes la pregunta tu mismo.

Agentes disponibles:

- `agente_documental`: responde con evidencia textual del corpus. Usalo cuando
  la pregunta pida hechos, cifras, declaraciones, descripciones de eventos o de
  actores. Es el agente por defecto: ante la duda, este.
- `agente_analitico`: responde preguntas cuantitativas sobre la metadata
  agregada (cuantos documentos, distribuciones, comparaciones de volumen entre
  fenomenos). Usalo cuando la pregunta sea de conteo o de distribucion, no de
  contenido. **Para este agente rellena SIEMPRE `group_by`** con la dimension
  que pide la pregunta: fenomeno, organizacion, fuente, formato o anio. Si lo
  dejas vacio, el agente tiene que adivinarla a partir de tu texto y puede
  contestar por una dimension distinta de la preguntada.
- `agente_visualizador`: decide que componente del tablero mostrar. Usalo cuando
  el usuario pida ver, graficar, comparar visualmente o filtrar el tablero.

{voz.DOMINIO}
Los ids de fenomeno son F1 (IA y capacidades estrategicas), F2 (seguridad del
entorno espacial) y F3 (dinamicas territoriales).

Reglas:
- Un paso = una sola idea. Para comparar dos temas, dos pasos separados: una
  consulta que mezcla dos temas recupera resultados superficiales de ambos.
- Maximo {MAX_PASOS} pasos. Cada paso cuesta presupuesto.
- `paralelo: true` si los pasos no dependen unos de otros. El documental y el
  visualizador casi nunca dependen entre si.
- Si la pregunta pide datos Y una vista, planifica ambos agentes.
- `fenomeno` solo si la pregunta lo acota de forma clara.
"""

_REPLAN = """La primera pasada no encontro evidencia suficiente. Motivo:
{motivo}

Replanifica con consultas DISTINTAS: reformula los terminos, prueba sinonimos o
acota a un fenomeno. No repitas las mismas consultas, no traeran nada nuevo.
Consultas ya intentadas: {intentadas}"""


def _llm():
    """Cliente del gateway para el orquestador, con su modelo de la agent card."""
    from langchain_openai import ChatOpenAI

    s = get_settings()
    if not s.llm_configured:
        raise RuntimeError("LLM_BASE_URL y LLM_API_KEY no configurados.")
    return ChatOpenAI(
        base_url=s.llm_base_url,
        api_key=s.llm_api_key,
        model=gateway_model_for(AGENTE) or s.llm_model,
        timeout=s.request_timeout_s,
        temperature=0,
    )


def _mensajes(pregunta: str, motivo: str, intentadas: list[str]) -> list[dict[str, str]]:
    contenido = pregunta
    if motivo:
        detalle = _REPLAN.format(motivo=motivo, intentadas=intentadas)
        contenido = f"{pregunta}\n\n{detalle}"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": contenido},
    ]


def planificar(
    pregunta: str,
    *,
    motivo: str = "",
    intentadas: list[str] | None = None,
    modelo: Any = None,
) -> Plan:
    """Produce el plan del turno. UNA llamada al modelo. Nunca lanza.

    Args:
        pregunta: consulta saneada del usuario.
        motivo: por que se replanifica. Vacio en la primera pasada.
        intentadas: consultas ya lanzadas, para no repetirlas.
        modelo: cliente ya construido. Solo para pruebas; en produccion se
            construye aqui.

    Returns:
        Un `Plan` validado. Si el modelo falla o devuelve algo que no encaja en
        el esquema, un plan de respaldo determinista.
    """
    with tracing.span("llm", "orquestador.planificar", input=pregunta[:500]) as sp:
        turnlog.record_agent(AGENTE)
        try:
            cliente = modelo if modelo is not None else _llm()
            estructurado = cliente.with_structured_output(Plan, include_raw=True)
            crudo = estructurado.invoke(_mensajes(pregunta, motivo, intentadas or []))

            # `include_raw` deja el mensaje original accesible: es de donde sale
            # el consumo real de tokens. Sin esto, la llamada del orquestador no
            # aparece en `tokens_por_agente` y el desglose miente.
            mensaje = crudo.get("raw") if isinstance(crudo, dict) else None
            usage.record_usage(
                getattr(mensaje, "usage_metadata", None),
                agent=AGENTE,
                model=model_for(AGENTE),
            )

            plan = crudo.get("parsed") if isinstance(crudo, dict) else crudo
            if not isinstance(plan, Plan) or not plan.pasos:
                log.warning("el orquestador no devolvio un plan usable; se usa el de respaldo")
                turnlog.marcar_no_cacheable("plan_de_respaldo")
                sp.set_output("plan de respaldo (salida no usable)")
                return plan_de_respaldo(pregunta)

            sp.set_output(plan.model_dump_json())
            return plan
        except Exception as exc:  # noqa: BLE001 - frontera: planificar nunca tumba el turno
            log.warning("fallo la planificacion (%s); se usa el plan de respaldo", exc)
            turnlog.marcar_no_cacheable("plan_de_respaldo")
            sp.set_output(f"plan de respaldo ({type(exc).__name__})")
            return plan_de_respaldo(pregunta)
