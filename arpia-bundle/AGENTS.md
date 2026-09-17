# A.R.P.I.A. — Agent Instructions

> Este archivo es la directiva raíz para cualquier agente de código
> (Claude Code, Cursor, Codex, OpenCode, Devin). Las secciones 1–6 provienen
> del bundle `ARPIA_visual_foundation_v0.1` y **no deben debilitarse**.
> Las secciones 7+ son reglas del repositorio de competencia.

## REGLA ABSOLUTA — Git

**Ningún agente de código ejecuta `git add`, `git commit`, `git push`,
`git reset`, `git checkout` ni `git rebase`, ni ninguna otra operación que
modifique el estado de git o del remoto.** Leer (`git status`, `git diff`,
`git log`) sí está permitido. `.claude/settings.json` deniega estos comandos
a nivel de configuración; esta línea es el respaldo por si esa configuración
falla o no aplica. Cuando el trabajo esté listo, el agente escribe los
comandos exactos y el usuario los ejecuta él mismo.

---

## 1. Project status

A.R.P.I.A. es una aplicación en evolución. Su alcance funcional final,
arquitectura de información, flujos de trabajo y framework de frontend
**no se consideran fijos**.

No infieras ni inventes funcionalidad de la aplicación a partir del
sistema visual.

## 2. Visual foundation

Antes de crear o modificar código de frontend/UI, consulta:

- `docs/design/visual-system.md`
- `docs/design/design-tokens.json`

Son la fuente de verdad del fundamento visual de A.R.P.I.A.

**Regla de implementación en este repo:** nunca escribas un color
hexadecimal literal en código de aplicación. Los tokens se consumen
exclusivamente a través de `src/theme/tokens.py`, que lee
`docs/design/design-tokens.json` en tiempo de ejecución. Si un color no
existe en el JSON, no existe en la aplicación.

## 3. Framework independence

El fundamento visual es deliberadamente agnóstico al framework.

No asumas ni introduzcas un framework de frontend basándote en estos
documentos. El frontend eventual puede ser Python o un framework
compatible con Python.

**Estado en este repo:** el equipo seleccionó **Streamlit** como frontend
primario (ver `docs/architecture.md` §4). Esa selección es una decisión de
proyecto, no una propiedad del fundamento visual. La capa de adaptación
vive aislada en `src/theme/` para que cambiar de framework no obligue a
tocar los tokens.

## 4. Semantic color rules

Usa tokens semánticos en vez de colores arbitrarios.

Fenómenos:
- F1 — IA y Capacidades Estratégicas: `#3566CC`
- F2 — Seguridad del Entorno Espacial: `#54B1DC`
- F3 — Dinámicas Territoriales: `#10B981`

Semántica del sistema:
- Success / operational: `#10B981`
- Information: `#54B1DC`
- Warning / evidence: `#F59E0B`
- Critical / error: `#EF4444`

Foundation:
- Void: `#05040D`
- Background: `#040C1D`
- Surface: `#0F1B30`
- Elevated: `#16243A`

## 5. Visual direction

A.R.P.I.A. debe sentirse: analítica, aeroespacial, técnica, precisa,
profesional, densa en información pero controlada.

Evitar: estética cyberpunk genérica, neón excesivo, glow excesivo,
elementos sci-fi decorativos sin propósito funcional, colores brillantes
arbitrarios, complejidad visual que compita con la información analítica.

## 6. Important constraint

**No crees un sistema completo de componentes de UI solo porque existen
tokens visuales.** Componentes, layouts, interacciones, navegación,
dashboards, mapas, estructuras de chat y demás patrones deben derivarse de
los requisitos funcionales eventuales de la aplicación.

Si el reto no pide un mapa, no construyas un mapa.

## 7. Restricciones de la competencia (no negociables)

- **Licencia**: todo el código propio bajo Apache 2.0. Ninguna dependencia
  GPL/AGPL/LGPL copyleft fuerte. Una licencia restrictiva **descalifica al
  equipo**. Antes de añadir cualquier dependencia, verificar licencia:
  `uv run python scripts/preflight.py --licenses`.
- **Modelos**: solo modelos open-weight servidos por el gateway del evento.
  No llamar APIs comerciales de LLM directamente.
- **Secretos**: nunca hardcodear claves. Todo por variable de entorno.
  `scripts/preflight.py` falla el build si detecta un patrón de secreto.
- **Presupuesto de tokens**: cada llamada al gateway consume presupuesto
  compartido del equipo. Antes de añadir un paso agéntico, preguntar si un
  paso determinista resuelve lo mismo.

## 8. Reglas de diseño de agentes

Antes de crear un agente nuevo, responde estas seis preguntas en el
docstring del módulo. Si no puedes responderlas, el agente no está
suficientemente definido para escribirse:

1. Propósito
2. Entrada que recibe
3. Salida que produce
4. Criterio de éxito
5. Autoridad sobre el sistema (solo lectura / escritura / acción externa)
6. **Qué NO debe saber** (frontera de aislamiento de contexto)

Reglas duras:

- Todo bucle agéntico lleva **tope máximo de iteraciones**. Sin excepción.
- El *docstring* de una tool es el prompt que lee el modelo: describe
  cuándo usarla, cuándo **no**, y la forma exacta de los argumentos.
- Un solo agente bien equipado antes que varios coordinándose. Añadir un
  agente exige justificar qué capacidad compra.
- Toda acción irreversible pasa por confirmación humana explícita.

## 9. Convenciones de código

- Python 3.11+. Gestión con `uv`. Lint y formato con `ruff`.
- Nombres de código en inglés; docstrings y comentarios de negocio en español.
- Type hints obligatorios en funciones públicas.
- Sin `print()` en código de aplicación: usar el logger de `src/config.py`.
- Módulos cortos y de una responsabilidad. Si un archivo pasa de ~200
  líneas, probablemente son dos.

## 10. Cambios al fundamento visual

Si la implementación revela la necesidad de un token visual nuevo:

1. Verifica si un token semántico existente satisface el requisito.
2. No crees un color o estilo de un solo uso si un token semántico sirve.
3. Si de verdad hace falta un token nuevo, actualiza `design-tokens.json`
   **y** `visual-system.md` juntos, en el mismo commit.
4. Preserva la consistencia semántica en toda la aplicación.
