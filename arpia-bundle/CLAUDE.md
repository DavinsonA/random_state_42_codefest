# CLAUDE.md — Manual de operación

> Claude Code lee este archivo automáticamente al iniciar sesión en la raíz
> del repo. Está optimizado para trabajo en terminal durante un evento de
> 24 horas. Mantenlo corto: un CLAUDE.md desactualizado es peor que ninguno.

**Lee `AGENTS.md` antes de escribir cualquier código.** Contiene las reglas
del sistema visual y las restricciones de la competencia. Este archivo solo
cubre operación.

## REGLA ABSOLUTA — Git

**Nunca ejecutes `git add`, `git commit`, `git push`, `git reset`,
`git checkout` ni `git rebase`.** Leer sí (`git status`, `git diff`,
`git log`). `.claude/settings.json` lo deniega a nivel de configuración;
esta línea es el respaldo escrito. Cuando el trabajo esté listo, escribe los
comandos exactos y espera a que el usuario los ejecute.

---

## Estado del proyecto

| Campo | Valor |
|---|---|
| Nombre | A.R.P.I.A. |
| Reto | **NO DEFINIDO** — se publica el 18 de septiembre |
| Línea de trabajo activa | **NO DEFINIDA** — ver `docs/architecture.md` |
| Frontend | Streamlit (decisión tomada, ver `../arpia/docs/architecture.md` §4) |
| Framework de agentes | LangGraph |

> **Al iniciar el evento**, actualiza esta tabla en el primer commit. Es lo
> primero que lee cualquier agente y lo que evita que construya la línea
> equivocada.

---

## Comandos

> El código vive en `../arpia` (repo hermano dentro del mismo monorepo). Los
> comandos de `uv` (sync, run, add, pytest, ruff) se ejecutan **desde
> `arpia/`**. Los scripts de `arpia-bundle/scripts/` operan sobre `../arpia`
> vía la variable `ARPIA_ROOT` (por defecto ya apunta ahí) y pueden invocarse
> desde cualquiera de las dos carpetas.

### Entorno

```bash
bash scripts/setup.sh              # instala uv, sincroniza ../arpia, verifica gateway
cd ../arpia
source .venv/bin/activate
uv sync                            # re-sincronizar tras cambiar dependencias
uv add <paquete>                   # añadir dependencia (verifica licencia antes)
```

### Desarrollo

```bash
# desde arpia-bundle/
uv run --project ../arpia python scripts/run_node.py --list
uv run --project ../arpia python scripts/run_node.py retrieve --input "..."
uv run --project ../arpia python scripts/run_node.py --graph --input "..." --json

# desde arpia/
uv run uvicorn src.api.main:app --reload --port 8000      # API (lo que evalúa el jurado)
uv run streamlit run src/ui/app.py                        # UI
```

`run_node.py` es la herramienta principal de iteración: prueba lógica de
agentes sin levantar la UI, imprime la traza y el costo estimado.

### Calidad

```bash
# desde arpia/
uv run ruff check src/ tests/ --fix
uv run ruff format src/ tests/
uv run pytest tests/ -q

# desde cualquiera de las dos carpetas (usa ARPIA_ROOT internamente)
uv run --project ../arpia python ../arpia-bundle/scripts/preflight.py   # TODAS las verificaciones pre-deploy
```

### Despliegue (Coolify)

```bash
uv run --project ../arpia python scripts/preflight.py     # OBLIGATORIO antes de push
# el usuario ejecuta el commit/push — este repo nunca lo hace por sí mismo
# git add -A && git commit -m "..." && git push origin main
# Coolify despliega automáticamente al detectar el push (Base Directory=/arpia)
cd ../arpia && docker compose up --build                  # reproducir el build localmente primero
```

---

## Reglas de trabajo durante el evento

1. **Nunca hardcodear un color.** `from src.theme import tokens` y usa el
   token semántico. Si no existe, no se usa.
2. **Nunca hardcodear un secreto.** `preflight.py` falla el build si lo
   detecta. Todo por `.env` (ver `.env.example`).
3. **Todo bucle agéntico lleva tope de iteraciones.** Sin excepción.
4. **Antes de añadir un agente**, justifica qué capacidad compra que no se
   obtenga con un paso determinista.
5. **Feature freeze a las 20h.** Después solo bugfix, documentación y pitch.
6. **Si una tool falla, devuelve texto de error** — nunca lanza excepción
   que tumbe el grafo.

---

## Cómo pedirme cosas (patrones que funcionan)

Bien:
- *"Añade una tool `search_corpus` en `src/tools/` que envuelva el retriever
  de `src/retrieval/`. Docstring completo con cuándo usarla y cuándo no.
  Regístrala en el registry. Escribe el test."*
- *"Convierte los tokens de `design-tokens.json` en un template de Plotly y
  aplícalo en `src/theme/plotly_theme.py`. No inventes colores."*
- *"Corre `run_node.py retrieve` con estas 3 consultas y dime en qué falla
  el ranking."*

Mal:
- *"Haz la UI bonita"* → no hay criterio verificable; terminarás con
  componentes inventados que violan `AGENTS.md` §6.
- *"Construye el dashboard"* → ¿qué dashboard? El reto define eso.

---

## Estructura

El código vive en `../arpia` (repo hermano). Este repo (`arpia-bundle/`) solo
contiene el método: instrucciones para agentes, skills y scripts.

```
../arpia/src/
├── config.py          # configuración central, logger, lectura de .env
├── theme/             # ÚNICO lugar que toca design-tokens.json
│   ├── tokens.py      #   carga y expone tokens tipados
│   ├── streamlit_theme.py
│   └── plotly_theme.py
├── retrieval/         # adaptador al índice vectorial existente
├── tools/             # tools del agente (una función = una tool)
├── agents/            # estado + grafo LangGraph
├── api/               # FastAPI: el endpoint que consume el jurado
│   └── contracts.py   #   ÚNICO lugar con los esquemas Pydantic de la API
└── ui/                # Streamlit
```

Regla: `theme/` no importa de `agents/`. `tools/` no importa de `ui/`.
Las dependencias fluyen hacia abajo, nunca en círculo.

```
arpia-bundle/
├── AGENTS.md / CLAUDE.md   # directivas para agentes de código (este archivo)
├── .claude/skills/         # skills reutilizables para Claude Code
├── scripts/                # setup, iteración por nodo, preflight — operan sobre ../arpia
├── docs/prompts/           # prompts versionados
└── lab/                    # experimentos desechables, nada de aquí se despliega
```

---

## Fallos frecuentes y su causa

| Síntoma | Causa probable |
|---|---|
| Colores no coinciden con el bundle | alguien escribió un hex literal; busca con `scripts/preflight.py --tokens` |
| El grafo no termina | falta tope de iteraciones en la arista condicional |
| El jurado no puede consumir la API | el esquema de respuesta cambió; ver `../arpia/src/api/contracts.py` y el handbook |
| Presupuesto de tokens agotado | un bucle reintentando; revisa la traza con `run_node.py --graph` |
| Coolify no despliega | falta `Dockerfile` en `arpia/` (Base Directory del panel) o variable de entorno sin configurar |
