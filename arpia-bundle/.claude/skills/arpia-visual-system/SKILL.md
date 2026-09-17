---
name: arpia-visual-system
description: Aplicar el sistema visual A.R.P.I.A. a cualquier salida con UI o graficos. Usar al crear o modificar vistas de Streamlit, figuras de Plotly, mapas o cualquier elemento visual. Tambien al anadir un color, una escala o un estilo nuevo.
---

# Sistema visual A.R.P.I.A.

## Fuente de verdad
`docs/design/design-tokens.json` y `docs/design/visual-system.md`. Leelos antes
de escribir UI. No inventes colores ni tipografias.

## Regla no negociable
**Ningun hexadecimal literal fuera de `src/theme/`.**

```python
from src.theme.tokens import tokens
color = tokens.brand.primary          # correcto
color = tokens.phenomenon("F2")       # correcto: color semantico de fenomeno
color = "#3566CC"                     # PROHIBIDO — preflight.py lo detecta
```

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

## Streamlit
```python
from src.theme.streamlit_theme import apply, evidence_block
apply()   # PRIMERA llamada del script: configura pagina, CSS y Plotly
st.markdown(evidence_block(texto, meta=f"{doc_id} · p.{pagina}"), unsafe_allow_html=True)
```

## Plotly
`apply()` ya registra el template `arpia` como predeterminado. No pases
`color_discrete_sequence` a mano salvo que mapees fenomenos:

```python
fig = px.bar(df, x="mes", y="n", color="fenomeno",
             color_discrete_map=tokens.phenomenon_map())
```

Escalas: `SEQUENTIAL` para magnitud; `DIVERGING` **solo** si la variable tiene
negativo, neutro y positivo con significado real.

## Limite importante
`AGENTS.md` §6: no construyas una libreria de componentes solo porque existen
tokens. Componentes, layouts y navegacion se derivan de requisitos funcionales.
Si el reto no pide un mapa, no hay mapa.
