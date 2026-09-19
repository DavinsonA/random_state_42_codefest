---
name: arpia-visual-system
description: Aplicar el sistema visual A.R.P.I.A. a cualquier salida con UI o graficos. Usar al crear o modificar el chat o el tablero (src/ui/static/), graficos de Chart.js, o cualquier elemento visual. Tambien al anadir un color, una escala o un estilo nuevo.
---

# Sistema visual A.R.P.I.A.

## Fuente de verdad
`docs/design/design-tokens.json` y `docs/design/visual-system.md`. Leelos antes
de escribir UI. No inventes colores ni tipografias.

## Regla no negociable
**Ningun hexadecimal literal fuera de `src/theme/` (Python) ni de
`src/ui/static/css/tokens.css` (frontend).**

```python
from src.theme.tokens import tokens
color = tokens.brand.primary          # correcto
color = tokens.phenomenon("F2")       # correcto: color semantico de fenomeno
color = "#3566CC"                     # PROHIBIDO — preflight.py lo detecta
```

```css
color: var(--arpia-primary);          /* correcto */
color: #3566CC;                       /* PROHIBIDO fuera de tokens.css */
```

`tokens.css` es el espejo de `design-tokens.json` para el frontend. Si cambia
el JSON, cambian los dos en el mismo commit.

Si necesitas un color que no existe en el JSON: primero busca un token semantico
que sirva. Si de verdad falta, actualiza `design-tokens.json` **y**
`visual-system.md` en el mismo commit.

## Uso semantico
- F1/F2/F3 identifican **fenomenos**, no estados. No los uses por bonitos.
- `semantic.evidence` (ambar) se reserva para citas, referencias y RAG.
- `semantic.critical` (rojo) solo para errores o estados criticos, nunca como
  color decorativo ni como color neutro de datos.
- El azul de marca no sirve como texto pequeno sobre fondo oscuro: usalo en
  bordes, iconos, indicadores y elementos graficos grandes.

## Graficos del tablero (Chart.js)
Los cuatro paneles viven en `src/ui/static/js/dashboard.js`. El color de una
serie sale SIEMPRE de la variable CSS del fenomeno que representa, leida del
documento — nunca de una constante en el JS:

```js
const css = getComputedStyle(document.documentElement);
const color = css.getPropertyValue("--arpia-f2").trim();
```

Un mismo fenomeno lleva su color en todas las vistas, sin excepcion. Si una
grafica no representa fenomenos, usa los colores de marca, no los de F1/F2/F3.

## Evidencia y trazabilidad
`--arpia-evidence` (ambar) esta reservado a citas y referencias: es lo que
vuelve boton un `doc_id` en el texto de una respuesta
(`src/ui/static/js/referencias.js`). No lo uses para nada mas.

## Limite importante
`AGENTS.md` §6: no construyas una libreria de componentes solo porque existen
tokens. Componentes, layouts y navegacion se derivan de requisitos funcionales.
Si el reto no pide un mapa, no hay mapa.
