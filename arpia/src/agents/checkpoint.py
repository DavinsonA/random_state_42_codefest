"""Memoria conversacional persistente del grafo (checkpointer SQLite).

El `sesion_id` de `POST /chat` viaja como `thread_id` y este modulo es lo que
hace que eso signifique algo: el estado del grafo se guarda por hilo y el turno
siguiente continua donde quedo el anterior.

**Por que SQLite y no memoria.** `InMemorySaver` vive en el proceso: se pierde en
cada redespliegue y crece sin limite durante las 24 horas del evento. Un archivo
SQLite sobrevive al reinicio, se puede inspeccionar con `sqlite3` cuando algo va
mal a las 3 de la manana, y tiene una politica de purga ejecutable.

**Donde vive el archivo.** En `state/`, NO en `data/`. El volumen del corpus se
monta en solo lectura a proposito —el indice no debe poder corromperse— asi que
el estado mutable necesita su propio volumen. Si la ruta no es escribible se cae
a memoria y se avisa: una sesion sin memoria responde peor, pero responde.
Perder el turno por no poder abrir un archivo de estado seria mucho peor.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path
from typing import Any

from src.config import get_logger

log = get_logger(__name__)

_checkpointer: Any = None
_lock = threading.Lock()
_persistente = False


def _ruta() -> Path:
    """Ruta del archivo de checkpoints. `CHECKPOINT_PATH` la sobrescribe."""
    return Path(os.getenv("CHECKPOINT_PATH", "state/checkpoints.sqlite"))


def get_checkpointer() -> Any:
    """Checkpointer del proceso. SQLite si se puede; memoria si no.

    `check_same_thread=False` es obligatorio: FastAPI atiende los turnos en
    hilos distintos del pool y todos comparten esta conexion. SQLite serializa
    las escrituras internamente, asi que es seguro.
    """
    global _checkpointer, _persistente
    if _checkpointer is not None:
        return _checkpointer
    with _lock:
        if _checkpointer is not None:
            return _checkpointer
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver

            ruta = _ruta()
            ruta.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(ruta), check_same_thread=False)
            _checkpointer = SqliteSaver(conn)
            _checkpointer.setup()
            _persistente = True
            log.info("memoria conversacional en %s", ruta)
        except Exception as exc:  # noqa: BLE001 - frontera: nunca tumba el arranque
            from langgraph.checkpoint.memory import InMemorySaver

            log.warning("sin checkpointer persistente (%s); se usa memoria del proceso", exc)
            _checkpointer = InMemorySaver()
            _persistente = False
    return _checkpointer


def es_persistente() -> bool:
    """True si la memoria sobrevive a un reinicio. Lo reporta `/health`."""
    return _persistente


def reset() -> None:
    """Descarta el checkpointer. Solo para pruebas."""
    global _checkpointer, _persistente
    with _lock:
        _checkpointer = None
        _persistente = False
