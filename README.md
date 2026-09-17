# random_state_42_codefest

Monorepo del equipo `random_state = 42`. Una sola fuente de verdad para el
código; el reto se publica el 18 de septiembre.

```
random_state_42_codefest/
├── arpia/            el aplicativo — lo único que se despliega y se califica
├── arpia-bundle/     el método — directivas de agente, skills, scripts de desarrollo
└── deploy-test/      app dummy para validar la cadena GitHub → Coolify → URL pública
```

## Dónde trabajar

- **Código de producto, API, UI, tema visual, tests**: [`arpia/`](arpia/README.md).
- **Cómo trabajar con agentes de código, skills, scripts de iteración/preflight**:
  [`arpia-bundle/`](arpia-bundle/README.md).
- **Validación de despliegue en Coolify**: [`deploy-test/`](deploy-test/README.md)
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
