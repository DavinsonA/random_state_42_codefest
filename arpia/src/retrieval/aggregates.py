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
    """Tabla de documentos, cacheada. Lista vacia si el indice no esta.

    **El fallo no se cachea.** Si el volumen del indice aun no esta montado
    cuando llega la primera peticion, cachear la lista vacia dejaria el tablero
    en blanco hasta reiniciar el contenedor, respondiendo 200 y sin un solo
    aviso. Paso exactamente eso esta noche con una ruta mal configurada:
    `/api/view` devolvia `total: 0` con el corpus entero en disco.
    """
    global _tabla
    if _tabla:
        return _tabla
    with _lock:
        if _tabla:
            return _tabla
        try:
            from src.tools.corpus import _get_index

            filas = _get_index().document_table()
        except Exception as exc:  # noqa: BLE001 - frontera: nunca tumba el turno
            log.warning("no se pudo construir la tabla de agregacion: %s", exc)
            return []
        if not filas:
            log.warning("la tabla de agregacion salio vacia; no se cachea")
            return []
        _tabla = filas
        log.info("tabla de agregacion: %s documentos", len(_tabla))
    return _tabla


def disponible() -> bool:
    """True si hay tabla con la que responder. Lo consulta el tablero."""
    return bool(tabla())


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


def _seleccion(
    fenomenos: list[Fenomeno] | None,
    organizacion: str | None,
    desde: int | None,
    hasta: int | None,
    formato: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """Filas que entran en una agregacion.

    Returns:
        `(filas, dimensionado, universo)`: las filas tras TODOS los filtros, las
        que quedan antes del filtro temporal (base de la cobertura) y el tamano
        de la tabla entera.

    La cobertura se mide ANTES del filtro temporal, y el motivo es concreto:
    un rango de anos descarta en silencio los documentos sin ano, asi que
    medirla despues daria siempre "0 sin dato" — justo el mensaje tranquilizador
    y falso que ese campo existe para evitar.
    """
    filas = tabla()
    universo = len(filas)
    if fenomenos:
        permitidos = set(fenomenos)
        filas = [f for f in filas if f.get("fenomeno") in permitidos]
    if organizacion:
        filas = [f for f in filas if f.get("organizacion") == organizacion]
    if formato:
        filas = [f for f in filas if f.get("formato") == formato]
    dimensionado = list(filas)
    if desde is not None:
        filas = [f for f in filas if f.get("anio") and f["anio"] >= desde]
    if hasta is not None:
        filas = [f for f in filas if f.get("anio") and f["anio"] <= hasta]
    return filas, dimensionado, universo


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
        `cobertura.sin_dato_en_la_dimension` declara cuantos documentos quedaron
        fuera por no tener el dato de la dimension pedida, medido antes de
        aplicar el rango temporal.
    """
    filas, dimensionado, universo = _seleccion(fenomenos, organizacion, desde, hasta)
    sin_dato = sum(1 for f in dimensionado if not _valor(f, group_by))
    # Un rango de anos descarta TODO documento sin ano, agrupe por lo que
    # agrupe. Medido en el corpus: un rango 2005-2026 sobre un conteo por
    # organizacion deja 621 de 1.826 documentos y hace desaparecer al mayor
    # publicador, porque ninguno de sus documentos declara ano. Sin este numero
    # la vista parece completa y no lo es.
    excluidos_por_fecha = len(dimensionado) - len(filas)

    conteos: dict[str, int] = defaultdict(int)
    docs: dict[str, list[str]] = defaultdict(list)
    for fila in filas:
        clave = _valor(fila, group_by)
        if not clave:
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
            "documentos_en_dimension": len(dimensionado),
            "documentos_contados": len(filas),
            "sin_dato_en_la_dimension": sin_dato,
            "excluidos_por_fecha": excluidos_por_fecha,
        },
    }


#: Tope de series por grafica: mas de esto no se distingue ni por color ni en la leyenda.
MAX_SERIES = 8

#: Categorias por grafica cuando la dimension no es el ano (que es una serie completa).
MAX_CATEGORIAS = 25


def agregar_series(
    metrica: Metrica = "conteo_documentos",
    group_by: GroupBy = "fenomeno",
    serie_por: GroupBy | None = None,
    *,
    fenomenos: list[Fenomeno] | None = None,
    organizacion: str | None = None,
    desde: int | None = None,
    hasta: int | None = None,
    limite: int | None = None,
) -> dict[str, Any]:
    """Conteo en dos dimensiones: categorias (eje) x series (colores). CERO tokens.

    Es lo que la GUI armaba con una peticion por fenomeno: `group_by` da las
    categorias y `serie_por` cuantas series hay. Se calcula aqui, una vez, sobre
    el mismo filtrado que `agregar`, para que las dos vistas de un dato jamas
    discrepen.

    Args:
        limite: tope de categorias (las de mayor total); no aplica al ano.
        serie_por: dimension que separa las series. None = una sola serie `total`.
            No puede coincidir con `group_by`.

    Returns:
        `{"categorias": [...], "series": [{"clave", "valores", "doc_ids"}],
        "total", "cobertura", "categorias_omitidas", "series_omitidas"}`.
        `valores[i]` y `doc_ids[i]` corresponden a `categorias[i]`. Las
        categorias van cronologicas si `group_by` es el ano y por total
        descendente en los demas casos; `doc_ids` es una muestra de 10.
    """
    if serie_por is not None and serie_por == group_by:
        raise ValueError("serie_por no puede ser igual a group_by")

    filas, dimensionado, universo = _seleccion(fenomenos, organizacion, desde, hasta)
    sin_dato = sum(1 for f in dimensionado if not _valor(f, group_by))

    peso = (lambda f: 1) if metrica == "conteo_documentos" else (lambda f: f["n_fragmentos"])
    por_categoria: dict[str, int] = defaultdict(int)
    celdas: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    muestras: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for fila in filas:
        categoria = _valor(fila, group_by)
        serie = _valor(fila, serie_por) if serie_por else "total"
        if not categoria or not serie:
            continue
        w = peso(fila)
        por_categoria[categoria] += w
        celdas[serie][categoria] += w
        if len(muestras[serie][categoria]) < 10:
            muestras[serie][categoria].append(fila["doc_id"])

    temporal = group_by == "anio"
    cuales = sorted(por_categoria, key=lambda c: (-por_categoria[c], c))
    omitidas = 0
    tope = min(MAX_CATEGORIAS, limite) if limite else MAX_CATEGORIAS
    if not temporal and len(cuales) > tope:
        omitidas = len(cuales) - tope
        cuales = cuales[:tope]
    categorias = sorted(cuales) if temporal else cuales

    por_serie = {s: sum(celdas[s].get(c, 0) for c in categorias) for s in celdas}
    # Las series de un fenomeno van en orden F1, F2, F3: el color de cada una no cambia entre vistas.
    orden = sorted(
        por_serie, key=(lambda s: s) if serie_por == "fenomeno" else (lambda s: (-por_serie[s], s))
    )
    series_omitidas = max(0, len(orden) - MAX_SERIES)
    orden = orden[:MAX_SERIES]

    return {
        "metrica": metrica,
        "group_by": group_by,
        "serie_por": serie_por,
        "categorias": categorias,
        "series": [
            {
                "clave": s,
                "valores": [celdas[s].get(c, 0) for c in categorias],
                "doc_ids": [muestras[s].get(c, []) for c in categorias],
            }
            for s in orden
        ],
        "total": sum(por_serie[s] for s in orden),
        "cobertura": {
            "documentos_universo": universo,
            "documentos_en_dimension": len(dimensionado),
            "documentos_contados": len(filas),
            "sin_dato_en_la_dimension": sin_dato,
            "excluidos_por_fecha": len(dimensionado) - len(filas),
        },
        "categorias_omitidas": omitidas,
        "series_omitidas": series_omitidas,
    }


#: Filas por pagina como maximo. Un documento pesa poco, pero una pagina sin tope
#: convierte "ver los documentos de esta barra" en volcar el corpus entero.
MAX_PAGINA = 100


def documentos(
    *,
    fenomenos: list[Fenomeno] | None = None,
    organizacion: str | None = None,
    formato: str | None = None,
    desde: int | None = None,
    hasta: int | None = None,
    limite: int = 25,
    offset: int = 0,
) -> dict[str, Any]:
    """Lista paginada de documentos, con los mismos filtros que `agregar`. CERO tokens.

    Existe porque cada fila de un agregado solo lleva una muestra de 10
    `doc_id`: para "ver todos los documentos de esta barra" hace falta la lista.
    Ordenada por `doc_id` para que la paginacion sea estable entre llamadas.

    Returns:
        `{"total", "siguiente", "filas", "excluidos_por_fecha"}`. `siguiente` es
        el `offset` de la pagina siguiente, o None en la ultima.
    """
    limite = max(1, min(int(limite), MAX_PAGINA))
    offset = max(0, int(offset))
    filas, dimensionado, _ = _seleccion(fenomenos, organizacion, desde, hasta, formato)
    filas = sorted(filas, key=lambda f: f["doc_id"])
    pagina = filas[offset : offset + limite]
    return {
        "total": len(filas),
        "siguiente": offset + limite if offset + limite < len(filas) else None,
        "filas": [
            {
                "doc_id": f["doc_id"],
                "organizacion": f.get("organizacion") or "",
                "anio": f.get("anio"),
                "formato": f.get("formato") or "",
                "fenomeno": f.get("fenomeno") or "",
                "fuente": f.get("fuente") or "",
                "n_fragmentos": f.get("n_fragmentos") or 0,
                "primer_chunk_id": f"{f['doc_id']}__chunk_000000",
            }
            for f in pagina
        ],
        "excluidos_por_fecha": len(dimensionado) - len(filas),
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
