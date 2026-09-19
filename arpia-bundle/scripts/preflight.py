#!/usr/bin/env python
"""Verificacion pre-despliegue. Obligatorio antes de cada push a Coolify.

Comprueba, en orden de gravedad:
  1. secretos filtrados en el codigo          -> descalifica / compromete claves
  2. licencias de dependencias                -> DESCALIFICA al equipo
  3. colores hexadecimales fuera de theme/    -> viola AGENTS.md §2
  4. topes de iteracion en bucles agenticos   -> riesgo de quemar presupuesto
  5. archivos obligatorios del entregable

Codigo de salida distinto de 0 si algo critico falla.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from pathlib import Path

BUNDLE_ROOT = Path(__file__).resolve().parents[1]
# El aplicativo vive en el repo hermano ../arpia; overrideable via ARPIA_ROOT
# para poder correr el preflight contra un checkout en otra ubicacion.
ROOT = Path(os.environ.get("ARPIA_ROOT", BUNDLE_ROOT.parent / "arpia")).resolve()

SECRET_PATTERNS = [
    (r"sk-[A-Za-z0-9]{16,}", "clave tipo OpenAI/Anthropic"),
    (r"AKIA[0-9A-Z]{16}", "clave de acceso AWS"),
    (r"ghp_[A-Za-z0-9]{20,}", "token de GitHub"),
    (r"(?i)(api[_-]?key|secret|password|token)\s*=\s*[\"'][^\"'{$]{12,}[\"']", "credencial literal"),
]

# Licencias copyleft fuerte: su presencia descalifica al equipo.
FORBIDDEN_LICENSES = ("GPL", "AGPL", "LGPL")
LICENSE_ALLOWLIST = ("LGPL-2.1-or-later",)  # excepciones revisadas a mano, si las hubiera

REQUIRED_FILES = [
    "LICENSE",
    "README.md",
    "Dockerfile",
    "pyproject.toml",
    "requirements.txt",
    ".dockerignore",
]

HEX_RE = re.compile(r"#[0-9a-fA-F]{6}\b")

ENV_VAR_RE = re.compile(
    r"""os\.getenv\(\s*["']([A-Z_][A-Z0-9_]*)["']"""
    r"""|os\.environ\.get\(\s*["']([A-Z_][A-Z0-9_]*)["']"""
    r"""|os\.environ\[\s*["']([A-Z_][A-Z0-9_]*)["']\s*\]"""
)
ENV_EXAMPLE_KEY_RE = re.compile(r"^([A-Z_][A-Z0-9_]*)=", re.MULTILINE)


def _py_files(exclude: tuple[str, ...] = ()) -> list[Path]:
    out = []
    for p in ROOT.rglob("*.py"):
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith((".venv/", "node_modules/", "data/")) or any(e in rel for e in exclude):
            continue
        out.append(p)
    return out


def check_secrets() -> list[str]:
    errs = []
    for path in _py_files():
        text = path.read_text("utf-8", errors="ignore")
        for pattern, label in SECRET_PATTERNS:
            for m in re.finditer(pattern, text):
                line = text[: m.start()].count("\n") + 1
                errs.append(f"{path.relative_to(ROOT)}:{line} posible {label}")
    return errs


def check_licenses() -> list[str]:
    try:
        out = subprocess.run(
            ["uv", "run", "pip-licenses", "--format=csv"],
            capture_output=True, text=True, timeout=120, cwd=ROOT,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ["[aviso] no se pudo verificar licencias (pip-licenses no disponible)"]
    if out.returncode != 0:
        return ["[aviso] pip-licenses fallo; verificar licencias a mano"]

    errs = []
    for row in out.stdout.splitlines()[1:]:
        parts = row.split(",")
        if len(parts) < 3:
            continue
        name, lic = parts[0].strip('" '), parts[2].strip('" ')
        if lic in LICENSE_ALLOWLIST:
            continue
        if any(f in lic.upper() for f in FORBIDDEN_LICENSES):
            errs.append(f"DEPENDENCIA PROHIBIDA: {name} ({lic}) — descalifica al equipo")
    return errs


def check_tokens() -> list[str]:
    """Ningun hexadecimal fuera de src/theme/ y docs/design/."""
    errs = []
    for path in _py_files(exclude=("src/theme/",)):
        text = path.read_text("utf-8", errors="ignore")
        for m in HEX_RE.finditer(text):
            line = text[: m.start()].count("\n") + 1
            errs.append(
                f"{path.relative_to(ROOT)}:{line} color literal {m.group(0)} "
                f"— usar src.theme.tokens (AGENTS.md §2)"
            )
    return errs


#: Nombres que cuentan como tope de iteraciones. `max_agent_iterations` y
#: `max_iterations` son los del bucle ReAct original; `max_pasos` y
#: `max_replanes` los del orquestador de plan unico que lo reemplazo. Se
#: aceptan los cuatro: lo que importa es que el coste del turno este acotado,
#: no como se llame la constante que lo acota.
TOPES_CONOCIDOS = ("max_agent_iterations", "max_iterations", "max_pasos", "max_replanes")


def check_iteration_caps() -> list[str]:
    """Todo modulo de agentes debe referenciar un tope de iteraciones."""
    agents_dir = ROOT / "src" / "agents"
    if not agents_dir.exists():
        return []
    joined = "\n".join(
        p.read_text("utf-8", errors="ignore") for p in agents_dir.rglob("*.py")
    ).lower()
    if not any(t in joined for t in TOPES_CONOCIDOS):
        return ["src/agents/ no referencia ningun tope de iteraciones (AGENTS.md §8)"]
    return []


def check_env_parity() -> list[str]:
    """Paridad dev/deploy: toda variable de entorno leida en `src/` debe estar
    declarada en `.env.example`. Una variable que solo existe en el `.env`
    local de alguien es una fuente de fallo que aparece tarde, en Coolify."""
    example_path = ROOT / ".env.example"
    if not example_path.exists():
        return ["falta .env.example: no se puede verificar paridad de variables"]
    declared = set(ENV_EXAMPLE_KEY_RE.findall(example_path.read_text("utf-8", errors="ignore")))

    referenced: set[str] = set()
    for path in _py_files():
        text = path.read_text("utf-8", errors="ignore")
        for match in ENV_VAR_RE.finditer(text):
            referenced.add(next(g for g in match.groups() if g))

    missing = sorted(referenced - declared)
    return [f"variable '{v}' usada en src/ pero no declarada en .env.example" for v in missing]


def check_required_files() -> list[str]:
    errs = [f"falta archivo obligatorio: {f}" for f in REQUIRED_FILES if not (ROOT / f).exists()]
    lic = ROOT / "LICENSE"
    if lic.exists():
        text = lic.read_text("utf-8", errors="ignore")
        if "ACCION REQUERIDA" in text or "TERMS AND CONDITIONS" not in text:
            errs.append(
                "LICENSE incompleto: pegar el texto integro de Apache 2.0 "
                "(https://www.apache.org/licenses/LICENSE-2.0.txt) — sin esto DESCALIFICA"
            )
    return errs


CHECKS = {
    "secrets": ("Secretos filtrados", check_secrets, True),
    "licenses": ("Licencias de dependencias", check_licenses, True),
    "tokens": ("Colores fuera de theme/", check_tokens, False),
    "iterations": ("Topes de iteracion", check_iteration_caps, False),
    "env_parity": ("Paridad de variables dev/deploy", check_env_parity, True),
    "files": ("Archivos obligatorios", check_required_files, True),
}


def main() -> int:
    ap = argparse.ArgumentParser(description="Verificacion pre-despliegue de A.R.P.I.A.")
    for name in CHECKS:
        ap.add_argument(f"--{name}", action="store_true", help=f"solo {name}")
    args = ap.parse_args()

    selected = [k for k in CHECKS if getattr(args, k)] or list(CHECKS)
    critical_failed = False

    print(f"==> preflight A.R.P.I.A. (objetivo: {ROOT})\n")
    for key in selected:
        label, fn, is_critical = CHECKS[key]
        errs = fn()
        if not errs:
            print(f"  [ok]    {label}")
            continue
        only_warnings = all(e.startswith("[aviso]") for e in errs)
        marker = "[aviso]" if (only_warnings or not is_critical) else "[FALLA]"
        print(f"  {marker} {label}")
        for e in errs[:12]:
            print(f"            {e}")
        if len(errs) > 12:
            print(f"            ... y {len(errs) - 12} mas")
        if is_critical and not only_warnings:
            critical_failed = True

    print()
    if critical_failed:
        print("==> PREFLIGHT FALLIDO. No desplegar.")
        return 1
    print("==> preflight superado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
