"""El progreso en vivo del asistente del tablero no puede romper el turno ni inventar datos.

Verificaciones estaticas, como las del chat: vigilan las formas en que esto se estropearia sin que
nadie lo note mirandolo (un intervalo que sobrevive al turno, un color fuera de los tokens, una
carga externa).
"""

from __future__ import annotations

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "src" / "ui" / "static"
PROGRESO_JS = (STATIC / "js" / "progreso.js").read_text(encoding="utf-8")
DASHBOARD_JS = (STATIC / "js" / "dashboard.js").read_text(encoding="utf-8")


def test_el_sondeo_se_detiene_en_el_finally_del_turno():
    bloque = DASHBOARD_JS[DASHBOARD_JS.index("async function preguntar(") :]
    finally_ = bloque[bloque.index("} finally {") :]
    assert "seguimiento.detener()" in finally_, (
        "un intervalo que sobrevive al turno consulta para siempre"
    )


def test_el_seguimiento_arranca_antes_de_esperar_la_respuesta():
    bloque = DASHBOARD_JS[DASHBOARD_JS.index("async function preguntar(") :]
    assert bloque.index("seguirProgreso(") < bloque.index("await enviarChat(")


def test_un_fallo_del_progreso_no_escapa():
    consultar = PROGRESO_JS[PROGRESO_JS.index("async function consultar()") :]
    assert "catch {" in consultar[: consultar.index("const consultaId")]


def test_no_hay_colores_ni_cargas_externas():
    assert not re.search(r"#[0-9a-fA-F]{6}\b", PROGRESO_JS)
    assert "http" not in PROGRESO_JS.replace("GET /api/progress", "")


def test_solo_se_pintan_pasos_que_el_backend_reporto():
    """Sin estimaciones: ninguna barra de porcentaje ni pasos anunciados de antemano."""
    assert "%" not in re.sub(r"//.*", "", PROGRESO_JS)
    assert "obtenerProgreso(" in PROGRESO_JS
