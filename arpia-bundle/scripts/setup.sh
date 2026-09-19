#!/usr/bin/env bash
# Inicializacion del entorno de A.R.P.I.A. Idempotente: seguro re-ejecutar.
#
# El aplicativo (pyproject.toml, src/, .env.example) vive en el repo hermano
# ../arpia; este script solo orquesta desde arpia-bundle/. Overrideable via
# ARPIA_ROOT para apuntar a un checkout en otra ubicacion.
set -euo pipefail

BUNDLE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ARPIA_ROOT="${ARPIA_ROOT:-$BUNDLE_ROOT/../arpia}"
cd "$ARPIA_ROOT"
echo "==> A.R.P.I.A. — setup ($ARPIA_ROOT)"

if ! command -v uv >/dev/null 2>&1; then
  echo "--> instalando uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

echo "--> sincronizando dependencias"
uv sync

if [ ! -f .env ]; then
  cp .env.example .env
  echo "!!  .env creado desde plantilla — COMPLETA LLM_API_KEY antes de continuar"
fi

echo "--> verificando tokens visuales"
uv run python -c "
from src.theme.tokens import tokens
print(f'    fenomenos: {sorted(tokens.phenomena)}')
print(f'    fondo:     {tokens.foundation.background}')
"

echo "--> verificando conectividad con el gateway de modelos"
uv run python - <<'PY'
from src.config import get_settings
s = get_settings()
if not s.llm_configured:
    print("    [pendiente] LLM_BASE_URL / LLM_API_KEY sin configurar en .env")
else:
    import httpx
    try:
        r = httpx.get(f"{s.llm_base_url.rstrip('/')}/models",
                      headers={"Authorization": f"Bearer {s.llm_api_key}"}, timeout=10)
        print(f"    gateway responde: HTTP {r.status_code}")
    except Exception as e:
        print(f"    [aviso] gateway no responde: {e}")
PY

echo ""
echo "==> listo."
echo "    (comandos relativos a $ARPIA_ROOT)"
echo "    API + interfaces: uv run uvicorn src.api.main:app --reload --port 8000"
echo "        chat:    http://localhost:8000/"
echo "        tablero: http://dashboard.localhost:8000/"
echo "    Nodo: uv run python $BUNDLE_ROOT/scripts/run_node.py --list"
