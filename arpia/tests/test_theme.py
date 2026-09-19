"""Pruebas de la capa de tema.

Protegen la invariante central de AGENTS.md §2: los tokens son la unica
fuente de color, y el resto del codigo no contiene hexadecimales literales.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.theme.tokens import load, tokens

ROOT = Path(__file__).resolve().parents[1]
HEX_RE = re.compile(r"#[0-9a-fA-F]{6}\b")


def test_tokens_cargan():
    t = load()
    assert t.foundation.background.startswith("#")
    assert set(t.phenomena) == {"F1", "F2", "F3"}


def test_fenomeno_desconocido_falla_ruidosamente():
    with pytest.raises(KeyError, match="F9"):
        tokens.phenomenon("F9")


def test_secuencia_categorica_empieza_por_fenomenos():
    seq = tokens.categorical_sequence
    assert seq[:3] == [tokens.phenomenon(k) for k in ("F1", "F2", "F3")]


def test_phenomenon_map_usa_nombres_legibles():
    mapa = tokens.phenomenon_map()
    assert len(mapa) == 3
    assert all(v.startswith("#") for v in mapa.values())


def test_ningun_hex_literal_fuera_de_theme():
    """El resto de src/ no puede contener colores propios."""
    ofensores = []
    for path in (ROOT / "src").rglob("*.py"):
        if "theme" in path.parts:
            continue
        for m in HEX_RE.finditer(path.read_text("utf-8", errors="ignore")):
            ofensores.append(f"{path.relative_to(ROOT)}: {m.group(0)}")
    assert not ofensores, "colores literales fuera de src/theme/: " + "; ".join(ofensores)
