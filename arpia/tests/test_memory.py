"""Pruebas del cache semantico y la ventana de historial (`src/agents/memory.py`).

No descargan el encoder: la ruta semantica se ejercita con un codificador
falso de vectores controlados, que es la unica forma de probar el umbral sin
depender de un modelo de 2 GB ni de que dos frases "se parezcan lo suficiente".
"""

from __future__ import annotations

import pytest

from src.agents.memory import UMBRAL, CacheSemantico, normalizar, ventana_historial
from src.api.contracts import AgentResponse, Evaluacion, Metadata, TokensPorAgente


def _respuesta(texto: str = "respuesta original") -> AgentResponse:
    return AgentResponse(
        respuesta=texto,
        evaluacion=Evaluacion(
            input="pregunta", actual_output=texto, retrieval_context=["fragmento del corpus"]
        ),
        metadata=Metadata(
            num_interacciones=3,
            agentes_invocados=["orquestador", "agente_documental"],
            tokens_por_agente=[
                TokensPorAgente(agente="orquestador", modelo="m", input=100, output=50, total=150)
            ],
            latencia_ms=2500,
        ),
        mode="live",
    )


@pytest.fixture
def sin_encoder(monkeypatch):
    """Fuerza la degradacion a coincidencia exacta."""
    from src.retrieval import encoder

    monkeypatch.setattr(encoder, "loaded", lambda: False)


# -- normalizacion -----------------------------------------------------------


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("Que dice el corpus?", "que dice el corpus"),
        ("  CAPACIDADES   antisatelite  ", "capacidades antisatelite"),
        ("Órbita baja", "orbita baja"),
    ],
)
def test_consultas_equivalentes_se_normalizan_igual(a, b):
    assert normalizar(a) == normalizar(b)


# -- degradacion sin encoder -------------------------------------------------


def test_sin_encoder_el_cache_sigue_sirviendo_por_coincidencia_exacta(sin_encoder):
    c = CacheSemantico()
    c.guardar("Que dice el corpus sobre satelites?", _respuesta())
    assert c.buscar("  que dice el CORPUS sobre satelites  ") is not None
    assert c.buscar("otra pregunta completamente distinta") is None


def test_un_acierto_declara_cero_consumo(sin_encoder):
    """Un acierto de cache no llama al modelo: reportar los tokens del turno
    original seria declarar un consumo que no ocurrio."""
    c = CacheSemantico()
    c.guardar("pregunta", _respuesta())
    hit = c.buscar("pregunta")
    assert hit is not None
    assert hit.metadata.num_interacciones == 0
    assert hit.metadata.tokens.total == 0
    assert hit.metadata.tokens_por_agente == []
    assert hit.metadata.agentes_invocados == ["memoria"]
    assert hit.metadata.estado.startswith("cache")


def test_un_acierto_conserva_intacto_el_bloque_de_calidad(sin_encoder):
    """La `evaluacion` es la misma respuesta, y se califica igual."""
    c = CacheSemantico()
    c.guardar("pregunta", _respuesta("texto con evidencia"))
    hit = c.buscar("pregunta")
    assert hit.respuesta == "texto con evidencia"
    assert hit.evaluacion.retrieval_context == ["fragmento del corpus"]


def test_no_se_reguarda_lo_que_vino_del_cache(sin_encoder):
    c = CacheSemantico()
    c.guardar("pregunta", _respuesta())
    hit = c.buscar("pregunta")
    c.guardar("otra", hit)
    assert c.buscar("otra") is None


def test_el_cache_tiene_tope_y_descarta_lo_mas_antiguo(sin_encoder):
    """AGENTS.md §8: todo almacen lleva tope. Un proceso de 24 horas sin el se
    queda sin memoria."""
    c = CacheSemantico(max_entradas=3)
    for i in range(5):
        c.guardar(f"pregunta {i}", _respuesta())
    assert c.stats()["entradas"] == 3
    assert c.buscar("pregunta 0") is None
    assert c.buscar("pregunta 4") is not None


# -- ruta semantica con encoder falso ---------------------------------------


@pytest.fixture
def encoder_falso(monkeypatch):
    """Vectores unitarios controlados: la similitud coseno es predecible."""
    import numpy as np

    from src.retrieval import encoder

    vectores = {
        "base": np.array([1.0, 0.0, 0.0]),
        "casi_igual": np.array([0.999, 0.0447, 0.0]),  # coseno ~0.999
        "parecida": np.array([0.90, 0.4359, 0.0]),  # coseno ~0.90, bajo el umbral
        "distinta": np.array([0.0, 1.0, 0.0]),  # coseno 0
    }
    monkeypatch.setattr(encoder, "loaded", lambda: True)
    monkeypatch.setattr(
        encoder, "encode", lambda textos, *a, **k: np.vstack([vectores[t] for t in textos])
    )
    return vectores


def test_acierta_con_una_consulta_semanticamente_equivalente(encoder_falso):
    c = CacheSemantico()
    c.guardar("base", _respuesta())
    hit = c.buscar("casi_igual")
    assert hit is not None
    assert hit.metadata.estado.startswith("cache")


def test_no_acierta_por_debajo_del_umbral(encoder_falso):
    """0,90 de similitud es 'tema parecido', no 'la misma pregunta'. Devolver la
    respuesta de otra pregunta cuesta calidad, que pesa el doble que eficiencia."""
    c = CacheSemantico()
    c.guardar("base", _respuesta())
    assert c.buscar("parecida") is None
    assert c.buscar("distinta") is None


def test_el_umbral_es_alto_a_proposito():
    assert UMBRAL >= 0.95


def test_stats_reporta_la_tasa_de_acierto(encoder_falso):
    c = CacheSemantico()
    c.guardar("base", _respuesta())
    c.buscar("casi_igual")
    c.buscar("distinta")
    s = c.stats()
    assert s["consultas"] == 2 and s["aciertos"] == 1
    assert s["tasa_acierto"] == 0.5


# -- ventana de historial ----------------------------------------------------


class _Msg:
    def __init__(self, tipo: str, texto: str) -> None:
        self.type = tipo
        self.content = texto


def test_la_ventana_conserva_el_mensaje_de_sistema():
    """Perder las reglas de dominio por truncado es justo lo que busca un
    atacante que alarga la conversacion."""
    historial = [_Msg("system", "reglas")] + [_Msg("human", f"m{i}") for i in range(20)]
    recortado = ventana_historial(historial, turnos=2)
    assert recortado[0].type == "system"
    assert len(recortado) == 5  # sistema + 2 turnos * 2 mensajes
    assert recortado[-1].content == "m19"


def test_la_ventana_no_toca_un_historial_corto():
    historial = [_Msg("human", "a"), _Msg("ai", "b")]
    assert ventana_historial(historial, turnos=6) == historial


def test_la_ventana_tolera_un_historial_vacio():
    assert ventana_historial([], turnos=6) == []
