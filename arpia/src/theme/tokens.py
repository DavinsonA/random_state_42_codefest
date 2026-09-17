"""Carga de los design tokens de A.R.P.I.A.

Único punto del proyecto autorizado para leer `docs/design/design-tokens.json`.
Ningún módulo de aplicación debe contener un color hexadecimal literal:
si un color no existe en el JSON, no existe en la aplicación (ver AGENTS.md §2).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

TOKENS_PATH = Path(__file__).resolve().parents[2] / "docs" / "design" / "design-tokens.json"


@dataclass(frozen=True)
class Foundation:
    void: str
    background: str
    surface: str
    elevated: str
    border: str
    border_active: str


@dataclass(frozen=True)
class Brand:
    deep: str
    primary: str
    electric: str
    space: str


@dataclass(frozen=True)
class Semantic:
    success: str
    info: str
    warning: str
    critical: str
    evidence: str


@dataclass(frozen=True)
class Text:
    primary: str
    secondary: str
    muted: str
    disabled: str


@dataclass(frozen=True)
class Tokens:
    foundation: Foundation
    brand: Brand
    semantic: Semantic
    text: Text
    phenomena: dict[str, dict[str, str]]

    def phenomenon(self, key: str) -> str:
        """Color semántico de un fenómeno (F1/F2/F3).

        Args:
            key: identificador del fenómeno, p. ej. "F1".

        Raises:
            KeyError: si el fenómeno no está declarado en los tokens.
        """
        key = key.upper()
        if key not in self.phenomena:
            raise KeyError(
                f"fenomeno '{key}' no declarado en design-tokens.json; "
                f"disponibles: {sorted(self.phenomena)}"
            )
        return self.phenomena[key]["color"]

    def phenomenon_map(self) -> dict[str, str]:
        """Mapa {nombre legible del fenomeno: color}, para leyendas de graficos."""
        return {v["name"]: v["color"] for v in self.phenomena.values()}

    @property
    def categorical_sequence(self) -> list[str]:
        """Secuencia categorica por defecto, en orden semantico F1-F2-F3.

        Se extiende con tonos de marca solo si hay mas series que fenomenos.
        """
        base = [self.phenomena[k]["color"] for k in sorted(self.phenomena)]
        return base + [self.brand.electric, self.brand.deep, self.text.secondary]


@lru_cache(maxsize=1)
def load(path: Path | None = None) -> Tokens:
    """Carga y cachea los design tokens desde el JSON del bundle visual."""
    raw = json.loads((path or TOKENS_PATH).read_text(encoding="utf-8"))
    colors = raw["colors"]
    return Tokens(
        foundation=Foundation(**colors["foundation"]),
        brand=Brand(**colors["brand"]),
        semantic=Semantic(**colors["semantic"]),
        text=Text(**colors["text"]),
        phenomena=colors["phenomena"],
    )


tokens = load()
