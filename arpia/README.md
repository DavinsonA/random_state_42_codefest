# A.R.P.I.A.

Sistema multiagente de análisis de fuentes abiertas para inteligencia
aeroespacial. Un solo contenedor FastAPI sirve las tres cosas que se evalúan:
el endpoint `POST /chat` que consume ADL, el chat web (Reto 1) y el tablero
(Reto 2). Cuál se sirve en `/` lo decide la cabecera `Host`.

Este repositorio es **el aplicativo**: lo único que se construye, se
despliega y se califica. El método de desarrollo (directivas para agentes,
skills, scripts de iteración) vive en el repo hermano [`../arpia-bundle`](../arpia-bundle).

## Estado

Reto publicado (CODEFEST Ad Astra 2026, Etapa 2). Qué exige ADL y cómo se califica:
[`../RETO.md`](../RETO.md). **Qué está construido, cómo funciona el API y qué falta:
[`API.md`](API.md)** — empieza por ahí.

## Dónde está cada cosa

| Si buscas… | Lee |
|---|---|
| Qué exige ADL y cómo se puntúa | [`../RETO.md`](../RETO.md) |
| Qué hay construido, el contrato de cada endpoint y qué falta | [`API.md`](API.md) — **la fuente de verdad** |
| Por qué el sistema es así (agentes, plan único, seguridad, honestidad de los datos) | [`docs/architecture.md`](docs/architecture.md) |
| Cómo se despliega y qué se decidió en Coolify | [`DEPLOY.md`](DEPLOY.md) |
| Reglas del frontend: stack, colores, forma de los datos | [`FRONTEND.md`](FRONTEND.md) |
| La frontera entre el API y el grafo | [`src/api/CONTRATO_GRAFO.md`](src/api/CONTRATO_GRAFO.md) |

Regla del repo: **si cambias un contrato o el comportamiento de un endpoint,
actualizas `API.md` en el mismo commit.** Un documento desactualizado es peor
que ninguno.

## Cómo se corre

```bash
uv sync
cp .env.example .env               # ARPIA_MODE=stub por defecto: arranca sin credenciales
uv run uvicorn src.api.main:app --reload --port 8000
```

Eso levanta todo: el API en `/chat`, el chat web en `http://localhost:8000/` y
el tablero en `http://dashboard.localhost:8000/`. En `stub` las respuestas son
simuladas y se ve a simple vista (`mode`, `metadata.estado`, `/health`); el
despliegue evaluado corre en `live`.

```bash
uv run pytest                      # incluye las pruebas JS del frontend
```

## Cómo se despliega

Coolify construye esta carpeta desde `Dockerfile` (build pack: Dockerfile).
Ver [`../arpia-bundle/.claude/skills/coolify-deploy/SKILL.md`](../arpia-bundle/.claude/skills/coolify-deploy/SKILL.md)
para el procedimiento completo
para la configuración exacta del panel.

```bash
docker compose up --build          # reproduce el build de Coolify localmente
```

## Estructura

```
src/
├── config.py              configuración central, logger, lectura de .env
├── api/
│   ├── main.py             endpoints: /chat /agent-card /health /usage
│   ├── chat.py              el turno completo: guardián → caché → grafo → guardián
│   ├── contracts.py         ÚNICO lugar con los esquemas Pydantic (formato ADL)
│   ├── dashboard.py         endpoints del tablero (/api/*), 0 tokens
│   ├── session.py           resolución del sesion_id (cuerpo, header, cookie)
│   ├── routing.py           qué HTML sirve / según el Host; monta static/
│   └── stub.py              respuestas simuladas para desarrollo sin credenciales
├── agents/               el grafo LangGraph y sus siete agentes
│   ├── graph.py            plan único + una replanificación, coste acotado
│   ├── orchestrator.py      decide a quién delegar. UNA llamada al modelo
│   ├── executors.py         documental, analítico, visualizador
│   ├── guardian.py          anti-inyección, determinista, 0 tokens
│   ├── memory.py            caché semántico + conversación previa
│   ├── verifier.py          contrasta respuesta contra evidencia, 0 tokens si está sana
│   ├── checkpoint.py        memoria conversacional persistente (SQLite en state/)
│   ├── budget.py            presupuesto de tiempo del turno
│   └── voz.py               el texto que lee el usuario nace de un solo módulo
├── retrieval/            índice FAISS, encoder local bge-m3, agregaciones
├── tools/                tools del agente + registry con traza
├── observability/        traza, registro por turno y consumo de tokens
├── theme/                ÚNICO lugar del Python que lee docs/design/design-tokens.json
└── ui/static/            el chat y el tablero: HTML, CSS y JS plano, sin build ni CDN

docs/
├── design/               bundle visual — fuente de verdad del tema (leído en runtime)
├── architecture.md        arquitectura del sistema desplegado y sus porqués
└── decisions/             ADRs

scripts/                  verificación del despliegue y batería de prompt injection
state/                    memoria conversacional — volumen escribible, aparte de data/
data/                     índice vectorial — se monta en SOLO LECTURA, no se versiona
tests/                    pytest — contrato del API, agentes y pruebas JS del frontend
```

## Reglas que hace cumplir este repo

| Regla | Dónde se verifica |
|---|---|
| Ningún color hexadecimal en `src/**/*.py` fuera de `src/theme/` | `tests/test_theme.py` |
| El contrato HTTP no cambia sin querer | `tests/test_contract.py` |
| El tablero no inventa ni un dato | `tests/test_tablero_sin_datos_inventados.py` |
| Ningún endpoint devuelve 500 ni 422 | `tests/test_contract.py`, `tests/test_chat.py` |
| Ningún secreto ni dependencia copyleft | `../arpia-bundle/scripts/preflight.py` |

La regla equivalente en el frontend —ningún hex fuera de `css/tokens.css`— está
declarada en [`FRONTEND.md`](FRONTEND.md) pero **no tiene prueba que la haga
cumplir**: `test_theme.py` solo recorre los `.py`.

## Licencia

Apache 2.0 — ver [`LICENSE`](LICENSE).
