"""Respuesta simulada para `ARPIA_MODE=stub`.

Existe para una sola cosa: poder desplegar y validar el contrato HTTP completo
antes de tener indice, gateway o agentes. La forma del JSON es IDENTICA a la de
modo `live` —mismos bloques, mismos tipos, mismo desglose de tokens— pero nada
de aqui toca `src.retrieval` ni el gateway del evento, y por tanto no consume
un solo token del presupuesto.

Todo lo que produce va marcado: `mode="stub"`, textos con el prefijo `[stub]` y
`metadata.estado="stub"`. `RETO.md` prohibe datos simulados en la version
desplegada; estas marcas son lo que hace imposible confundirlos con reales.

Determinista: la misma consulta produce siempre la misma respuesta.
"""

from __future__ import annotations

import hashlib
import re

from src.agents.card import model_for
from src.api.contracts import (
    AgentResponse,
    Citation,
    Evaluacion,
    Metadata,
    TokensPorAgente,
    ToolCall,
    ViewSpec,
)

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


def _fragmentos(texto: str, k: int = 3) -> list[dict[str, str]]:
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


def _tokens(agente: str, texto: str, factor: int) -> TokensPorAgente:
    """Cifras deterministas y plausibles. No son una estimacion de costo: en
    modo stub NO hubo llamada al modelo, y el desglose existe solo para que el
    consumidor del contrato vea el campo poblado."""
    base = len(texto) + 40
    entrada = base * factor
    salida = max(16, base // 2)
    return TokensPorAgente(
        agente=agente,
        modelo=model_for(agente),
        input=entrada,
        output=salida,
        total=entrada + salida,
    )


def stub_response(texto: str, *, latencia_ms: int = 0) -> AgentResponse:
    """Respuesta completa y bien formada, con datos simulados.

    Args:
        texto: consulta del usuario, ya saneada.
        latencia_ms: medida por el endpoint de extremo a extremo.
    """
    fragmentos = _fragmentos(texto)
    fenomenos = _fenomenos_mencionados(texto)
    con_vista = _quiere_vista(texto)

    agentes = ["orquestador", "agente_documental"]
    tools: list[ToolCall] = [
        ToolCall(
            name="buscar_corpus",
            input_parameters={"query": texto, "k": 3},
            output=f"{len(fragmentos)} fragmentos simulados",
        )
    ]
    desglose = [_tokens("orquestador", texto, 2), _tokens("agente_documental", texto, 6)]

    view_spec: ViewSpec | None = None
    if con_vista:
        agentes.append("agente_visualizador")
        view_spec = ViewSpec(
            chart="bar",
            fenomenos=fenomenos,  # type: ignore[arg-type]  # validado por Literal
            group_by="organizacion",
            titulo="[stub] Vista simulada",
            nota="Datos simulados: esta vista no proviene del corpus.",
        )
        tools.append(
            ToolCall(
                name="emitir_view_spec",
                input_parameters={"chart": "bar", "group_by": "organizacion"},
                output=view_spec.model_dump_json(),
            )
        )
        desglose.append(_tokens("agente_visualizador", texto, 3))

    respuesta = (
        "[stub] Esta instancia corre en modo simulado: no hay corpus, indice ni "
        "modelo conectados, asi que la respuesta no contiene informacion real "
        f"sobre {texto[:120]!r}. La estructura del JSON si es la definitiva. "
        "Para respuestas reales, el servicio debe desplegarse con ARPIA_MODE=live."
    )

    return AgentResponse(
        respuesta=respuesta,
        evaluacion=Evaluacion(
            input=texto,
            actual_output=respuesta,
            retrieval_context=[f["text"] for f in fragmentos],
            tools_called=tools,
        ),
        metadata=Metadata(
            # Coherente con el desglose: un agente simulado = una llamada
            # simulada. No hubo llamadas reales; `mode` y `estado` lo dicen.
            num_interacciones=len(desglose),
            agentes_invocados=agentes,
            tokens_por_agente=desglose,
            latencia_ms=latencia_ms,
            estado="stub",
        ),
        mode="stub",
        citations=[
            Citation(
                doc_id=f["doc_id"],
                chunk_id=f["chunk_id"],
                fuente=f["fuente"],
                fragmento=f["text"][:240],
            )
            for f in fragmentos
        ],
        view_spec=view_spec,
    )
