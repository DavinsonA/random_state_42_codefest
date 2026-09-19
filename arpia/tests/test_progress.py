"""`GET /api/progress`: qué agentes van corriendo, sin publicar su contenido.

El endpoint existe para que la interfaz pueda mostrar en vivo por dónde va un
turno que tarda decenas de segundos. Queda **abierto en producción**, y de ahí
sale la prueba más importante de este archivo.

`GET /api/trace` está cerrado tras `ARPIA_DEBUG_TRACE` porque los spans llevan
en `input` y `output` el texto de las preguntas y los fragmentos recuperados del
corpus. Si `/api/progress` devolviera esos campos, estaríamos publicando por la
puerta de atrás —en la URL pública de la evaluación— justo lo que se cerró a
propósito. La proyección no se limita a omitirlos: se construye campo por campo
desde una lista blanca, de modo que un campo nuevo en `Span` no pueda colarse
solo.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from src import config
from src.api.main import app
from src.observability import tracing

#: Texto que solo puede salir del contenido de un span. Si aparece en la
#: respuesta, hay fuga.
PREGUNTA = "cuantos satelites lanzo el pais X en 2024 segun el corpus"
FRAGMENTO = "Segun SWF Counterspace, las operaciones de proximidad en orbita geoestacionaria"


@pytest.fixture
def cliente(monkeypatch):
    """Cliente en modo `stub`.

    El `setenv` no es cosmetico: `get_settings()` lee `.env`, donde
    `ARPIA_MODE=live` para el desarrollo contra el gateway. Sin forzarlo aqui,
    la prueba de integracion lanzaria un turno real y gastaria de los 100 USD
    del equipo cada vez que alguien corre la suite.
    """
    monkeypatch.setenv("ARPIA_MODE", "stub")
    config.get_settings.cache_clear()
    yield TestClient(app)
    config.get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _limpiar():
    tracing.reset()
    tracing.olvidar_sesiones()
    yield
    tracing.reset()
    tracing.olvidar_sesiones()


def _turno_a_medias(sesion: str = "s-1") -> str:
    """Simula un turno en vuelo: traza registrada y spans a medias.

    Reproduce lo que ve un `GET` concurrente mientras `run_chat` corre en el
    threadpool: la traza ya esta en el buffer y algunos spans cerraron.
    """
    trace_id = tracing.start_trace()
    tracing.registrar_sesion(sesion, trace_id)
    with tracing.span("tool", "guardian.revisar_entrada", input=PREGUNTA) as sp:
        sp.set_output("permitido")
    with tracing.span("llm", "orquestador.planificar", input=PREGUNTA) as sp:
        sp.set_output(json.dumps({"pasos": [{"agente": "agente_documental"}]}))
    with tracing.span("tool", "buscar_corpus", input=PREGUNTA) as sp:
        sp.set_output(FRAGMENTO)
    return trace_id


# -- la prueba que manda ----------------------------------------------------


def test_progress_no_publica_el_contenido_de_los_spans(cliente):
    """La razon de ser del endpoint cerrado /api/trace aplica igual aqui."""
    _turno_a_medias("s-privacidad")
    r = cliente.get("/api/progress", params={"sesion": "s-privacidad"})
    assert r.status_code == 200
    crudo = r.text

    assert PREGUNTA not in crudo, "la pregunta del usuario viaja en la respuesta"
    assert FRAGMENTO not in crudo, "un fragmento del corpus viaja en la respuesta"
    assert "input" not in crudo, "la clave input no puede aparecer"
    assert "output" not in crudo, "la clave output no puede aparecer"


def test_progress_solo_devuelve_los_campos_de_la_lista_blanca(cliente):
    """Lista blanca, no lista negra: un campo nuevo en Span no se cuela solo."""
    _turno_a_medias("s-campos")
    pasos = cliente.get("/api/progress", params={"sesion": "s-campos"}).json()["pasos"]
    assert pasos
    for paso in pasos:
        assert set(paso) == {"span_id", "parent_id", "tipo", "nombre", "duracion_ms"}


def test_la_duracion_es_un_numero_y_no_arrastra_marcas_de_tiempo(cliente):
    """`start_ms`/`end_ms` son relojes del proceso: no aportan y sí filtran
    cuando empezo el turno."""
    _turno_a_medias("s-duracion")
    pasos = cliente.get("/api/progress", params={"sesion": "s-duracion"}).json()["pasos"]
    for paso in pasos:
        assert isinstance(paso["duracion_ms"], (int, float))
        assert paso["duracion_ms"] >= 0
        assert "start_ms" not in paso and "end_ms" not in paso


# -- comportamiento ---------------------------------------------------------


def test_progress_lista_los_pasos_ya_completados(cliente):
    _turno_a_medias("s-pasos")
    cuerpo = cliente.get("/api/progress", params={"sesion": "s-pasos"}).json()
    assert cuerpo["disponible"] is True
    nombres = [p["nombre"] for p in cuerpo["pasos"]]
    assert nombres == [
        "guardian.revisar_entrada",
        "orquestador.planificar",
        "buscar_corpus",
    ]


def test_sin_turno_en_curso_responde_200_y_lo_declara(cliente):
    """Convencion del modulo: nunca un 4xx; `disponible: false` con motivo."""
    r = cliente.get("/api/progress", params={"sesion": "sesion-que-no-existe"})
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["disponible"] is False and cuerpo["motivo"]
    assert cuerpo["pasos"] == []


def test_sin_parametro_de_sesion_responde_200(cliente):
    """Un adorno informativo jamas devuelve un error que la interfaz deba
    manejar como fallo."""
    r = cliente.get("/api/progress")
    assert r.status_code == 200
    assert r.json()["disponible"] is False


def test_al_terminar_el_turno_la_sesion_deja_de_estar_en_curso(cliente):
    """Si no se limpiara, el panel seguiria mostrando el turno anterior como si
    seiguiera corriendo."""
    _turno_a_medias("s-fin")
    assert cliente.get("/api/progress", params={"sesion": "s-fin"}).json()["disponible"]
    tracing.olvidar_sesion("s-fin")
    assert not cliente.get("/api/progress", params={"sesion": "s-fin"}).json()["disponible"]


def test_dos_sesiones_no_se_mezclan(cliente):
    _turno_a_medias("s-a")
    _turno_a_medias("s-b")
    a = cliente.get("/api/progress", params={"sesion": "s-a"}).json()
    b = cliente.get("/api/progress", params={"sesion": "s-b"}).json()
    assert a["trace_id"] != b["trace_id"]


# -- el mapa no puede crecer sin tope ---------------------------------------


def test_el_mapa_de_sesiones_esta_acotado():
    """AGENTS.md §8: en un proceso que corre 24 horas, una estructura que crece
    por turno es una fuga de memoria con otro nombre."""
    for i in range(tracing.MAX_SESIONES * 3):
        tracing.registrar_sesion(f"sesion-{i}", tracing.start_trace())
    assert tracing.sesiones_en_curso() <= tracing.MAX_SESIONES


def test_el_mapa_conserva_las_sesiones_mas_recientes():
    """Descartar la mas nueva dejaria sin progreso justo al turno en vuelo."""
    for i in range(tracing.MAX_SESIONES + 5):
        tracing.registrar_sesion(f"s{i}", tracing.start_trace())
    assert tracing.trace_de_sesion(f"s{tracing.MAX_SESIONES + 4}") is not None
    assert tracing.trace_de_sesion("s0") is None


def test_olvidar_una_sesion_que_no_existe_no_lanza():
    """Se llama en el `finally` de cada turno, incluso si el turno fallo antes
    de registrarse."""
    tracing.olvidar_sesion("jamas-registrada")


# -- integracion con el turno real ------------------------------------------


def test_un_turno_real_registra_y_limpia_su_sesion(cliente):
    """Lo que de verdad importa: que `run_chat` enganche y suelte.

    En `stub` el turno dura 1-2 ms, asi que no se puede observar el progreso a
    mitad; lo que si se comprueba es el efecto observable a ambos lados, que es
    donde estaria el fallo.
    """
    assert tracing.trace_de_sesion("s-real") is None
    r = cliente.post("/chat", json={"texto": "hola", "sesion_id": "s-real"})
    assert r.status_code == 200
    # Terminado el turno, la sesion ya no figura en curso.
    assert tracing.trace_de_sesion("s-real") is None
    assert not cliente.get("/api/progress", params={"sesion": "s-real"}).json()["disponible"]


def test_la_sesion_se_suelta_aunque_el_turno_reviente(monkeypatch, cliente):
    """El `finally` del envoltorio, probado de verdad."""
    from src.api import chat as chat_mod

    def _explota(texto, session_id):
        raise RuntimeError("fallo inesperado")

    monkeypatch.setattr(chat_mod, "_turno", _explota)
    with pytest.raises(RuntimeError):
        chat_mod.run_chat("hola", "s-revienta")
    assert tracing.trace_de_sesion("s-revienta") is None
