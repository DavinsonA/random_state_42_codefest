"""Turno simulado para `ARPIA_MODE=stub`.

Existe para una sola cosa: poder desplegar y validar el contrato HTTP completo
antes de tener indice, gateway o agentes. La forma del JSON es IDENTICA a la de
modo `live` —mismos bloques, mismos tipos, mismo desglose— pero nada de aqui
toca `src.retrieval` ni el gateway del evento, y por tanto no consume un solo
token del presupuesto.

Escribe en `turnlog` y `usage` exactamente como lo harian los agentes reales,
para que `src/api/chat.py` no necesite un camino especial: arma la respuesta
leyendo el registro del turno, venga de donde venga.

**Los tokens quedan en cero, no en cifras inventadas.** No hubo llamada al
modelo; `num_interacciones` cuenta los agentes simulados porque esa es la
trayectoria, pero declarar un consumo que no ocurrio seria falsear el Bloque B.

Todo lo que produce va marcado: `mode="stub"`, `estado="stub"` y textos con el
prefijo `[stub]`. `RETO.md` prohibe datos simulados en la version desplegada;
estas marcas son lo que hace imposible confundirlos con reales.
"""

from __future__ import annotations

import hashlib
import re

from src.agents.card import model_for
from src.api.contracts import ViewSpec
from src.observability import turnlog, usage

# Intencion de visualizacion. Lista deliberadamente corta: en modo stub solo
# sirve para ejercitar las DOS ramas del contrato (con y sin `view_spec`).
# El enrutamiento real lo decide el orquestador (Fase 3), no una lista de
# palabras.
_PALABRAS_VISTA = (
    "grafica",
    "grafico",
    "graficar",
    "mapa",
    "mapea",
    "muestra",
    "muestrame",
    "visualiza",
    "tablero",
    "dashboard",
    "compara",
    "evolucion",
    "tendencia",
    "linea de tiempo",
)

_FENOMENOS = {
    "F1": ("ia", "inteligencia artificial", "militar", "capacidades estrategicas"),
    "F2": ("espacial", "satelite", "orbita", "leo", "espacio"),
    "F3": ("territorial", "frontera", "territorio", "america latina"),
}


def _seed(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)


def _quiere_vista(texto: str) -> bool:
    bajo = texto.lower()
    return any(p in bajo for p in _PALABRAS_VISTA)


def _fenomenos_mencionados(texto: str) -> list[str]:
    """Coincidencia por palabra completa, no por subcadena: "ia" dentro de
    "espacial" no es una mencion al fenomeno de IA."""
    bajo = texto.lower()
    return [
        f
        for f, claves in _FENOMENOS.items()
        if any(re.search(rf"\b{re.escape(c)}\b", bajo) for c in claves)
    ]


def stub_fragments(texto: str, k: int = 3) -> list[dict[str, str]]:
    """Fragmentos con la misma forma que `Hit` en `src/retrieval/index.py`."""
    seed = _seed(texto)
    return [
        {
            "chunk_id": f"stub-chunk-{seed % 1000}-{i}",
            "doc_id": f"stub-doc-{(seed + i) % 100}",
            "fuente": "fuente simulada",
            "text": (
                f"[stub] Fragmento {i} generado en modo simulado para la consulta "
                f"{texto[:80]!r}. No proviene del indice real del corpus."
            ),
        }
        for i in range(1, k + 1)
    ]


def stub_answer(texto: str) -> str:
    """Texto de respuesta simulado, siempre marcado como tal."""
    return (
        "[stub] Esta instancia corre en modo simulado: no hay corpus, indice ni "
        "modelo conectados, asi que la respuesta no contiene informacion real "
        f"sobre {texto[:120]!r}. La estructura del JSON si es la definitiva. "
        "Para respuestas reales, el servicio debe desplegarse con ARPIA_MODE=live."
    )


def stub_turn(texto: str) -> tuple[str, ViewSpec | None, str]:
    """Ejecuta un turno simulado completo.

    Anota en `turnlog` y `usage` lo mismo que anotarian los agentes reales.

    Returns:
        `(respuesta, view_spec, estado)`.
    """
    fragmentos = stub_fragments(texto)
    turnlog.add_context([f["text"] for f in fragmentos])
    turnlog.add_citations(
        [
            {
                "doc_id": f["doc_id"],
                "chunk_id": f["chunk_id"],
                "fuente": f["fuente"],
                "fragmento": f["text"][:240],
            }
            for f in fragmentos
        ]
    )
    turnlog.record_tool_call(
        "buscar_corpus", {"query": texto, "k": 3}, f"{len(fragmentos)} fragmentos simulados"
    )
    usage.record_usage(None, agent="orquestador", model=model_for("orquestador"))
    usage.record_usage(None, agent="agente_documental", model=model_for("agente_documental"))

    view_spec: ViewSpec | None = None
    if _quiere_vista(texto):
        view_spec = ViewSpec(
            chart="bar",
            fenomenos=_fenomenos_mencionados(texto),  # type: ignore[arg-type]
            group_by="organizacion",
            titulo="[stub] Vista simulada",
            nota="Datos simulados: esta vista no proviene del corpus.",
        )
        turnlog.record_tool_call(
            "emitir_view_spec",
            {"chart": "bar", "group_by": "organizacion"},
            view_spec.model_dump_json(),
        )
        usage.record_usage(
            None, agent="agente_visualizador", model=model_for("agente_visualizador")
        )

    return stub_answer(texto), view_spec, "stub"
