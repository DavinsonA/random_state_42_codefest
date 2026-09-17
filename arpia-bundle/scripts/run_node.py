#!/usr/bin/env python
"""Ejecuta nodos o el grafo completo desde terminal, sin levantar la UI.

Es la herramienta principal de iteracion durante el evento: permite probar la
logica de un agente y leer su traza en segundos, en vez de esperar un reload
de Streamlit.

Importa `src` desde ../arpia (ARPIA_ROOT). Requiere las dependencias de
`arpia/pyproject.toml` instaladas: correr con `uv run --project ../arpia`
desde `arpia-bundle/`, o activar el venv de `arpia/` antes de invocarlo.

Ejemplos:
    python scripts/run_node.py --list
    python scripts/run_node.py retrieve --input "capacidades antisatelite 2024"
    python scripts/run_node.py tool search_corpus --input "deforestacion Guaviare"
    python scripts/run_node.py --graph --input "compara X e Y" --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

BUNDLE_ROOT = Path(__file__).resolve().parents[1]
# El paquete `src` vive en el repo hermano ../arpia; overrideable via
# ARPIA_ROOT para correr este script contra un checkout en otra ubicacion.
ARPIA_ROOT = Path(os.environ.get("ARPIA_ROOT", BUNDLE_ROOT.parent / "arpia")).resolve()
sys.path.insert(0, str(ARPIA_ROOT))

from src.config import get_logger  # noqa: E402
from src.tools.registry import registry  # noqa: E402

log = get_logger("run_node")


def cmd_retrieve(query: str, k: int) -> dict:
    """Recuperacion pura, sin LLM. Aisla la calidad del retriever."""
    from src.tools.corpus import _get_index

    index = _get_index()
    hits = index.search(query, k=k)
    return {
        "query": query,
        "documents": index.top_documents(hits, n=3),
        "fragments": [
            {"rank": i, "doc_id": h.doc_id, "chunk_id": h.chunk_id,
             "score": round(h.score, 4), "preview": h.text[:160]}
            for i, h in enumerate(hits, start=1)
        ],
    }


def cmd_tool(name: str, query: str) -> dict:
    """Invoca una tool aislada, tal como la llamaria el agente."""
    fn = registry.get(name)
    result = fn(query)
    return {"tool": name, "result": result, "trace": registry.trace()}


def cmd_graph(query: str) -> dict:
    """Ejecuta el grafo agentico completo y devuelve respuesta + traza."""
    from src.agents.graph import build_graph

    registry.reset()
    result = build_graph().invoke({"question": query, "turns": 0})
    return {
        "question": query,
        "answer": result.get("answer", ""),
        "turns": result.get("turns", 0),
        "trace": registry.trace(),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Ejecuta nodos de A.R.P.I.A. desde terminal")
    ap.add_argument("node", nargs="?", help="retrieve | tool")
    ap.add_argument("tool_name", nargs="?", help="nombre de la tool (con 'tool')")
    ap.add_argument("--input", "-i", default="", help="consulta de entrada")
    ap.add_argument("-k", type=int, default=8, help="numero de fragmentos")
    ap.add_argument("--graph", action="store_true", help="ejecuta el grafo completo")
    ap.add_argument("--list", action="store_true", help="lista nodos y tools disponibles")
    ap.add_argument("--json", action="store_true", help="salida JSON cruda")
    args = ap.parse_args()

    if args.list:
        import src.tools.corpus  # noqa: F401 - registra las tools

        print("nodos:  retrieve | tool | --graph")
        print(f"tools:  {', '.join(registry.names()) or '(ninguna registrada)'}")
        return 0

    if not args.input:
        ap.error("se requiere --input")

    import src.tools.corpus  # noqa: F401 - registra las tools

    start = time.perf_counter()
    if args.graph:
        out = cmd_graph(args.input)
    elif args.node == "retrieve":
        out = cmd_retrieve(args.input, args.k)
    elif args.node == "tool":
        if not args.tool_name:
            ap.error("'tool' requiere el nombre de la tool")
        out = cmd_tool(args.tool_name, args.input)
    else:
        ap.error(f"nodo desconocido: {args.node!r}. Usa --list.")

    elapsed = (time.perf_counter() - start) * 1000

    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        for key, value in out.items():
            if key == "fragments":
                print(f"\n{key}:")
                for f in value:
                    print(f"  [{f['rank']}] {f['doc_id']} ({f['score']}) {f['preview']}...")
            elif key == "trace":
                print(f"\n{key}: {json.dumps(value, ensure_ascii=False)}")
            else:
                print(f"{key}: {value}")
    print(f"\n-- {elapsed:.0f} ms", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
