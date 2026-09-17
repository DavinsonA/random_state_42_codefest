"""Tools sobre el corpus documental.

Plantilla de referencia: el docstring de cada funcion es el texto que lee el
modelo. Copien esta estructura al escribir tools nuevas el dia del evento.
"""

from __future__ import annotations

import os

from src.retrieval.index import VectorIndex
from src.tools.registry import registry

_index: VectorIndex | None = None


def _get_index() -> VectorIndex:
    global _index
    if _index is None:
        _index = VectorIndex(os.getenv("VECTOR_INDEX_PATH", "data/base_vectorial/encoder_bge_m3"))
    return _index


@registry.register(span_type="retrieval")
def search_corpus(query: str, k: int = 8) -> str:
    """Busca fragmentos relevantes en el corpus documental indexado.

    Usar cuando la pregunta requiera evidencia textual del corpus: hechos,
    cifras, declaraciones, descripciones de eventos o de actores.

    NO usar para: calculos aritmeticos, consultas sobre la fecha actual, ni
    preguntas que ya quedaron respondidas por una llamada anterior en esta
    misma conversacion. Para comparar dos temas, hacer DOS busquedas separadas
    en vez de una sola consulta combinada: una consulta que mezcla dos temas
    recupera resultados superficiales de ambos.

    Args:
        query: consulta en lenguaje natural. Una sola idea por consulta.
            Se usa literal: no se traduce ni se expande.
        k: numero de fragmentos a devolver. Por defecto 8. Subir a 15-20 solo
            si las busquedas anteriores no trajeron evidencia suficiente.

    Returns:
        Texto con los fragmentos numerados, cada uno con su identificador de
        documento para poder citarlo. Si no hay resultados, lo indica
        explicitamente en vez de devolver texto vacio.
    """
    hits = _get_index().search(query, k=k)
    if not hits:
        return f"Sin resultados para la consulta: {query!r}"

    bloques = [
        f"[{i}] ({hit.citation()}) score={hit.score:.3f}\n{hit.text}"
        for i, hit in enumerate(hits, start=1)
    ]
    return "\n\n".join(bloques)


@registry.register
def list_documents(doc_ids: list[str]) -> str:
    """Devuelve los metadatos conocidos de una lista de documentos.

    Usar para confirmar la procedencia de documentos ya identificados por una
    busqueda previa (fuente, formato, fenomeno asociado).

    NO usar para descubrir documentos nuevos: para eso esta `search_corpus`.

    Args:
        doc_ids: identificadores exactos, tal como los devolvio `search_corpus`.

    Returns:
        Una linea por documento con sus metadatos, o aviso de no encontrado.
    """
    index = _get_index()
    index._load()  # noqa: SLF001 - acceso deliberado al cargador perezoso
    meta = index._meta or []  # noqa: SLF001

    wanted = set(doc_ids)
    vistos: dict[str, dict] = {}
    for row in meta:
        did = row.get("doc_id")
        if did in wanted and did not in vistos:
            vistos[did] = row

    if not vistos:
        return f"Ningun documento encontrado para: {', '.join(doc_ids)}"

    return "\n".join(
        f"{did}: fuente={row.get('fuente', '?')} formato={row.get('formato', '?')} "
        f"fenomeno={row.get('fenomeno', '?')}"
        for did, row in vistos.items()
    )
