#!/usr/bin/env bash
# Verifica el entorno DESPLEGADO (Coolify), NO localhost.
#
# El jurado consume la aplicacion desplegada, no el repositorio: este script
# es la unica prueba que corre contra ese entorno desde fuera. Un
# `docker compose up` local pasando no garantiza que el despliegue responda.
#
# Uso: scripts/smoke_deploy.sh https://arpia.mi-dominio.com
#
# Golpea /health, /analyze y /usage; valida codigo HTTP y forma minima de la
# respuesta; imprime un resumen legible. Sale con codigo != 0 si algo falla.

set -u

BASE_URL="${1:-}"
if [[ -z "$BASE_URL" ]]; then
  echo "uso: $0 <url-base-del-despliegue>" >&2
  exit 2
fi
BASE_URL="${BASE_URL%/}"

# En algunos entornos (Windows) `python3` es un alias roto de la Microsoft
# Store; probar candidatos en vez de asumir uno fijo.
PYTHON_BIN=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" --version >/dev/null 2>&1; then
    PYTHON_BIN="$candidate"
    break
  fi
done
if [[ -z "$PYTHON_BIN" ]]; then
  echo "no se encontro un interprete de Python usable (probado: python3, python)" >&2
  exit 2
fi

FAILED=0
OK="[ok]   "
BAD="[FALLA]"

# Evalua una condicion Python sobre el JSON recibido. $1=json $2=expresion
_schema_ok() {
  "$PYTHON_BIN" -c "
import json, sys
try:
    data = json.loads(sys.argv[1])
except Exception:
    sys.exit(1)
sys.exit(0 if ($2) else 1)
" "$1" 2>/dev/null
}

check_endpoint() {
  local label="$1" method="$2" path="$3" body_arg="$4" expr="$5"
  local url="$BASE_URL$path" raw code json

  echo "-- $path"
  if [[ "$method" == "POST" ]]; then
    raw=$(curl -sS -m 30 -w '\n%{http_code}' -X POST "$url" \
      -H 'Content-Type: application/json' -d "$body_arg" 2>&1)
  else
    raw=$(curl -sS -m 10 -w '\n%{http_code}' "$url" 2>&1)
  fi
  local status=$?
  if [[ $status -ne 0 ]]; then
    echo "  $BAD no se pudo conectar: $raw"
    FAILED=1
    echo
    return
  fi

  code=$(echo "$raw" | tail -n1)
  json=$(echo "$raw" | sed '$d')

  if [[ "$code" == "200" ]]; then
    echo "  $OK HTTP $code"
  else
    echo "  $BAD HTTP inesperado: $code (se esperaba 200)"
    FAILED=1
  fi

  if _schema_ok "$json" "$expr"; then
    echo "  $OK esquema valido ($label)"
  else
    echo "  $BAD esquema invalido: ${json:0:300}"
    FAILED=1
  fi
  echo
}

echo "==> smoke test de despliegue: $BASE_URL"
echo

check_endpoint "health" GET "/health" "" \
  "'status' in data and 'mode' in data and 'tools_registered' in data and 'max_iterations' in data"

check_endpoint "analyze" POST "/analyze" '{"query": "smoke test de despliegue"}' \
  "all(k in data for k in ('query','answer','evidence','warnings','trace','tokens_used','elapsed_ms','mode')) and 'trace_id' in data.get('trace', {}) and isinstance(data['trace'].get('spans'), list)"

check_endpoint "usage" GET "/usage" "" \
  "'session' in data and 'total_tokens' in data.get('session', {})"

if [[ "$FAILED" -ne 0 ]]; then
  echo "==> smoke test FALLIDO"
  exit 1
fi
echo "==> smoke test superado"
exit 0
