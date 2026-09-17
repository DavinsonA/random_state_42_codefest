"""Configuracion central y logging estructurado.

Toda credencial y endpoint se lee de variables de entorno. Nunca se escribe
un secreto en codigo (AGENTS.md §7).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Configuracion de ejecucion, resuelta desde el entorno."""

    llm_base_url: str
    llm_api_key: str
    llm_model: str
    max_agent_iterations: int
    request_timeout_s: int
    log_level: str
    arpia_mode: str

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_base_url and self.llm_api_key)

    @property
    def is_stub(self) -> bool:
        return self.arpia_mode == "stub"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    mode = os.getenv("ARPIA_MODE", "stub").strip().lower()
    if mode not in ("stub", "live"):
        mode = "stub"
    return Settings(
        llm_base_url=os.getenv("LLM_BASE_URL", ""),
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_model=os.getenv("LLM_MODEL", ""),
        max_agent_iterations=int(os.getenv("MAX_AGENT_ITERATIONS", "6")),
        request_timeout_s=int(os.getenv("REQUEST_TIMEOUT_S", "60")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        arpia_mode=mode,
    )


def get_logger(name: str) -> logging.Logger:
    """Logger con formato consistente. Usar SIEMPRE en vez de print()."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s", "%H:%M:%S")
        )
        logger.addHandler(handler)
        logger.setLevel(get_settings().log_level)
        logger.propagate = False
    return logger
