"""Endpoints de soporte del tablero (Reto 2).

Los consume el HTML estatico de `static/`, que mantiene otra sesion. No los
evalua ADL directamente —lo que se evalua es que el tablero muestre el
componente correcto con los datos correctos— pero son la unica via por la que
esos datos llegan al navegador.

Dos reglas, las mismas que en `/chat`:

- **Ninguno devuelve 500.** Un fallo se reporta dentro de un 200 con
  `disponible: false` y su motivo. Un 500 en el tablero durante la demo se ve
  igual que un despliegue caido.
- **Todo dato es rastreable.** Cada cifra viene con los `doc_id` que la
  sustentan, y `/api/evidence/{chunk_id}` devuelve el fragmento exacto. Es el
  requisito de trazabilidad de `RETO.md`, y es lo que permite que un experto
  cuestione un numero y llegue a su fuente en dos clics.

Cero tokens: todo sale de la tabla de metadata y del indice local.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from src.config import get_logger
from src.observability import tracing

log = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["tablero"])


def _error(motivo: str, **extra: Any) -> JSONResponse:
    """Degradacion legible. Siempre 200: el tablero distingue 'no hay dato' de
    'el servicio se cayo', y un 404 no permite esa distincion."""
    return JSONResponse(status_code=200, content={"disponible": False, "motivo": motivo, **extra})


@router.get("/components")
def components() -> JSONResponse:
    """Catalogo de componentes y dimensiones con datos reales detras.

    Lo consulta el tablero al arrancar para saber que puede pintar, y el agente
    visualizador antes de emitir un `ViewSpec`.
    """
    try:
        import json

        from src.tools.analytics import componentes_disponibles

        return JSONResponse(content=json.loads(componentes_disponibles()))
    except Exception as exc:  # noqa: BLE001 - el tablero nunca recibe un 500
        log.warning("catalogo no disponible: %s", exc)
        return _error(f"catalogo no disponible: {type(exc).__name__}")


@router.get("/aggregate")
def aggregate(
    metrica: str = Query("conteo_documentos"),
    group_by: str = Query("fenomeno"),
    fenomenos: str = Query("", description='Ids separados por coma: "F1,F2"'),
    organizacion: str = Query(""),
    desde: int | None = Query(None),
    hasta: int | None = Query(None),
    limite: int = Query(25, ge=1, le=100),
) -> JSONResponse:
    """Conteo agregado sobre la tabla de documentos.

    Es el endpoint que puebla casi todo el tablero. Devuelve tambien `cobertura`:
    cuantos documentos quedaron fuera por no tener el dato de la dimension
    pedida. Ese numero se muestra, no se esconde.
    """
    try:
        from src.retrieval import aggregates

        lista = [f.strip().upper() for f in fenomenos.split(",") if f.strip()]
        datos = aggregates.agregar(
            metrica=metrica,  # type: ignore[arg-type]
            group_by=group_by,  # type: ignore[arg-type]
            fenomenos=lista or None,  # type: ignore[arg-type]
            organizacion=organizacion or None,
            desde=desde,
            hasta=hasta,
            limite=limite,
        )
        return JSONResponse(content={"disponible": True, **datos})
    except Exception as exc:  # noqa: BLE001
        log.warning("agregacion fallida: %s", exc)
        return _error(f"agregacion no disponible: {type(exc).__name__}")


@router.get("/timeline")
def timeline(
    fenomenos: str = Query(""),
    desde: int | None = Query(None),
    hasta: int | None = Query(None),
) -> JSONResponse:
    """Serie anual de documentos.

    Granularidad anual porque es la unica que el corpus sostiene, y con la
    cobertura por delante: solo el 34% de los documentos declara ano. Una linea
    de tiempo que oculte eso convierte un conteo honesto en una cifra enganosa.
    """
    try:
        from src.retrieval import aggregates

        lista = [f.strip().upper() for f in fenomenos.split(",") if f.strip()]
        datos = aggregates.agregar(
            group_by="anio",
            fenomenos=lista or None,  # type: ignore[arg-type]
            desde=desde,
            hasta=hasta,
            limite=100,
        )
        filas = sorted(datos["filas"], key=lambda f: f["clave"])
        cobertura = datos["cobertura"]
        return JSONResponse(
            content={
                "disponible": True,
                "granularidad": "anio",
                "filas": filas,
                "total": datos["total"],
                "cobertura": cobertura,
                "aviso": (
                    f"{cobertura['sin_dato_en_la_dimension']} de "
                    f"{cobertura['documentos_en_dimension']} documentos no declaran ano "
                    "y no aparecen en esta serie."
                ),
            }
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("linea de tiempo fallida: %s", exc)
        return _error(f"linea de tiempo no disponible: {type(exc).__name__}")


@router.get("/geo")
def geo() -> JSONResponse:
    """Datos geograficos. **No disponibles, y es un hecho del corpus.**

    La metadata tiene ocho campos: `doc_id`, `chunk_id`, `fuente`, `formato`,
    `fenomeno`, `posicion`, `num_tokens` y `texto`. No hay lugar, ni pais, ni
    coordenadas. Extraerlos del texto exigiria procesar 326.866 fragmentos con
    un modelo, que no cabe en el presupuesto ni en el reloj.

    Existe y responde 200 a proposito: el tablero puede preguntar y recibir un
    "no hay dato" explicito, en vez de un 404 que se confunde con un fallo de
    despliegue. Inventar una ubicacion seria peor que las dos cosas, y
    `RETO.md` lo prohibe.
    """
    return _error(
        "el corpus no contiene ubicacion: la metadata no tiene lugar, pais ni coordenadas",
        alternativa=(
            "para analisis geografico se puede agrupar por organizacion, que es un "
            "dato real del corpus, pero indica quien publica y no donde ocurre"
        ),
    )


@router.get("/evidence/{chunk_id}")
def evidence(chunk_id: str) -> JSONResponse:
    """El fragmento exacto detras de una cita.

    Es lo que convierte una cita en evidencia verificable: el experto hace clic
    en `F2-SWF-120` y lee el texto que sustenta la afirmacion, con su
    procedencia. `RETO.md` lo exige para todo dato mostrado.
    """
    try:
        from src.tools.corpus import _get_index

        fila = _get_index().chunk(chunk_id)
    except Exception as exc:  # noqa: BLE001
        log.warning("evidencia no accesible: %s", exc)
        return _error(f"indice no disponible: {type(exc).__name__}", chunk_id=chunk_id)

    if fila is None:
        return _error("fragmento no encontrado", chunk_id=chunk_id)

    return JSONResponse(
        content={
            "disponible": True,
            "chunk_id": fila.get("chunk_id"),
            "doc_id": fila.get("doc_id"),
            "texto": fila.get("texto", ""),
            "fuente": fila.get("fuente", ""),
            "organizacion": fila.get("organizacion", ""),
            "anio": fila.get("anio"),
            "formato": fila.get("formato", ""),
            "fenomeno": fila.get("fenomeno_id", ""),
            "fenomeno_nombre": fila.get("fenomeno_nombre", ""),
        }
    )


@router.get("/trace/{trace_id}")
def trace(trace_id: str) -> JSONResponse:
    """Arbol de ejecucion de un turno: que se llamo, con que y cuanto tardo.

    Se conservan las ultimas trazas en memoria. Sirve para explicar una
    respuesta rara **despues** de que ocurrio, que es cuando siempre hace falta.
    """
    spans = tracing.get_trace(trace_id)
    if spans is None:
        return _error("traza no disponible (solo se conservan las mas recientes)")
    return JSONResponse(content={"disponible": True, "trace_id": trace_id, "spans": spans})
