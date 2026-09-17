"""Template de Plotly derivado de los design tokens de A.R.P.I.A.

Aplica la seccion 13 de `visual-system.md`: colores semanticos consistentes,
escalas secuenciales para magnitud, divergentes solo cuando la variable tiene
negativo/neutro/positivo con significado.
"""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

from src.theme.tokens import tokens

TEMPLATE_NAME = "arpia"

# Escala secuencial para magnitud: del fondo profundo al cian de marca.
SEQUENTIAL = [
    tokens.foundation.elevated,
    tokens.brand.deep,
    tokens.brand.primary,
    tokens.brand.space,
]

# Divergente: critico -> neutro -> operacional. Usar SOLO con variables que
# tengan negativo, neutro y positivo con significado real (visual-system.md §13).
DIVERGING = [tokens.semantic.critical, tokens.foundation.elevated, tokens.semantic.success]


def _axis() -> dict:
    return {
        "gridcolor": tokens.foundation.border,
        "zerolinecolor": tokens.foundation.border_active,
        "linecolor": tokens.foundation.border_active,
        "tickfont": {"color": tokens.text.secondary, "size": 11},
        "title": {"font": {"color": tokens.text.secondary, "size": 12}},
    }


def build_template() -> go.layout.Template:
    """Construye el template de Plotly a partir de los tokens."""
    return go.layout.Template(
        layout={
            "paper_bgcolor": tokens.foundation.background,
            "plot_bgcolor": tokens.foundation.surface,
            "font": {"color": tokens.text.primary, "size": 12},
            "title": {"font": {"color": tokens.text.primary, "size": 16}, "x": 0.01},
            "colorway": tokens.categorical_sequence,
            "colorscale": {"sequential": SEQUENTIAL, "diverging": DIVERGING},
            "xaxis": _axis(),
            "yaxis": _axis(),
            "legend": {
                "bgcolor": "rgba(0,0,0,0)",
                "bordercolor": tokens.foundation.border,
                "font": {"color": tokens.text.secondary, "size": 11},
            },
            "hoverlabel": {
                "bgcolor": tokens.foundation.elevated,
                "bordercolor": tokens.foundation.border_active,
                "font": {"color": tokens.text.primary, "size": 12},
            },
            "margin": {"l": 56, "r": 24, "t": 48, "b": 48},
        }
    )


def register(as_default: bool = True) -> None:
    """Registra el template en Plotly. Llamar una vez al arrancar la app."""
    pio.templates[TEMPLATE_NAME] = build_template()
    if as_default:
        pio.templates.default = TEMPLATE_NAME


def color_for_phenomenon(key: str) -> str:
    """Atajo semantico para colorear una serie por fenomeno (F1/F2/F3)."""
    return tokens.phenomenon(key)
