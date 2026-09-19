# FRONTEND.md — Contexto para la sesión de Claude Code (frontend)

> Pegar esto al inicio de la sesión, o dejarlo en `arpia/static/FRONTEND.md`
> para que Claude Code lo lea. Complementa `RETO.md` y `architecture-layers.md`.

---

## Qué construimos

Dos páginas, servidas por el mismo backend en FastAPI:

| Archivo | Subdominio | Qué es |
|---|---|---|
| `chat.html` | `frontagent.*` | Conversación a pantalla completa. **Es el Reto 1** |
| `dashboard.html` | `dashboard.*` | Tablero + panel de chat lateral. **Es el Reto 2** |

El backend enruta por cabecera `Host` y sirve el archivo correcto en `/`. El
frontend **no** maneja esa lógica: solo existen dos HTML distintos.

---

## Stack — y lo que está prohibido

**Se usa:** HTML, CSS y JavaScript plano. Sin framework, sin build, sin
transpilación, sin `npm`. Los archivos se sirven tal como se escriben.

**Prohibido:**
- React, Vue, Svelte, Tailwind, Bootstrap o cualquier framework.
- Cualquier `<script src="https://cdn...">`. Las librerías van **vendorizadas**
  en `static/vendor/`. Si la red del venue falla durante la evaluación del
  sábado y el tablero depende de un CDN, perdemos el Reto 2 completo por algo
  ajeno a nuestro trabajo.
- Cualquier color hexadecimal fuera de `css/tokens.css`.
- `fetch()` fuera de `js/api.js`.

**Librerías vendorizadas disponibles:** `plotly.min.js` (gráficos),
`leaflet.js` + `leaflet.css` (mapas).

---

## Estructura de archivos

```
static/
├── chat.html
├── dashboard.html
├── css/
│   ├── tokens.css      variables de color — ÚNICO archivo con hex
│   └── app.css         layout, componentes, estados
├── js/
│   ├── api.js          única capa que hace fetch()
│   ├── chat.js         envío de turnos, render de mensajes
│   ├── viewspec.js     traduce un ViewSpec en la llamada y el render
│   ├── charts.js       Plotly con el tema
│   ├── map.js          Leaflet con capas por fenómeno
│   └── graph.js        red de entidades
└── vendor/             plotly, leaflet — nunca CDN
```

Regla de dependencias: `chat.js` y `viewspec.js` llaman a `api.js`. `api.js` no
llama a nadie. Ningún archivo de render hace `fetch` por su cuenta.

---

## tokens.css — la fuente de verdad del color

```css
:root {
  --arpia-void: #05040D;
  --arpia-bg: #040C1D;
  --arpia-surface: #0F1B30;
  --arpia-elevated: #16243A;
  --arpia-border: #233E4D;
  --arpia-border-active: #2B4B5D;

  --arpia-deep: #003F5E;
  --arpia-primary: #3566CC;
  --arpia-electric: #1B68BC;
  --arpia-space: #54B1DC;

  --arpia-f1: #3566CC;   /* IA en entornos militares */
  --arpia-f2: #54B1DC;   /* Seguridad espacial */
  --arpia-f3: #10B981;   /* Dinámicas territoriales */

  --arpia-success: #10B981;
  --arpia-info: #54B1DC;
  --arpia-warning: #F59E0B;
  --arpia-critical: #EF4444;
  --arpia-evidence: #F59E0B;

  --arpia-text: #F0F6FC;
  --arpia-text-secondary: #A1A5A9;
  --arpia-text-muted: #6A737C;
  --arpia-text-disabled: #49626F;
}
```

**Uso semántico, no decorativo:**
- `--arpia-f1/f2/f3` identifican **fenómenos**. Un mismo fenómeno lleva el
  mismo color en todas las vistas, sin excepción.
- `--arpia-evidence` (ámbar) se reserva para **citas y trazabilidad**. No se usa
  para nada más.
- `--arpia-critical` (rojo) solo para errores y estados críticos. Nunca como
  color de dato.
- El azul de marca no sirve para texto pequeño sobre fondo oscuro: úsenlo en
  bordes, íconos y elementos gráficos grandes.

**Dirección visual:** analítico, aeroespacial, técnico, preciso, denso en
información pero controlado. Evitar estética cyberpunk, neón, glow, degradados
llamativos, e iconografía genérica de IA (cerebros, robots, redes neuronales).
La identidad viene de composición, jerarquía y densidad — no de adornos.
Esquinas poco redondeadas, bordes de 1px para separar, sombras suaves o ninguna.

---

## Lo que devuelve el backend

### `POST /chat`

Formato fijado por ADL. **No se puede cambiar.** Lo que el frontend consume:

```json
{
  "respuesta": "texto en lenguaje natural para mostrar al usuario",
  "evaluacion": {
    "input": "...",
    "actual_output": "...",
    "retrieval_context": ["fragmento 1", "fragmento 2"],
    "tools_called": [{"name": "...", "input_parameters": {}, "output": "..."}]
  },
  "metadata": {
    "num_interacciones": 2,
    "agentes_invocados": ["orquestador", "agente_documental"],
    "tokens": {"input": 2130, "output": 410, "total": 2540},
    "latencia_ms": 2340,
    "estado": "ok"
  },
  "view_spec": null,
  "citations": [{"doc_id": "...", "chunk_id": "...", "quote": "...", "score": 0.81}]
}
```

- `respuesta` → burbuja del asistente.
- `metadata.agentes_invocados` → chips de agentes.
- `citations` → bloques de evidencia con botón de trazabilidad.
- `view_spec` → si no es `null`, hay que renderizar un componente.

### Endpoints de soporte

| Ruta | Devuelve |
|---|---|
| `GET /api/components` | Catálogo de componentes disponibles |
| `GET /api/aggregate?metrica=&group_by=&fenomeno=&desde=&hasta=` | Datos agregados |
| `GET /api/timeline?fenomeno=&desde=&hasta=` | Serie temporal |
| `GET /api/geo?fenomeno=&desde=&hasta=` | Puntos o regiones con conteos |
| `GET /api/graph?fenomeno=` | Nodos y aristas |
| `GET /api/evidence/{chunk_id}` | Fragmento original completo |

---

## ViewSpec — cómo se renderiza

Cuando `view_spec` no es `null`:

```json
{
  "chart": "timeline",
  "fenomenos": ["F3"],
  "desde": "2024-01-01",
  "hasta": null,
  "lugar": null,
  "group_by": "mes",
  "titulo": "Actividad territorial desde 2024"
}
```

`viewspec.js` traduce eso en la llamada correcta y el render correcto:

| `chart` | Endpoint | Render |
|---|---|---|
| `timeline` | `/api/timeline` | Plotly, línea por fenómeno |
| `bar` | `/api/aggregate` | Plotly, barras |
| `map` | `/api/geo` | Leaflet, capa por fenómeno |
| `table` | `/api/aggregate` | Tabla HTML |

Un componente activo a la vez. La especificación es explícita: *el sistema no
debe limitarse a mostrar todos los componentes a la vez en un dashboard
estático.*

---

## Tres detalles de UI que valen puntos

**1. Chips de agentes invocados.** Bajo cada respuesta del asistente, una fila
con los agentes que participaron, leída de `metadata.agentes_invocados`, más
interacciones, latencia y tokens. Hace visible la arquitectura multiagente a
quien evalúa sin que tenga que abrir el código.

**2. Evidencia con trazabilidad.** Cada cita se muestra en un bloque con borde
izquierdo ámbar y su `doc_id` en monoespaciada. Al hacer clic, abre el
fragmento completo vía `/api/evidence/{chunk_id}`. Es un requisito obligatorio
de la especificación, y es lo que se demuestra en el pitch cuando pregunten por
verificación de fuentes.

**3. Botón "Visualizar esto".** En cualquier respuesta del chat, reenvía el
turno al backend pidiendo explícitamente una visualización. Es el puente
visible entre Reto 1 y Reto 2.

---

## Distribución del dashboard

```
┌──────────────────────────────────────┬──────────────────┐
│  filtros globales: fenómeno · fechas │                  │
├──────────────────────────────────────┤   panel de chat  │
│                                      │                  │
│   componente activo                  │   el usuario     │
│   (lo elige el agente visualizador)  │   pide vistas en │
│                                      │   lenguaje       │
├──────────────────────────────────────┤   natural        │
│   evidencia del elemento seleccionado│                  │
└──────────────────────────────────────┴──────────────────┘
```

---

## Si ya hay código montado — cómo formatearlo

Antes de seguir construyendo, migrar lo existente en este orden:

1. **Extraer todos los hexadecimales** a `tokens.css` y reemplazarlos por
   `var(--arpia-*)`. Si un color no corresponde a ningún token, no va: elegir
   el token semántico más cercano.
2. **Mover todo `fetch()` a `api.js`.** Cada función de `api.js` devuelve JSON
   ya parseado y lanza un error legible si falla.
3. **Eliminar cualquier `<script src>` externo** y vendorizar la librería.
4. **Revisar contraste**: texto secundario sobre superficie debe ser legible.
   Si un color de dato solo se distingue por matiz, añadir etiqueta o forma —
   el color no puede ser el único portador de significado.
5. **Revisar que los fenómenos usen su color semántico** y el mismo en todas
   las vistas.

---

## Accesibilidad

- Contraste suficiente entre texto y fondo; verificar los grises secundarios.
- Nunca depender solo del color: acompañar con etiqueta, forma o patrón.
- Leyendas, títulos y unidades explícitas en cada visualización.
- Leyendas fuera del área de datos, nunca tapando información.

---

## Fronteras de archivos — no tocar

Hay otra sesión de Claude Code trabajando el backend en paralelo. **Esta sesión
solo modifica `static/`.**

No tocar: `src/api/`, `src/agents/`, `src/tools/`, `src/retrieval/`,
`Dockerfile`, `pyproject.toml`.

Si hace falta un endpoint nuevo o cambiar la forma de una respuesta, **no lo
implementes**: anótalo y avísale al arquitecto. El contrato se cambia en un
solo lugar y por una sola persona.

## Git

Esta sesión **nunca** ejecuta `git add`, `git commit` ni `git push`. Puede leer
(`git status`, `git diff`). Cuando algo esté listo, escribe los comandos y para.
