"""Lectura de la agent card (`agent_card.json`, formato ADL §2.3).

La card es la fuente de verdad de DOS cosas que el contrato necesita:

- los **ids de agente** que pueden aparecer en `metadata.agentes_invocados`;
- el **modelo fijo por agente**, que ADL usa para calcular el costo estimado
  por pregunta (`RETO.md` §Modelos). Declararlo aqui y leerlo desde el codigo
  evita que la card y el sistema se desincronicen.

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


def reset_cache() -> None:
    """Limpia las caches. Solo para pruebas."""
    load_card.cache_clear()
    agent_models.cache_clear()
