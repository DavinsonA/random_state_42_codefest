"""Tools sobre el corpus documental.

Los nombres coinciden EXACTAMENTE con los declarados en `agent_card.json`.
No es cosmetica: `evaluacion.tools_called` reporta el nombre de la funcion, y
ADL evalua el bloque de diseno contra la agent card. Una tool que se llama de
una forma en la card y de otra en la traza es una inconsistencia detectable.

Plantilla de referencia: el docstring de cada funcion es el texto que lee el
modelo. Copien esta estructura al escribir tools nuevas el dia del evento.
"""

from __future__ import annotations

import os

from src.observability import turnlog
from src.retrieval.index import VectorIndex
from src.tools.registry import registry

_index: VectorIndex | None = None


def _get_index() -> VectorIndex:
    global _index
    if _index is None:
        _index = VectorIndex(os.getenv("VECTOR_INDEX_PATH", "data/encoder_bge_m3"))
    return _index


@registry.register(span_type="retrieval")
def buscar_corpus(query: str, k: int = 8) -> str:
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
    # Lo que ADL llama `retrieval_context`: el texto que se le entrego al modelo,
    # con su procedencia para que las citas del modelo tengan respaldo.
    turnlog.add_context([f"({hit.citation()}) {hit.text}" for hit in hits])
    turnlog.add_citations(
        [
            {
                "doc_id": hit.doc_id,
                "chunk_id": hit.chunk_id,
                "fuente": hit.metadata.get("organizacion") or hit.metadata.get("fuente"),
                "fragmento": hit.text[:240],
            }
            for hit in hits
        ]
    )
    return "\n\n".join(bloques)


@registry.register
def detalle_documento(doc_ids: list[str]) -> str:
    """Devuelve los metadatos conocidos de una lista de documentos.

    Usar para confirmar la procedencia de documentos ya identificados por una
    busqueda previa (fuente, formato, fenomeno asociado).

    NO usar para descubrir documentos nuevos: para eso esta `buscar_corpus`.

    Args:
        doc_ids: identificadores exactos, tal como los devolvio `buscar_corpus`.

    Returns:
        Una linea por documento con sus metadatos, o aviso de no encontrado.
    """
    vistos = _get_index().documents_meta(doc_ids)
    if not vistos:
        return f"Ningun documento encontrado para: {', '.join(doc_ids)}"

    return "\n".join(
        f"{did}: organizacion={row.get('organizacion', '?')} "
        f"anio={row.get('anio', 'no identificado')} "
        f"formato={row.get('formato', '?')} "
        f"fenomeno={row.get('fenomeno_nombre', '?')}"
        for did, row in vistos.items()
    )
