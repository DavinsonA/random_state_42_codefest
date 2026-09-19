"""Traza jerarquica de spans, consumible por un evaluador externo (DeepEval).

DeepEval mide trayectoria, no solo respuesta final: que se llamo, con que
argumentos, en que orden, cuantas iteraciones. Un span es la unidad minima de
esa trayectoria. La jerarquia (`parent_id`) permite reconstruir el arbol de
ejecucion de una request completa.

Ambito por request: `start_trace()` se llama una vez al entrar a un endpoint
HTTP y crea un `trace_id` nuevo. Usa `contextvars` para que requests
concurrentes (FastAPI las corre en threads separados) no mezclen spans.
"""

from __future__ import annotations

import contextvars
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Literal

SpanType = Literal["llm", "tool", "retrieval"]


@dataclass
class Span:
    """Un nodo de la traza: una llamada con su entrada, salida y duracion."""

    span_id: str
    parent_id: str | None
    type: SpanType
    name: str
    input: Any
    output: Any
    start_ms: float
    end_ms: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "type": self.type,
            "name": self.name,
            "input": self.input,
            "output": self.output,
            "start_ms": round(self.start_ms, 3),
            "end_ms": round(self.end_ms, 3),
        }


@dataclass
class Trace:
    """Traza completa de una request: un `trace_id` y sus spans."""

    trace_id: str
    spans: list[Span] = field(default_factory=list)

    def to_spans(self) -> list[dict[str, Any]]:
        return [s.to_dict() for s in self.spans]


_current_trace: contextvars.ContextVar[Trace | None] = contextvars.ContextVar(
    "_current_trace", default=None
)
_current_parent: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "_current_parent", default=None
)
_trace_count = 0

#: Trazas recientes, consultables por `GET /api/trace/{trace_id}`. Acotado
#: (AGENTS.md §8): un proceso de 24 horas no puede guardar una traza por
#: pregunta. Se conservan las ultimas, que es lo que sirve para diagnosticar una
#: respuesta rara que acaba de ocurrir.
MAX_TRAZAS = 50
_recientes: OrderedDict[str, Trace] = OrderedDict()
_recientes_lock = Lock()


def start_trace() -> str:
    """Inicia una traza nueva. Llamar una vez al entrar a un endpoint HTTP."""
    global _trace_count
    _trace_count += 1
    trace = Trace(trace_id=uuid.uuid4().hex)
    _current_trace.set(trace)
    _current_parent.set(None)
    with _recientes_lock:
        _recientes[trace.trace_id] = trace
        while len(_recientes) > MAX_TRAZAS:
            _recientes.popitem(last=False)
    return trace.trace_id


def trace_count() -> int:
    """Numero de trazas iniciadas por el proceso (contrato `/usage`)."""
    return _trace_count


def current_trace_id() -> str | None:
    trace = _current_trace.get()
    return trace.trace_id if trace else None


def to_spans() -> list[dict[str, Any]]:
    """Spans de la traza activa, en formato serializable."""
    trace = _current_trace.get()
    return trace.to_spans() if trace else []


def get_trace(trace_id: str) -> list[dict[str, Any]] | None:
    """Spans de una traza pasada. None si ya no esta en el buffer.

    El arbol se reconstruye con `parent_id`: cada span sabe quien lo invoco, asi
    que se puede ver que agente llamo a que herramienta y cuanto tardo cada
    tramo. Es lo unico que permite explicar una respuesta rara despues de que
    ocurrio.
    """
    with _recientes_lock:
        trace = _recientes.get(trace_id)
    return trace.to_spans() if trace else None


def recent_trace_ids() -> list[str]:
    """Ids de las trazas en memoria, de la mas reciente a la mas antigua."""
    with _recientes_lock:
        return list(reversed(_recientes.keys()))


def reset() -> None:
    """Vacia el buffer de trazas. Solo para pruebas."""
    with _recientes_lock:
        _recientes.clear()


# -- turno en curso por sesion ----------------------------------------------
# Todo lo de aqui abajo es ADITIVO: no altera `Span`, ni `to_dict()`, ni el
# formato que consume DeepEval. Existe para que `GET /api/progress` pueda decir
# por donde va un turno que todavia no ha terminado.
#
# **Supuesto de despliegue: un solo worker** (`--workers 1` en el Dockerfile,
# donde es una decision explicita porque cada worker carga su propia copia del
# indice y del encoder). Este mapa vive en memoria del proceso: con varios
# workers, el GET del navegador puede caer en un proceso que no atendio ese
# turno, y el panel se quedaria vacio sin error visible. Si algun dia se
# levantan mas workers, esto necesita un almacen compartido.

#: Sesiones con turno en curso que se recuerdan a la vez. Acotado por la misma
#: razon que `MAX_TRAZAS` (AGENTS.md §8): un proceso que corre 24 horas no puede
#: tener una estructura que crece con cada turno. El tope es holgado frente a
#: los evaluadores concurrentes que se esperan, y lo que se descarta es lo mas
#: antiguo, que es justo lo que ya no esta en vuelo.
MAX_SESIONES = 64
_sesiones: OrderedDict[str, str] = OrderedDict()
_sesiones_lock = Lock()


def registrar_sesion(sesion_id: str, trace_id: str) -> None:
    """Anota que esta sesion tiene un turno corriendo bajo esta traza."""
    if not sesion_id:
        return
    with _sesiones_lock:
        _sesiones.pop(sesion_id, None)  # reinsertar para que cuente como reciente
        _sesiones[sesion_id] = trace_id
        while len(_sesiones) > MAX_SESIONES:
            _sesiones.popitem(last=False)


def olvidar_sesion(sesion_id: str) -> None:
    """El turno termino. Se llama tambien cuando falla: sin esto, el panel
    seguiria mostrando el turno anterior como si siguiera en vuelo."""
    with _sesiones_lock:
        _sesiones.pop(sesion_id, None)


def olvidar_sesiones() -> None:
    """Vacia el mapa. Solo para pruebas."""
    with _sesiones_lock:
        _sesiones.clear()


def trace_de_sesion(sesion_id: str) -> str | None:
    with _sesiones_lock:
        return _sesiones.get(sesion_id)


def sesiones_en_curso() -> int:
    with _sesiones_lock:
        return len(_sesiones)


#: Los unicos campos de un `Span` que pueden salir por una URL publica.
#:
#: Lista BLANCA, y la diferencia importa: con una lista negra, un campo nuevo en
#: `Span` se publicaria solo el dia que alguien lo anada. `input` y `output`
#: llevan el texto de las preguntas y los fragmentos del corpus —es la razon por
#: la que `GET /api/trace` esta cerrado tras `ARPIA_DEBUG_TRACE`— y
#: `start_ms`/`end_ms` son relojes del proceso que no aportan nada al panel.
_CAMPOS_PUBLICOS = ("span_id", "parent_id")


def pasos_de_traza(trace_id: str) -> list[dict[str, Any]] | None:
    """Proyeccion publicable de una traza: que paso, de quien colgaba y cuanto
    tardo. Nunca su contenido.

    Devuelve None si la traza ya no esta en el buffer.

    La lista de spans se copia y la copia se proyecta fuera del lock. El span
    que este cerrandose en otro hilo aparecera en la llamada siguiente: para un
    panel que se refresca cada segundo, ver un paso con un instante de retraso
    es correcto, y bloquear el hilo del turno para leerlo no lo seria.
    """
    with _recientes_lock:
        trace = _recientes.get(trace_id)
        spans = list(trace.spans) if trace else None
    if spans is None:
        return None
    return [
        {
            **{campo: getattr(s, campo) for campo in _CAMPOS_PUBLICOS},
            "tipo": s.type,
            "nombre": s.name,
            "duracion_ms": round(max(s.end_ms - s.start_ms, 0.0), 1),
        }
        for s in spans
    ]


class span:  # noqa: N801 - nombre en minuscula deliberado, uso como `with tracing.span(...)`
    """Context manager que registra un span en la traza activa.

    Si no hay traza activa (por ejemplo, codigo llamado fuera de un request
    HTTP, como en pruebas unitarias de un nodo aislado), no falla: solo no
    registra nada. Un span nunca debe propagar una excepcion adicional.
    """

    def __init__(self, span_type: SpanType, name: str, input: Any = None) -> None:  # noqa: A002
        self.type = span_type
        self.name = name
        self.input = input
        self.output: Any = None
        self._span_id = uuid.uuid4().hex
        self._parent_id: str | None = None
        self._token: contextvars.Token | None = None
        self._start = 0.0

    def set_output(self, output: Any) -> None:
        self.output = output

    def __enter__(self) -> span:
        self._start = time.perf_counter() * 1000
        self._parent_id = _current_parent.get()
        self._token = _current_parent.set(self._span_id)
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        end = time.perf_counter() * 1000
        trace = _current_trace.get()
        if trace is not None:
            trace.spans.append(
                Span(
                    span_id=self._span_id,
                    parent_id=self._parent_id,
                    type=self.type,
                    name=self.name,
                    input=self.input,
                    output=self.output,
                    start_ms=self._start,
                    end_ms=end,
                )
            )
        if self._token is not None:
            _current_parent.reset(self._token)
        return False
