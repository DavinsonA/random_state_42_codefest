"""Adaptacion de los design tokens a Streamlit.

Streamlit expone solo un puñado de colores via `config.toml`. Todo lo demas
(jerarquia de superficies, bordes, densidad) exige CSS. Este modulo concentra
ese CSS en un solo lugar y lo deriva de los tokens, de modo que ningun archivo
de UI contenga un hexadecimal literal.

Limitacion conocida: los selectores `data-testid` de Streamlit pueden cambiar
entre versiones menores. Si el estilo se rompe tras actualizar Streamlit, el
culpable esta aqui y no en la UI. La version se fija en `pyproject.toml`.
"""

from __future__ import annotations

import streamlit as st

from src.theme.plotly_theme import register as register_plotly
from src.theme.tokens import tokens

_CSS = """
<style>
  :root {{
    --arpia-void: {void_};
    --arpia-bg: {bg};
    --arpia-surface: {surface};
    --arpia-elevated: {elevated};
    --arpia-border: {border};
    --arpia-border-active: {border_active};
    --arpia-text: {text};
    --arpia-text-secondary: {text_secondary};
    --arpia-primary: {primary};
    --arpia-evidence: {evidence};
  }}

  .stApp {{ background: var(--arpia-bg); }}

  section[data-testid="stSidebar"] {{
    background: var(--arpia-void);
    border-right: 1px solid var(--arpia-border);
  }}

  h1, h2, h3, h4 {{ color: var(--arpia-text); letter-spacing: -0.01em; }}
  p, li, label, span {{ color: var(--arpia-text-secondary); }}

  /* Superficie estandar: contenedores con borde. Densidad controlada,
     radio contenido (visual-system.md §11). */
  div[data-testid="stVerticalBlockBorderWrapper"] {{
    background: var(--arpia-surface);
    border: 1px solid var(--arpia-border);
    border-radius: 4px;
  }}

  div[data-testid="stMetric"] {{
    background: var(--arpia-surface);
    border: 1px solid var(--arpia-border);
    border-left: 2px solid var(--arpia-primary);
    border-radius: 3px;
    padding: 12px 14px;
  }}
  div[data-testid="stMetricValue"] {{ color: var(--arpia-text); }}

  .stTabs [data-baseweb="tab-list"] {{
    gap: 2px; border-bottom: 1px solid var(--arpia-border);
  }}
  .stTabs [aria-selected="true"] {{
    border-bottom: 2px solid var(--arpia-primary);
    color: var(--arpia-text);
  }}

  code, pre, .stCode {{
    background: var(--arpia-void) !important;
    border: 1px solid var(--arpia-border);
    border-radius: 3px;
  }}

  /* Ambar reservado para evidencia/citas (visual-system.md §7). */
  .arpia-evidence {{
    border-left: 2px solid var(--arpia-evidence);
    background: var(--arpia-surface);
    padding: 8px 12px;
    margin: 6px 0;
    border-radius: 0 3px 3px 0;
    font-size: 0.86rem;
  }}
  .arpia-meta {{
    font-family: ui-monospace, "SFMono-Regular", Menlo, monospace;
    font-size: 0.74rem;
    color: {muted};
  }}
</style>
"""


def apply(page_title: str = "A.R.P.I.A.", layout: str = "wide") -> None:
    """Configura la pagina, inyecta el CSS y registra el template de Plotly.

    Debe ser la primera llamada de Streamlit en `src/ui/app.py`.
    """
    st.set_page_config(page_title=page_title, layout=layout, initial_sidebar_state="expanded")
    st.markdown(
        _CSS.format(
            void_=tokens.foundation.void,
            bg=tokens.foundation.background,
            surface=tokens.foundation.surface,
            elevated=tokens.foundation.elevated,
            border=tokens.foundation.border,
            border_active=tokens.foundation.border_active,
            text=tokens.text.primary,
            text_secondary=tokens.text.secondary,
            muted=tokens.text.muted,
            primary=tokens.brand.primary,
            evidence=tokens.semantic.evidence,
        ),
        unsafe_allow_html=True,
    )
    register_plotly()


def evidence_block(text: str, meta: str = "") -> str:
    """HTML de un bloque de evidencia/cita. Devuelve markup, no lo renderiza.

    Args:
        text: fragmento citado.
        meta: identificador de procedencia (doc_id, pagina, fuente).
    """
    meta_html = f'<div class="arpia-meta">{meta}</div>' if meta else ""
    return f'<div class="arpia-evidence">{text}{meta_html}</div>'


def write_config_toml(path: str = ".streamlit/config.toml") -> None:
    """Genera `.streamlit/config.toml` desde los tokens. Idempotente."""
    from pathlib import Path

    content = f"""[theme]
base = "dark"
primaryColor = "{tokens.brand.primary}"
backgroundColor = "{tokens.foundation.background}"
secondaryBackgroundColor = "{tokens.foundation.surface}"
textColor = "{tokens.text.primary}"

[server]
headless = true
"""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
