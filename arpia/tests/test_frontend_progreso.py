"""El progreso en vivo del chat no puede romper el turno ni inventar datos.

Verificaciones estaticas sobre `js/chat.js`, `js/api.js` y `css/app.css`. Son
mecanicas a proposito: lo que vigilan son justo las cuatro formas en que esta
funcionalidad se estropearia sin que nadie lo note al mirarla —un intervalo que
sobrevive al turno, un paso inventado, una carga externa nueva y un color fuera
del sistema de tokens—.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[1] / "src" / "ui" / "static"
CHAT_JS = (STATIC / "js" / "chat.js").read_text(encoding="utf-8")
API_JS = (STATIC / "js" / "api.js").read_text(encoding="utf-8")
APP_CSS = (STATIC / "css" / "app.css").read_text(encoding="utf-8")


def test_el_polling_se_detiene_en_el_finally_del_turno():
    """Un intervalo que sobrevive al turno consulta para siempre una sesion que
    ya termino, y nadie lo ve hasta que la pestana lleva una hora abierta."""
    bloque = CHAT_JS[CHAT_JS.index("async function enviar(") :]
    finally_ = bloque[bloque.index("} finally {") :]
    assert "detenerProgreso()" in finally_, "el polling no se detiene al terminar el turno"


def test_seguir_progreso_limpia_los_dos_intervalos():
    """Son dos: el cronometro y la consulta. Olvidar uno deja medio adorno vivo."""
    cuerpo = CHAT_JS[CHAT_JS.index("function seguirProgreso(") :]
    cuerpo = cuerpo[: cuerpo.index("\n}\n")]
    assert cuerpo.count("setInterval(") == cuerpo.count("clearInterval(") == 2


def test_solo_se_pintan_pasos_que_el_backend_reporto():
    """Prohibido simular pasos con temporizadores o estimar porcentajes: una
    barra de progreso inventada es un dato inventado con otra forma."""
    cuerpo = CHAT_JS[CHAT_JS.index("function seguirProgreso(") :]
    cuerpo = cuerpo[: cuerpo.index("\n}\n")]
    assert "datos.pasos" in cuerpo, "los pasos deben venir del backend"
    for prohibido in ("porcentaje", "estimad", "Math.random", "progress-bar"):
        assert prohibido not in cuerpo, f"rastro de progreso simulado: {prohibido}"


def test_el_bloque_en_vivo_se_anuncia_a_lectores_de_pantalla():
    assert 'setAttribute("aria-live", "polite")' in CHAT_JS


def test_el_estado_no_depende_solo_del_color():
    """Cada paso lleva su etiqueta de texto y su duracion, no un semaforo."""
    assert "etiquetaDePaso(paso.nombre)" in CHAT_JS
    assert "duracion_ms" in CHAT_JS


def test_se_respeta_prefers_reduced_motion():
    bloque = APP_CSS[APP_CSS.index("@media (prefers-reduced-motion: reduce)") :]
    assert ".progreso-paso { animation: none; }" in bloque


def test_el_progreso_no_usa_colores_fuera_de_los_tokens():
    """Si un color no esta en tokens.css, no existe."""
    bloque = APP_CSS[APP_CSS.index("/* -- progreso en vivo") :]
    bloque = bloque[: bloque.index("@media (prefers-reduced-motion")]
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", bloque), "hexadecimal suelto en el progreso"


#: Lo que parece una URL y no es una carga de red.
#:
#: `w3.org/2000/svg` es el namespace XML que exige `createElementNS`, no una
#: descarga; `localhost` son las direcciones de desarrollo que la interfaz
#: reconoce para ofrecer el enlace al tablero. Ninguna sale a internet en el
#: despliegue, que es lo que esta prueba protege.
_NO_SON_CARGAS = ("w3.org/2000/svg", "localhost")


def test_no_se_anaden_cargas_externas():
    """El contenedor sirve todo; una CDN nueva es una dependencia de red en la
    ventana de evaluacion. Lo descubrio de verdad: el tablero cargaba tiles de
    `tile.openstreetmap.org` para un mapa que el corpus no puede sostener."""
    for archivo in (STATIC / "js").glob("*.js"):
        texto = archivo.read_text(encoding="utf-8")
        for url in re.findall(r"https?://[^\s\"')]+", texto):
            if any(permitida in url for permitida in _NO_SON_CARGAS):
                continue
            pytest.fail(f"URL externa en {archivo.name}: {url}")


def test_solo_api_js_habla_con_el_backend():
    """`pedir()` centraliza timeouts y errores; un fetch suelto se los salta."""
    assert "fetch(" not in CHAT_JS
    assert "obtenerProgreso" in API_JS and "obtenerProgreso" in CHAT_JS


def test_el_progreso_tiene_timeout_propio_y_corto():
    """No puede competir por la conexion con el turno que describe."""
    bloque = API_JS[API_JS.index("export function obtenerProgreso") :]
    bloque = bloque[: bloque.index("\n}")]
    assert "timeoutMs" in bloque
