"""El tablero desplegado no puede mostrar datos inventados.

`RETO.md` §Restricciones duras: "Datos reales en la version desplegada. No se
aceptan datos simulados o inventados en el tablero final". El prototipo del
tablero traia series, marcadores de mapa y nodos de relaciones de ejemplo que se
dibujaban al abrir, tambien en modo live. Esta prueba lo impide de forma
mecanica: si vuelven, la suite falla.

Los datos de demostracion del modo stub (`viewspec.datosSimulados`) SI se
permiten: solo se usan con `ARPIA_MODE=stub`, van marcados "Simulado" y el
servicio los avisa con un banner.
"""

from __future__ import annotations

from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[1] / "src" / "ui" / "static"

# Restos del prototipo: cifras, ciudades y nodos escritos a mano.
PROHIBIDO = (
    "PROVISIONAL",
    "Provisional",
    'data-origen="provisional"',
    "Datos de ejemplo",
    "Ubicaciones de ejemplo",
    "Relaciones de ejemplo",
    "País A",
    "Empresa B",
    "Bogotá",
    "Medellín",
)


@pytest.mark.parametrize("archivo", ["dashboard.html", "js/dashboard.js"])
def test_el_tablero_no_trae_datos_de_ejemplo(archivo):
    texto = (STATIC / archivo).read_text("utf-8")
    hallados = [p for p in PROHIBIDO if p in texto]
    assert not hallados, f"{archivo} contiene datos de ejemplo: {hallados}"


def test_el_tablero_no_depende_de_un_servidor_de_mapas_externo():
    """Sin lugar en el corpus no hay mapa; y una tesela externa fallaria sin internet."""
    for archivo in ("dashboard.html", "js/dashboard.js"):
        texto = (STATIC / archivo).read_text("utf-8").lower()
        assert "openstreetmap" not in texto, archivo
        assert "leaflet" not in texto and "L.map(" not in texto, archivo


def test_el_tablero_abre_con_las_vistas_del_corpus():
    """Al abrir, los paneles con datos se llenan desde el backend, no desde constantes."""
    js = (STATIC / "js" / "dashboard.js").read_text("utf-8")
    assert "VISTA_TIEMPO_INICIAL" in js and "VISTA_INICIAL" in js
    assert "inicial: true" in js
