"""Chart.js: `defaults.animation` se muta, nunca se reemplaza.

Sustituir el objeto entero borraba la configuracion por defecto de las animaciones de color y cada
grafico lanzaba `this._fn is not a function` al animar `backgroundColor`/`borderColor`.
"""

from __future__ import annotations

import re
from pathlib import Path

DASHBOARD_JS = Path(__file__).resolve().parents[1] / "src/ui/static/js/dashboard.js"


def test_defaults_animation_no_se_reemplaza_por_un_objeto():
    fuente = DASHBOARD_JS.read_text(encoding="utf-8")
    reemplazos = re.findall(r"Chart\.defaults\.animation\s*=\s*([^;]+);", fuente)
    assert reemplazos == ["false"], (
        "solo se admite desactivar la animacion (`= false`); para ajustarla, "
        f"mutar `Chart.defaults.animation.duration`: {reemplazos}"
    )
