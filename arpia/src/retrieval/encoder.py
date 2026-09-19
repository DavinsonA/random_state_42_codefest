"""Encoder local compartido (bge-m3).

UNICO punto del sistema que instancia el modelo de embeddings. Existe por una
razon de memoria: el encoder ocupa ~2,3 GB en RAM y lo necesitan dos
componentes distintos —la busqueda vectorial (`src/retrieval/index.py`) y el
cache semantico (`src/agents/memory.py`)—. Dos instancias serian 4,6 GB y un
contenedor muerto.

Codificar aqui **no consume tokens del presupuesto**: el modelo corre en la CPU
del contenedor, no en el gateway del evento. Esa es exactamente la ventaja que
`RETO.md` senala en el bloque de eficiencia: recuperacion que no pasa por un
LLM son tokens que los demas equipos si gastan.

**Carga explicita, nunca implicita.** `loaded()` no tiene efectos: solo dice
si el modelo ya esta en memoria. Quien quiera cargarlo llama a `warmup()`, y eso
se hace al arrancar el proceso. La razon es concreta: la primera carga descarga
~2 GB y tarda minutos, y si se dispara dentro de una peticion, el evaluador se
come ese tiempo como latencia — o un timeout.

Degradacion: si `sentence-transformers` no esta instalado o el modelo no esta en
cache, `warmup()` devuelve False y quien lo use debe tener camino alternativo.
Nunca se lanza.
"""

from __future__ import annotations

import threading
from typing import Any

from src.config import get_logger

log = get_logger(__name__)

DEFAULT_MODEL = "BAAI/bge-m3"

_encoder: Any = None
_fallo: str | None = None
_lock = threading.Lock()


def load(model_id: str | None = None) -> Any:
    """Devuelve el encoder, cargandolo la primera vez. `None` si no se puede.

    La primera llamada descarga el modelo (~2 GB) y tarda. Conviene provocarla
    en el arranque y no en la primera consulta de un evaluador.
    """
    global _encoder, _fallo
    if _encoder is not None or _fallo is not None:
        return _encoder
    with _lock:
        if _encoder is not None or _fallo is not None:
            return _encoder
        try:
            from sentence_transformers import SentenceTransformer

            nombre = model_id or DEFAULT_MODEL
            log.info("cargando encoder %s en CPU (primera vez: descarga ~2 GB)", nombre)
            _encoder = SentenceTransformer(nombre, device="cpu")
        except Exception as exc:  # noqa: BLE001 - frontera: nunca tumba el proceso
            _fallo = f"{type(exc).__name__}: {exc}"
            log.warning("encoder local no disponible: %s", _fallo)
    return _encoder


def loaded() -> bool:
    """True si el modelo YA esta en memoria. Sin efectos secundarios.

    Esta es la pregunta que deben hacer los caminos opcionales (como el cache
    semantico): "esta disponible ahora mismo", no "podrias cargarlo".
    """
    return _encoder is not None


def warmup(model_id: str | None = None) -> bool:
    """Carga el modelo ahora, a proposito. Bloqueante. Llamar al arrancar."""
    return load(model_id) is not None


def failure() -> str | None:
    """Motivo por el que el encoder no esta disponible, si lo hay."""
    return _fallo


def encode(texts: list[str], model_id: str | None = None):
    """Codifica textos a vectores normalizados. Lanza si no hay encoder.

    Normalizados a proposito: con vectores unitarios el producto punto ES la
    similitud coseno, que es lo que usan tanto el indice (`IndexFlatIP`) como
    el umbral del cache semantico.
    """
    modelo = load(model_id)
    if modelo is None:
        raise RuntimeError(f"encoder local no disponible: {_fallo}")
    return modelo.encode(texts, normalize_embeddings=True, convert_to_numpy=True)


def reset() -> None:
    """Descarga el encoder. Solo para pruebas."""
    global _encoder, _fallo
    with _lock:
        _encoder = None
        _fallo = None
