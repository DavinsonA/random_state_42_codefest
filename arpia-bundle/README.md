# A.R.P.I.A. — bundle de desarrollo

Este es el **método**, no la aplicación. El código que se despliega vive en
[`../arpia`](../arpia); esta carpeta nunca contiene una segunda copia de él.

## Qué es y qué no es

**Es**: directivas para agentes de código, un catálogo de skills reutilizables,
scripts de iteración/preflight que operan sobre `../arpia`, y prompts
versionados (incluido el del pitch).

**No es**: código de producto. No hay `src/`, no hay `Dockerfile`, no hay
dependencias de runtime. Si necesitas tocar el aplicativo, hazlo en
`../arpia`.

## Arranque

```bash
bash scripts/setup.sh          # sincroniza ../arpia, genera .env, verifica gateway
uv run --project ../arpia python scripts/run_node.py --list
```

Ver comandos completos en [`CLAUDE.md`](CLAUDE.md).

## Estructura

```
AGENTS.md                 directivas para agentes de código (leer primero)
CLAUDE.md                 manual de operación en terminal
.claude/skills/            12 skills reutilizables para Claude Code
scripts/                  setup, iteración por nodo, preflight — operan sobre ../arpia
docs/prompts/              prompts versionados (incluye el del pitch)
docs/architecture.md       enlace a ../arpia/docs/architecture.md
lab/                       experimentos desechables — nada de aquí se despliega
```

## Reglas que el andamiaje hace cumplir (sobre `../arpia`)

| Regla | Dónde se verifica |
|---|---|
| Ningún color literal fuera de `src/theme/` | `scripts/preflight.py`, `arpia/tests/test_theme.py` |
| Ningún secreto en el código | `scripts/preflight.py --secrets` |
| Ninguna dependencia copyleft fuerte | `scripts/preflight.py --licenses` |
| Todo bucle agéntico con tope de iteraciones | `scripts/preflight.py --iterations` |
| Contrato HTTP congelado no cambia sin querer | `arpia/tests/test_contract.py` |
| Una tool nunca tumba el grafo | `arpia/src/tools/registry.py` |

## Antes de desplegar

```bash
uv run --project ../arpia python scripts/preflight.py   # obligatorio
cd ../arpia && docker compose up --build                # reproducir el build de Coolify
```

## Licencia

El código en `../arpia` está bajo Apache 2.0. Este bundle se distribuye con
el mismo repositorio y las mismas condiciones.
