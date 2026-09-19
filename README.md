# random_state_42_codefest

Monorepo del equipo `random_state = 42` para CODEFEST Ad Astra 2026 (Etapa 2).
Una sola fuente de verdad para el código.

```
random_state_42_codefest/
├── arpia/            el aplicativo — lo único que se despliega y se califica
├── arpia-bundle/     el método — directivas de agente, skills, scripts de desarrollo
└── RETO.md           qué exige ADL y cómo se califica
```

**A.R.P.I.A.** es un sistema multiagente de análisis de fuentes abiertas sobre
inteligencia aeroespacial: responde preguntas citando el documento exacto que
sustenta cada afirmación, y decide qué visualización mostrar en el tablero.

## Por dónde empezar

1. [`RETO.md`](RETO.md) — qué pide ADL, cómo se puntúa y las restricciones duras.
2. [`arpia/API.md`](arpia/API.md) — **qué hay construido de verdad**, el contrato
   de cada endpoint y qué falta. Es la fuente de verdad de la implementación.
3. [`arpia/docs/architecture.md`](arpia/docs/architecture.md) — por qué el sistema
   es así.

## Dónde trabajar

- **Código de producto, API, UI, tema visual, tests**: [`arpia/`](arpia/README.md).
- **Cómo trabajar con agentes de código, skills, scripts de iteración/preflight**:
  [`arpia-bundle/`](arpia-bundle/README.md).
  (se elimina antes de la entrega final).

## Despliegue

Coolify construye **solo** `arpia/`:

- Base Directory: `/arpia`
- Watch Paths: `arpia/**`
- Build pack: Dockerfile

No hay submódulos, subtrees ni separación de repositorios: `arpia-bundle/`
nunca se copia a la imagen porque Coolify solo observa y construye desde
`arpia/**`.

## Licencia

Apache 2.0 — ver [`arpia/LICENSE`](arpia/LICENSE).
