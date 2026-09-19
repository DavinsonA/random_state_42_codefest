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
from src.retrieval.enrich import fenomeno_numero
from src.retrieval.index import Hit, VectorIndex
from src.tools.registry import registry

#: Candidatos que se piden al indice antes de filtrar. `IndexFlatIP` recorre
#: los 326.866 vectores sea cual sea `k`, asi que pedir 40 cuesta 2 ms mas que
#: pedir 8 (medido) y deja margen para filtrar por fenomeno sin perder recall.
SOBRE_RECUPERAR = 40

_index: VectorIndex | None = None


def _get_index() -> VectorIndex:
    global _index
    if _index is None:
        _index = VectorIndex(os.getenv("VECTOR_INDEX_PATH", "data/encoder_bge_m3"))
    return _index


def recuperar(
    query: str, k: int = 8, fenomeno: str | None = None, *, registrar_tool: bool = True
) -> list[Hit]:
    """Recupera fragmentos y DEJA CONSTANCIA en el registro del turno.

    Punto unico de recuperacion del sistema. Todo lo que busque en el corpus
    pasa por aqui, y por eso `evaluacion.retrieval_context` nunca sale vacio
    cuando hubo RAG: si un ejecutor llamara al indice por su cuenta, ADL veria
    una respuesta con citas y sin contexto recuperado, y Faithfulness —el 30%
    del bloque de calidad— se calcula contra ese campo.

    Cero tokens: FAISS y el encoder corren en la CPU del contenedor.

    Args:
        query: consulta en lenguaje natural, usada literal.
        k: fragmentos a devolver despues de filtrar.
        fenomeno: "F1" | "F2" | "F3" para sesgar el resultado, o None.
        registrar_tool: anota la busqueda en `tools_called`. La tool registrada
            `buscar_corpus` pasa False porque el registry ya la anota, y dos
            entradas por una sola busqueda falsearian la trayectoria.

    Returns:
        Lista de `Hit` ordenada por similitud descendente.
    """
    hits = _get_index().search(query, k=max(k, SOBRE_RECUPERAR))

    numero = fenomeno_numero(fenomeno) if fenomeno else None
    if numero is not None:
        filtrados = [h for h in hits if h.metadata.get("fenomeno") == numero]
        # Filtro BLANDO: el fenomeno es una pista, no una llave. Medido sobre el
        # corpus, el recuperador ya acierta el fenomeno el 88% de las veces sin
        # ayuda, y hay temas legitimamente transversales que un filtro duro
        # haria desaparecer sin que el usuario se entere.
        hits = filtrados or hits
    hits = hits[:k]

    # ADL evalua la trayectoria a partir de `tools_called`. Una recuperacion que
    # no deja rastro ahi se lee como una respuesta salida de la nada.
    if registrar_tool:
        turnlog.record_tool_call(
            "buscar_corpus",
            {"query": query, "k": k, "fenomeno": fenomeno or ""},
            f"{len(hits)} fragmentos recuperados"
            + (f" (mejor score {hits[0].score:.3f})" if hits else ""),
        )

    # Lo que ADL llama `retrieval_context`: el texto que se le entrego al modelo,
    # con su procedencia para que las citas tengan respaldo.
    turnlog.add_context([f"({h.citation()}) {h.text}" for h in hits])
    turnlog.add_citations(
        [
            {
                "doc_id": h.doc_id,
                "chunk_id": h.chunk_id,
                "fuente": h.metadata.get("organizacion") or h.metadata.get("fuente"),
                "fragmento": h.text[:240],
            }
            for h in hits
        ]
    )
    return hits


def citar_documentos(doc_ids: list[str]) -> list[dict]:
    """Deja constancia de documentos concretos del corpus como citas del turno.

    Es el equivalente de `recuperar` para las cifras: un conteo por
    organizacion no recupera fragmentos, pero cada cifra descansa sobre
    documentos reales. `RETO.md` exige que todo dato mostrado se rastree a su
    `doc_id` y `chunk_id`; sin esto, una respuesta cuantitativa salia con
    `citations` vacio aunque el sistema conocia los documentos detras de cada
    numero.

    Para cada documento registra su PRIMER fragmento, con su texto real: es la
    evidencia textual que un experto puede abrir (`GET /api/evidence/{chunk_id}`).

    **No fuerza la carga del indice.** Un indice sin cargar son 1,3 GB y varios
    segundos; en produccion ya esta cargado, porque la tabla de agregados sale de
    el. Si no lo esta, o si falla, devuelve `[]`: una cita que no se pudo obtener
    no debe tumbar un conteo exacto.

    Args:
        doc_ids: identificadores de documento (`F2-CSIS-014`).

    Returns:
        Las citas registradas, en el orden pedido. Vacia si no fue posible.
    """
    if not doc_ids:
        return []
    try:
        indice = _get_index()
        if not indice.stats():
            return []
        filas = indice.documents_meta(doc_ids)
    except Exception:  # noqa: BLE001 - una cita ausente no debe tumbar el conteo
        return []

    citas = [
        {
            "doc_id": d,
            "chunk_id": filas[d]["chunk_id"],
            "fuente": filas[d].get("organizacion") or filas[d].get("fuente"),
            "fragmento": str(filas[d].get("texto", ""))[:240],
        }
        for d in doc_ids
        if d in filas and filas[d].get("chunk_id")
    ]
    turnlog.add_citations(citas)
    return citas


@registry.register(span_type="retrieval")
def buscar_corpus(query: str, k: int = 8, fenomeno: str = "") -> str:
    """Busca fragmentos relevantes en el corpus documental indexado.

    Usar cuando la pregunta requiera evidencia textual del corpus: hechos,
    cifras, declaraciones, descripciones de eventos o de actores.

    NO usar para: conteos ni distribuciones —para eso esta `consultar_agregado`,
    que da cifras exactas mientras que contar por busqueda semantica produce
    numeros que parecen correctos y no lo son—; calculos aritmeticos; la fecha
    actual; ni preguntas ya respondidas por una llamada anterior de este mismo
    turno. Para comparar dos temas, hacer DOS busquedas separadas: una consulta
    que mezcla dos temas recupera resultados superficiales de ambos.

    Args:
        query: consulta en lenguaje natural. Una sola idea por consulta. Se usa
            literal: no se traduce ni se expande.
        k: numero de fragmentos a devolver. Por defecto 8. Subir a 15-20 solo si
            las busquedas anteriores no trajeron evidencia suficiente.
        fenomeno: "F1" (IA y capacidades estrategicas), "F2" (seguridad del
            entorno espacial) o "F3" (dinamicas territoriales) para sesgar la
            busqueda. Vacio busca en los tres, que es lo correcto salvo que la
            pregunta acote el tema de forma explicita.

    Returns:
        Texto con los fragmentos numerados, cada uno con su identificador de
        documento para poder citarlo. Si no hay resultados, lo indica
        explicitamente en vez de devolver texto vacio.
    """
    hits = recuperar(query, k=k, fenomeno=fenomeno or None, registrar_tool=False)
    if not hits:
        return f"Sin resultados para la consulta: {query!r}"
    return "\n\n".join(
        f"[{i}] ({hit.citation()}) score={hit.score:.3f}\n{hit.text}"
        for i, hit in enumerate(hits, start=1)
    )


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
