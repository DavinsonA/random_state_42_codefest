"""Lectura de la agent card (`agent_card.json`, formato ADL §2.3).

La card es la fuente de verdad de DOS cosas que el contrato necesita:

- los **ids de agente** que pueden aparecer en `metadata.agentes_invocados`;
- el **modelo fijo por agente**, que ADL usa para calcular el costo estimado
  por pregunta (`RETO.md` §Modelos). Declararlo aqui y leerlo desde el codigo
  evita que la card y el sistema se desincronicen.

**Dos nombres para un mismo modelo.** La card usa el nombre del PDF de ADL
(`llama-3.3-70b-instruct`), que es el que ADL cruza para calcular el costo y el
que se REPORTA en `tokens_por_agente` (`model_for`). El LiteLLM del evento
nombra distinto ese modelo (`meta.llama3-3-70b-instruct`), y ese es el id con el
que hay que LLAMAR (`gateway_model_for`). Enviar el nombre de la card hace que
LiteLLM responda "model not found"; `redactar()` lo captura y entrega fragmentos
crudos con `estado: ok`, sin ningun error visible.

Nunca lanza: si el archivo falta o esta corrupto, devuelve una card vacia y
`/health` lo reporta como advertencia. Un despliegue sin card debe seguir
respondiendo `/chat`.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.config import get_logger

log = get_logger(__name__)

# Componentes deterministas (0 tokens) que actuan sin ser agentes de modelo.
# No van en la card porque no consumen presupuesto ni tienen modelo asignado,
# pero SI aparecen en `agentes_invocados` cuando intervienen.
DETERMINISTIC_AGENTS = ("guardian", "memoria")

#: Nombre en la card / PDF de ADL -> id que acepta el LiteLLM del evento
#: (verificado con `GET /v1/models`). Los modelos cuyo nombre coincide no
#: figuran: se envian tal cual. `MODEL_ALIASES` (JSON) lo sobrescribe sin tocar
#: codigo, para corregirlo desde Coolify si el dia del evento un id cambia.
_ALIAS_LITELLM: dict[str, str] = {
    "llama-3.3-70b-instruct": "meta.llama3-3-70b-instruct",
    "llama-4-scout": "meta.llama4-scout-17b-instruct",
    "deepseek-r1-distill-llama-70b": "deepseek.r1",
    "qwen3-next-80b-a3b": "qwen3-next-80b",
}


def _card_path() -> Path:
    """Ruta de la card. `AGENT_CARD_PATH` la sobrescribe; por defecto, la raiz
    del proyecto (funciona igual con `uvicorn` desde `arpia/` y con WORKDIR
    `/app` en el contenedor)."""
    env = os.getenv("AGENT_CARD_PATH")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "agent_card.json"


@lru_cache(maxsize=1)
def load_card() -> dict[str, Any]:
    """Card completa, tal cual se sirve en `GET /agent-card`. `{}` si falta."""
    path = _card_path()
    try:
        return json.loads(path.read_text("utf-8"))
    except Exception as exc:  # noqa: BLE001 - frontera deliberada: nunca lanza
        log.warning("agent_card.json no disponible en %s: %s", path, exc)
        return {}


@lru_cache(maxsize=1)
def agent_models() -> dict[str, str]:
    """Mapa `id de agente -> modelo declarado`, incluido el orquestador.

    Los agentes deterministas quedan con modelo vacio a proposito: gastan cero
    tokens y reportar un modelo para ellos falsearia `tokens_por_agente`.
    """
    card = load_card()
    models: dict[str, str] = {}
    orq = card.get("orquestador") or {}
    if orq:
        models["orquestador"] = str(orq.get("modelo", ""))
    for sub in card.get("subagentes") or []:
        if sub.get("id"):
            models[str(sub["id"])] = str(sub.get("modelo", ""))
    for name in DETERMINISTIC_AGENTS:
        models.setdefault(name, "")
    return models


def agent_ids() -> list[str]:
    """Ids validos para `metadata.agentes_invocados`, en orden estable."""
    return sorted(agent_models())


def model_for(agent_id: str) -> str:
    """Modelo declarado para un agente. Cadena vacia si no tiene o no existe."""
    return agent_models().get(agent_id, "")


@lru_cache(maxsize=1)
def _aliases() -> dict[str, str]:
    """Mapa de traduccion vigente: el de codigo, mas lo que diga `MODEL_ALIASES`.

    Un JSON malformado no tumba el arranque: se ignora y se avisa.
    """
    mapa = dict(_ALIAS_LITELLM)
    crudo = os.getenv("MODEL_ALIASES", "").strip()
    if crudo:
        try:
            extra = json.loads(crudo)
            if isinstance(extra, dict):
                mapa.update({str(k): str(v) for k, v in extra.items()})
            else:
                log.warning("MODEL_ALIASES debe ser un objeto JSON; se ignora")
        except ValueError:
            log.warning("MODEL_ALIASES no es JSON valido; se ignora")
    return mapa


def gateway_model_for(agent_id: str) -> str:
    """Id de modelo con el que se LLAMA a LiteLLM para un agente.

    Es `model_for` traducido por `_aliases()`. Cadena vacia si el agente no tiene
    modelo: quien construye el cliente cae entonces a `LLM_MODEL`.

    NO usar para reportar consumo: `tokens_por_agente.modelo` lleva el nombre de la
    card (`model_for`), porque es el que ADL cruza contra la ficha para el costo.
    """
    declarado = model_for(agent_id)
    return _aliases().get(declarado, declarado)


def reset_cache() -> None:
    """Limpia las caches. Solo para pruebas."""
    load_card.cache_clear()
    agent_models.cache_clear()
    _aliases.cache_clear()
