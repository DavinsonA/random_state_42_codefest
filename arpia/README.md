# A.R.P.I.A.

Sistema multiagente de análisis de fuentes abiertas para inteligencia
aeroespacial. Expone una API (FastAPI) que consume el jurado y una interfaz
(Streamlit) para exploración manual.

Este repositorio es **el aplicativo**: lo único que se construye, se
despliega y se califica. El método de desarrollo (directivas para agentes,
skills, scripts de iteración) vive en el repo hermano [`../arpia-bundle`](../arpia-bundle).

## Estado

Reto publicado (CODEFEST Ad Astra 2026, Etapa 2). Qué exige ADL y cómo se califica:
[`../RETO.md`](../RETO.md). **Qué está construido, cómo funciona el API y qué falta:
[`API.md`](API.md)** — empieza por ahí.

## Cómo se corre

```bash
uv sync
cp .env.example .env               # ARPIA_MODE=stub por defecto: arranca sin credenciales
uv run uvicorn src.api.main:app --reload --port 8000   # API — lo que evalúa el jurado
uv run streamlit run src/ui/app.py                     # UI
```

## Cómo se despliega

Coolify construye esta carpeta desde `Dockerfile` (build pack: Dockerfile).
Ver [`../arpia-bundle/.claude/skills/coolify-deploy/SKILL.md`](../arpia-bundle/.claude/skills/coolify-deploy/SKILL.md)
para el procedimiento completo y `deploy-test/README.md` (raíz del monorepo)
para la configuración exacta del panel.

```bash
docker compose up --build          # reproduce el build de Coolify localmente
```

## Estructura

```
src/
├── config.py           configuración central, logger, lectura de .env
├── theme/               ÚNICO lugar que lee docs/design/design-tokens.json
├── retrieval/            adaptador al índice vectorial existente
├── tools/                tools del agente + registry con traza
├── agents/               estado + grafo LangGraph
├── api/
│   ├── contracts.py       ÚNICO lugar con los esquemas Pydantic (formato ADL de /chat)
│   └── main.py             endpoints: /chat /agent-card /health /usage
└── ui/                   Streamlit

docs/
├── design/               bundle visual — fuente de verdad del tema (leído en runtime)
├── architecture.md        líneas de trabajo y decisión de stack
└── decisions/             ADRs

tests/                    pytest — incluye tests de contrato de la API
```

## Reglas que hace cumplir este repo

| Regla | Dónde se verifica |
|---|---|
| Ningún color hexadecimal fuera de `src/theme/` | `tests/test_theme.py` |
| El contrato HTTP no cambia sin querer | `tests/test_contract.py` |
| Ningún secreto ni dependencia copyleft | `../arpia-bundle/scripts/preflight.py` |

## Licencia

Apache 2.0 — ver [`LICENSE`](LICENSE).
