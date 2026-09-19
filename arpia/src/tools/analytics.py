"""Tools cuantitativas y de catalogo del tablero.

Los nombres coinciden EXACTAMENTE con los declarados en `agent_card.json`.
Ninguna de las dos cuesta tokens: operan sobre la tabla de metadata, en memoria.
"""

from __future__ import annotations

import json

from src.retrieval import aggregates
from src.tools.registry import registry


@registry.register
def consultar_agregado(
    metrica: str = "conteo_documentos",
    group_by: str = "fenomeno",
    fenomenos: str = "",
    organizacion: str = "",
    desde: str = "",
    hasta: str = "",
) -> str:
    """Cuenta documentos o fragmentos del corpus, agrupados por una dimension.

    Usar cuando la pregunta sea CUANTITATIVA sobre el corpus: cuantos documentos
    hay de un fenomeno, que organizacion publica mas, como se reparte el material
    por ano o por formato, comparaciones de volumen entre fenomenos.

    NO usar para preguntas de CONTENIDO —que dice, que afirma, que concluye un
    documento—: para eso esta `buscar_corpus`. Tampoco para inferir importancia o
    riesgo: esto cuenta documentos, y la cantidad de documentos sobre un tema no
    mide su gravedad. Presentarlo como si lo midiera esta prohibido.

    Args:
        metrica: "conteo_documentos" (cuantos documentos) o "conteo_fragmentos"
            (cuantos trozos indexados, util para medir volumen de texto).
        group_by: dimension de agrupacion. Una de: "fenomeno", "organizacion",
            "fuente", "formato", "anio".
        fenomenos: filtro, ids separados por coma: "F1", "F2,F3". Vacio = los tres.
        organizacion: filtro por organizacion exacta, tal como la devuelve
            `componentes_disponibles`. Vacio = todas.
        desde, hasta: rango de anos inclusive, formato "2024". Vacio = sin limite.
            Solo cubre el 34% de documentos que declaran ano.

    Returns:
        JSON con `filas` (clave, valor y una muestra de `doc_ids` que sustentan
        cada cifra), `total` y `cobertura`. La cobertura dice cuantos documentos
        quedaron fuera por no tener el dato: hay que reportarla, no esconderla.
    """
    lista = [f.strip().upper() for f in fenomenos.split(",") if f.strip()]
    resultado = aggregates.agregar(
        metrica=metrica,  # type: ignore[arg-type]
        group_by=group_by,  # type: ignore[arg-type]
        fenomenos=lista or None,  # type: ignore[arg-type]
        organizacion=organizacion or None,
        desde=int(desde) if desde.strip().isdigit() else None,
        hasta=int(hasta) if hasta.strip().isdigit() else None,
    )
    return json.dumps(resultado, ensure_ascii=False)


@registry.register
def componentes_disponibles() -> str:
    """Catalogo de lo que el tablero puede renderizar y con que datos.

    Usar SIEMPRE antes de emitir un `ViewSpec`: devuelve los componentes
    existentes y los valores reales de cada dimension. Proponer una vista que el
    tablero no puede poblar cuenta como fallo de ejecucion, no como una vista
    imperfecta.

    NO usar para responder al usuario: es informacion de configuracion interna,
    no contenido del corpus.

    Returns:
        JSON con `componentes`, `metricas`, `agrupaciones`, los valores
        observados de cada dimension y la cobertura temporal del corpus.
    """
    from src.api.contracts import ChartType, GroupBy, Metrica

    def _opciones(tipo) -> list[str]:
        return list(tipo.__args__)

    return json.dumps(
        {
            "componentes": _opciones(ChartType),
            "metricas": _opciones(Metrica),
            "agrupaciones": _opciones(GroupBy),
            "dimensiones": aggregates.dimensiones_disponibles(),
            "nota": (
                "No hay lugar, actor ni fecha exacta en el corpus: no existen mapas "
                "ni granularidad menor al ano. El ano cubre el 34% de los documentos."
            ),
        },
        ensure_ascii=False,
    )
