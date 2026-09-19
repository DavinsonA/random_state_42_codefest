"""Presupuesto de tiempo de un turno.

El frontend abandona a los 90 s. El backend, sin tope, puede tardar mas: en el
peor caso son tres llamadas al modelo mas la recuperacion, y con el timeout por
llamada en 60 s eso son 180 s. El evaluador veria "tardo demasiado" en una
pregunta que el backend estaba respondiendo bien.

Este modulo no mata nada —no se puede interrumpir una llamada en curso sin
dejar tokens pagados a medias— sino que permite **no empezar** lo que no cabe.
Cada paso caro pregunta si queda tiempo antes de gastar; si no queda, se degrada
a lo que ya se tiene, que casi siempre es evidencia recuperada y util.

Vive en un `ContextVar` para que dos turnos simultaneos no compartan reloj, y
se propaga a los hilos del plan porque cada tarea corre con `copy_context()`.
"""

from __future__ import annotations

import contextvars
import time

#: Margen que se reserva para redactar y devolver la respuesta. Medido: la
#: redaccion tarda ~7 s con 8 fragmentos, asi que 15 s deja holgura sin ser
#: generoso.
MARGEN_REDACCION_S = 15.0

_deadline: contextvars.ContextVar[float | None] = contextvars.ContextVar("_deadline", default=None)


def start_turn(presupuesto_s: float) -> None:
    """Abre el reloj del turno. Llamar una vez al entrar a `/chat`."""
    _deadline.set(time.monotonic() + presupuesto_s if presupuesto_s > 0 else None)


def restante() -> float:
    """Segundos que quedan. `inf` si no hay presupuesto fijado."""
    fin = _deadline.get()
    return float("inf") if fin is None else max(0.0, fin - time.monotonic())


def alcanza(coste_estimado_s: float = 0.0) -> bool:
    """True si queda tiempo para algo que cueste `coste_estimado_s`."""
    return restante() > coste_estimado_s


def reset() -> None:
    """Quita el presupuesto. Solo para pruebas y para el uso fuera de HTTP."""
    _deadline.set(None)
