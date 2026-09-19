"""Corre las pruebas de JavaScript de las referencias (`tests/js`) dentro de pytest.

La logica pura del tooltip y del visor (partir el texto por `doc_id`, describir
una cita, paginar) vive en `src/ui/static/js/referencias.js` y se prueba con el
ejecutor de Node, sin dependencias. Si Node no esta instalado se omite: el
backend no lo necesita, solo esta verificacion del frontend.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("node") is None, reason="Node no esta instalado")
def test_las_pruebas_js_de_las_referencias_pasan():
    r = subprocess.run(
        ["node", "--test", "tests/js/*.test.mjs"],  # Node expande el patron (Windows y Linux)
        cwd=RAIZ,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-1000:]
