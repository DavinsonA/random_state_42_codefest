"""El nombre de modelo de la card no es el id que acepta LiteLLM.

La card declara `llama-3.3-70b-instruct` (el nombre del PDF de ADL, con el que
ADL calcula el costo por pregunta). LiteLLM solo acepta `meta.llama3-3-70b-instruct`.
Sin traduccion, la redaccion del agente documental falla con "model not found";
`redactar()` captura la excepcion y devuelve fragmentos crudos con `estado: ok`,
asi que en produccion TODA respuesta saldria sin redactar y sin ningun error visible.

Regla que se protege aqui:
- al LLAMAR a LiteLLM se usa el id del gateway (`gateway_model_for`);
- al REPORTAR en `tokens_por_agente` se usa el nombre de la card (`model_for`),
  porque es el que ADL cruza contra la ficha para calcular el costo.
"""

from __future__ import annotations

import json

import pytest

from src import config
from src.agents import card, executors, orchestrator

#: Ids que devuelve `GET /v1/models` del LiteLLM del evento para los 8 modelos
#: permitidos por el reto. Los demas (gpt-4*, claude, voyage) NO se pueden usar.
LITELLM_IDS_PERMITIDOS = {
    "gpt-oss-20b",
    "gpt-oss-120b",
    "meta.llama3-3-70b-instruct",
    "meta.llama4-scout-17b-instruct",
    "mixtral-8x7b-instruct",
    "deepseek.r1",
    "qwen3-next-80b",
    "gemma-3-27b",
}


@pytest.fixture(autouse=True)
def _limpio(monkeypatch):
    monkeypatch.delenv("MODEL_ALIASES", raising=False)
    card.reset_cache()
    config.get_settings.cache_clear()
    yield
    card.reset_cache()
    config.get_settings.cache_clear()


def test_todo_modelo_de_la_card_se_resuelve_a_un_id_que_litellm_acepta():
    """Guarda contra editar la card con un nombre que el gateway no conoce."""
    agentes = [a for a, modelo in card.agent_models().items() if modelo]
    assert agentes, "la card debe declarar modelos"
    for agente in agentes:
        assert card.gateway_model_for(agente) in LITELLM_IDS_PERMITIDOS, (
            f"{agente}: '{card.model_for(agente)}' no se traduce a un id de LiteLLM"
        )


def test_el_documental_llama_con_el_id_de_litellm_y_reporta_el_nombre_de_la_card():
    assert card.model_for("agente_documental") == "llama-3.3-70b-instruct"
    assert card.gateway_model_for("agente_documental") == "meta.llama3-3-70b-instruct"


def test_un_modelo_sin_alias_se_envia_tal_cual():
    assert card.gateway_model_for("orquestador") == card.model_for("orquestador") == "gpt-oss-120b"


def test_los_agentes_deterministas_no_tienen_modelo():
    assert card.gateway_model_for("guardian") == ""
    assert card.gateway_model_for("agente_inexistente") == ""


def test_el_alias_se_puede_sobrescribir_por_entorno(monkeypatch):
    """Si el dia del evento LiteLLM nombra distinto un modelo, se corrige en
    Coolify sin tocar codigo ni reconstruir la imagen."""
    monkeypatch.setenv("MODEL_ALIASES", json.dumps({"llama-3.3-70b-instruct": "otro-id"}))
    card.reset_cache()
    assert card.gateway_model_for("agente_documental") == "otro-id"
    assert card.model_for("agente_documental") == "llama-3.3-70b-instruct"  # lo reportado no cambia


def test_un_alias_malformado_no_tumba_el_arranque(monkeypatch):
    monkeypatch.setenv("MODEL_ALIASES", "esto no es json")
    card.reset_cache()
    assert card.gateway_model_for("agente_documental") == "meta.llama3-3-70b-instruct"


@pytest.mark.parametrize(
    ("construir", "agente", "esperado"),
    [
        (
            lambda: executors._llm("agente_documental"),
            "agente_documental",
            "meta.llama3-3-70b-instruct",
        ),
        (lambda: executors._llm("agente_visualizador"), "agente_visualizador", "gpt-oss-20b"),
        (lambda: orchestrator._llm(), "orquestador", "gpt-oss-120b"),
    ],
)
def test_los_clientes_reales_reciben_el_id_de_litellm(monkeypatch, construir, agente, esperado):
    """Lo que llega a `ChatOpenAI(model=...)` es lo que viaja a LiteLLM."""
    capturado: dict = {}

    class ClienteFalso:
        def __init__(self, **kwargs):
            capturado.update(kwargs)

    monkeypatch.setattr("langchain_openai.ChatOpenAI", ClienteFalso)
    monkeypatch.setenv("LLM_BASE_URL", "http://falso/v1")
    monkeypatch.setenv("LLM_API_KEY", "falsa")
    config.get_settings.cache_clear()

    construir()
    assert capturado["model"] == esperado, agente
