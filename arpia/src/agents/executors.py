"""Ejecutores: los agentes especializados que el orquestador invoca.

Este modulo es el registro y la frontera. Cada ejecutor recibe un `Paso` del
plan y devuelve un `Resultado`; el grafo no sabe nada mas de ellos, asi que
anadir un agente es registrar una funcion, no tocar el grafo.

**Estado en la Fase 3:** solo esta el documental, y solo su mitad local —la
recuperacion sobre FAISS, que no cuesta tokens—. La redaccion con modelo, el
agente analitico y el visualizador son la Fase 4. Lo que se prueba aqui es el
plano de control: planificar, delegar, evaluar la evidencia y replanificar una
vez.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from src.agents.plan import Paso
from src.config import get_logger
from src.observability import tracing

log = get_logger(__name__)

#: Puntaje de similitud a partir del cual un fragmento se considera evidencia.
#: Calibrado con consultas reales sobre el corpus: las buenas coincidencias caen
#: entre 0,57 y 0,68 (bge-m3 normalizado, producto punto). 0,50 deja margen sin
#: admitir ruido. PENDIENTE de recalibrar en la Fase 5 con el verificador: si
#: salta siempre, el umbral esta mal y se come el bloque de eficiencia.
UMBRAL_EVIDENCIA = 0.50


@dataclass
class Resultado:
    """Lo que un ejecutor le devuelve al grafo."""

    agente: str
    texto: str = ""
    evidencia: list[dict[str, Any]] = field(default_factory=list)
    view_spec: dict[str, Any] | None = None
    suficiente: bool = False
    error: str = ""


Ejecutor = Callable[[Paso], Resultado]
EJECUTORES: dict[str, Ejecutor] = {}


def registrar(agente: str) -> Callable[[Ejecutor], Ejecutor]:
    """Registra un ejecutor bajo un id de la agent card."""

    def decorador(fn: Ejecutor) -> Ejecutor:
        EJECUTORES[agente] = fn
        return fn

    return decorador


def ejecutar(paso: Paso) -> Resultado:
    """Corre un paso del plan. Nunca lanza: un ejecutor caido degrada el turno,
    no lo tumba."""
    fn = EJECUTORES.get(paso.agente)
    if fn is None:
        log.warning("el plan pidio '%s', que no esta implementado todavia", paso.agente)
        return Resultado(agente=paso.agente, error=f"agente '{paso.agente}' no implementado")
    with tracing.span("tool", f"ejecutar.{paso.agente}", input=paso.consulta[:300]) as sp:
        try:
            resultado = fn(paso)
            sp.set_output(f"suficiente={resultado.suficiente} evidencia={len(resultado.evidencia)}")
            return resultado
        except Exception as exc:  # noqa: BLE001 - frontera deliberada
            log.exception("el ejecutor '%s' fallo", paso.agente)
            sp.set_output(f"error: {type(exc).__name__}")
            return Resultado(agente=paso.agente, error=f"{type(exc).__name__}: {exc}")


# -- agente documental (mitad local; la redaccion llega en la Fase 4) --------


@registrar("agente_documental")
def documental(paso: Paso) -> Resultado:
    """Recupera evidencia del corpus. Cero tokens: FAISS y el encoder son locales.

    Esa gratuidad es la ventaja que `RETO.md` senala en el bloque de eficiencia:
    recuperacion que no pasa por un LLM son tokens que los demas equipos gastan.
    """
    from src.retrieval.enrich import fenomeno_numero
    from src.tools.corpus import _get_index

    hits = _get_index().search(paso.consulta, k=8)

    numero = fenomeno_numero(paso.fenomeno) if paso.fenomeno else None
    if numero is not None:
        filtrados = [h for h in hits if h.metadata.get("fenomeno") == numero]
        # Si el filtro deja la evidencia en nada, se prefiere la sin filtrar: un
        # filtro demasiado estricto es peor que uno impreciso cuando la
        # alternativa es responder "no encontre nada" teniendo material.
        hits = filtrados or hits

    evidencia = [
        {
            "chunk_id": h.chunk_id,
            "doc_id": h.doc_id,
            "texto": h.text,
            "score": round(h.score, 4),
            "citacion": h.citation(),
            "organizacion": h.metadata.get("organizacion", ""),
            "anio": h.metadata.get("anio"),
        }
        for h in hits
    ]
    mejor = max((e["score"] for e in evidencia), default=0.0)
    return Resultado(
        agente="agente_documental",
        evidencia=evidencia,
        suficiente=mejor >= UMBRAL_EVIDENCIA,
    )
