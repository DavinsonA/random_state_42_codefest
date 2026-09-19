"""Agregaciones parametrizadas sobre la tabla de documentos. CERO tokens.

Nunca hay SQL —ni generado por un modelo ni escrito a mano—: la unica forma de
pedir un agregado es elegir una `Metrica`, un `GroupBy` y unos filtros del
vocabulario cerrado de `src/api/contracts.py`. Lo que no esta en ese vocabulario
no se puede preguntar, y por tanto no se puede inyectar.

`RETO.md` prohibe presentar como medicion objetiva cualquier indice o puntaje
calculado ad-hoc. Aqui solo hay conteos y frecuencias sobre metadata real, y
cada resultado viene con los `doc_id` que lo sustentan: cualquier cifra del
tablero se puede abrir hasta sus documentos.

La tabla se construye una vez y se cachea: son 1.826 filas.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any

from src.api.contracts import Fenomeno, GroupBy, Metrica
from src.config import get_logger

log = get_logger(__name__)

#: Cobertura del ano en el corpus. Solo 622 de 1.826 documentos lo declaran en
#: su ruta. Toda agregacion temporal arrastra este numero: ocultarlo convierte
#: un conteo honesto en una cifra enganosa.
DOCS_CON_ANIO_PCT = 34

_tabla: list[dict[str, Any]] | None = None
_lock = threading.Lock()


def tabla() -> list[dict[str, Any]]:
    """Tabla de documentos, cacheada. Lista vacia si el indice no esta."""
    global _tabla
    if _tabla is not None:
        return _tabla
    with _lock:
        if _tabla is None:
            try:
                from src.tools.corpus import _get_index

                _tabla = _get_index().document_table()
                log.info("tabla de agregacion: %s documentos", len(_tabla))
            except Exception as exc:  # noqa: BLE001 - frontera: nunca tumba el turno
                log.warning("no se pudo construir la tabla de agregacion: %s", exc)
                _tabla = []
    return _tabla


def reset() -> None:
    """Descarta la tabla cacheada. Solo para pruebas."""
    global _tabla
    with _lock:
        _tabla = None


def _valor(fila: dict[str, Any], dimension: GroupBy) -> str:
    """Valor de agrupacion de una fila. Cadena vacia = no identificado."""
    if dimension == "anio":
        anio = fila.get("anio")
        return str(anio) if anio else ""
    return str(fila.get(dimension) or "")


def agregar(
    metrica: Metrica = "conteo_documentos",
    group_by: GroupBy = "fenomeno",
    *,
    fenomenos: list[Fenomeno] | None = None,
    organizacion: str | None = None,
    desde: int | None = None,
    hasta: int | None = None,
    limite: int = 25,
) -> dict[str, Any]:
    """Cuenta documentos o fragmentos, agrupados por una dimension.

    Args:
        metrica: `conteo_documentos` o `conteo_fragmentos`.
        group_by: dimension de agrupacion, del vocabulario cerrado.
        fenomenos: filtra a estos fenomenos. None o vacio = los tres.
        organizacion: filtra a una organizacion exacta.
        desde, hasta: rango de anos inclusive. Solo aplica a los documentos con
            ano identificado.
        limite: filas devueltas, de mayor a menor.

    Returns:
        `{"filas": [{"clave", "valor", "doc_ids"}], "total", "cobertura"}`.
        `cobertura` declara cuantos documentos del universo filtrado quedaron
        fuera por no tener el dato de la dimension pedida.
    """
    filas = tabla()
    universo = len(filas)

    if fenomenos:
        permitidos = set(fenomenos)
        filas = [f for f in filas if f.get("fenomeno") in permitidos]
    if organizacion:
        filas = [f for f in filas if f.get("organizacion") == organizacion]
    if desde is not None:
        filas = [f for f in filas if f.get("anio") and f["anio"] >= desde]
    if hasta is not None:
        filas = [f for f in filas if f.get("anio") and f["anio"] <= hasta]

    conteos: dict[str, int] = defaultdict(int)
    docs: dict[str, list[str]] = defaultdict(list)
    sin_dato = 0
    for fila in filas:
        clave = _valor(fila, group_by)
        if not clave:
            sin_dato += 1
            continue
        conteos[clave] += 1 if metrica == "conteo_documentos" else fila["n_fragmentos"]
        if len(docs[clave]) < 10:  # muestra de respaldo, no la lista entera
            docs[clave].append(fila["doc_id"])

    ordenadas = sorted(conteos.items(), key=lambda kv: (-kv[1], kv[0]))[:limite]
    return {
        "metrica": metrica,
        "group_by": group_by,
        "filas": [
            {"clave": clave, "valor": valor, "doc_ids": docs[clave]} for clave, valor in ordenadas
        ],
        "total": sum(conteos.values()),
        "cobertura": {
            "documentos_universo": universo,
            "documentos_filtrados": len(filas),
            "sin_dato_en_la_dimension": sin_dato,
        },
    }


def dimensiones_disponibles() -> dict[str, Any]:
    """Valores reales de cada dimension, para no proponer vistas imposibles.

    Lo consume el agente visualizador antes de emitir un `ViewSpec`: si una
    organizacion no esta en esta lista, no existe en el corpus.
    """
    filas = tabla()
    organizaciones = sorted({f["organizacion"] for f in filas if f.get("organizacion")})
    anios = sorted({f["anio"] for f in filas if f.get("anio")})
    return {
        "documentos": len(filas),
        "fenomenos": sorted({f["fenomeno"] for f in filas if f.get("fenomeno")}),
        "organizaciones": organizaciones,
        "formatos": sorted({f["formato"] for f in filas if f.get("formato")}),
        "anios": {"min": anios[0], "max": anios[-1]} if anios else {},
        "cobertura_anio_pct": DOCS_CON_ANIO_PCT,
    }
