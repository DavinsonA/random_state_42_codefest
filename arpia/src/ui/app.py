"""Interfaz de A.R.P.I.A.

Deliberadamente minima. `AGENTS.md` §6 prohibe construir un sistema de
componentes antes de conocer los requisitos funcionales: esta app aplica el
tema, expone una consulta y muestra evidencia con su procedencia. Nada mas.

Al conocer el reto, crecer AQUI segun lo que pida, no antes.
"""

from __future__ import annotations

import streamlit as st

from src.theme.streamlit_theme import apply, evidence_block
from src.theme.tokens import tokens

apply(page_title="A.R.P.I.A.")

with st.sidebar:
    st.markdown("### A.R.P.I.A.")
    st.caption("Analisis y Recuperacion para Procesamiento de Inteligencia Aeroespacial")
    st.divider()
    top_k = st.slider("Fragmentos a recuperar", 3, 20, 8)
    modo = st.radio("Modo", ["Recuperacion", "Analisis agentico"], index=0)
    st.divider()
    st.caption("Fenomenos")
    for key, meta in sorted(tokens.phenomena.items()):
        st.markdown(
            f'<span style="color:{meta["color"]}">&#9632;</span> '
            f'<span style="font-size:0.8rem">{key} — {meta["name"]}</span>',
            unsafe_allow_html=True,
        )

st.title("Analisis de fuentes abiertas")

query = st.text_input("Consulta", placeholder="Escribe una pregunta sobre el corpus...")

if query:
    if modo == "Recuperacion":
        from src.tools.corpus import _get_index

        with st.spinner("Recuperando..."):
            hits = _get_index().search(query, k=top_k)

        col_a, col_b = st.columns([1, 1])
        col_a.metric("Fragmentos", len(hits))
        col_b.metric("Documentos", len({h.doc_id for h in hits}))

        st.subheader("Evidencia")
        for hit in hits:
            st.markdown(
                evidence_block(hit.text[:600], meta=f"{hit.citation()} · score {hit.score:.3f}"),
                unsafe_allow_html=True,
            )
    else:
        from src.agents.graph import build_graph
        from src.tools.registry import registry

        registry.reset()
        with st.spinner("Analizando..."):
            result = build_graph().invoke({"question": query, "turns": 0})

        st.subheader("Respuesta")
        st.write(result.get("answer", ""))

        with st.expander("Traza de ejecucion"):
            st.json(registry.trace())
else:
    st.caption("Introduce una consulta para comenzar.")
