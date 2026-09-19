# FRONTEND.md — Guía del frontend

> **Qué es esto.** La guía de trabajo del frontend: stack, reglas de color,
> accesibilidad y la forma de los datos que sirve el backend. Complementa
> [`../RETO.md`](../RETO.md) (qué exige ADL) y [`docs/architecture.md`](docs/architecture.md)
> (por qué el sistema es como es).
>
> **Alineado con el backend a 19 de septiembre de 2026.** Hasta esa fecha este
> documento describía un frontend planeado (Plotly, Leaflet, `/api/graph`,
> `group_by: "mes"`) que el backend nunca sirvió; `API.md` §14 listaba las nueve
> discrepancias. Ya están corregidas aquí. La fuente de verdad del contrato sigue
> siendo [`API.md`](API.md): ante conflicto, manda `API.md`.

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
  en `vendor/`. Si la red del venue falla durante la evaluación del
  sábado y el tablero depende de un CDN, perdemos el Reto 2 completo por algo
  ajeno a nuestro trabajo.
- Cualquier color hexadecimal fuera de `css/tokens.css`.
- `fetch()` fuera de `js/api.js`.

**Librerías vendorizadas:** `chart.umd.min.js` (Chart.js — el único que se
carga, solo en `dashboard.html`). `leaflet.js` + `leaflet.css` siguen en el repo
pero **ya no se cargan**: el corpus no tiene dato geográfico y no hay mapa que
dibujar (ver `/api/geo` más abajo).

---

## Estructura de archivos

La raíz es **`src/ui/static/`**, no `static/`. Es lo que `src/api/routing.py`
monta en `/static/...` y en `/...`.

```
src/ui/static/
├── chat.html           Reto 1
├── dashboard.html      Reto 2 — único que carga Chart.js
├── css/
│   ├── tokens.css      variables de color — ÚNICO archivo con hex
│   ├── app.css         layout, componentes, estados
│   ├── tablero.css     rejilla y paneles del tablero
│   └── referencias.css tooltip y visor de documento
├── js/
│   ├── api.js          única capa que hace fetch()
│   ├── chat.js         envío de turnos, render de mensajes
│   ├── dashboard.js    los cuatro paneles del tablero (Chart.js)
│   ├── viewspec.js     traduce un ViewSpec en la llamada de datos
│   └── referencias.js  tooltip de procedencia y visor del documento
├── vendor/             chart.js (en uso), leaflet (sin uso) — nunca CDN
├── fonts/              Inter y JetBrains Mono, servidas localmente
└── img/, logo.jpg, fondo.jpg
```

No existen `charts.js`, `map.js` ni `graph.js`, y no hacen falta: los gráficos
viven en `dashboard.js`, y mapa y grafo de entidades no tienen datos detrás.

Regla de dependencias: `chat.js`, `dashboard.js`, `viewspec.js` y
`referencias.js` llaman a `api.js`. `api.js` no llama a nadie. Ningún archivo de
render hace `fetch` por su cuenta.

**Pruebas del frontend:** `tests/js/*.test.mjs` (`node --test`, se ejecutan
dentro de pytest). Cubren `viewspec.js` y `referencias.js`.

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
    "tokens_por_agente": [{"agente": "orquestador", "modelo": "...", "total": 900}],
    "latencia_ms": 2340,
    "estado": "ok"
  },
  "mode": "live",
  "view_spec": null,
  "citations": [
    {
      "doc_id": "F2-SWF-117",
      "chunk_id": "F2-SWF-117#12",
      "fuente": "F2/SWF_Global/informe.pdf",
      "fragmento": "texto citado, recortado",
      "formato": "pdf",
      "posicion": 12,
      "total_fragmentos": 87,
      "anio": 2019
    }
  ]
}
```

- `respuesta` → burbuja del asistente.
- `metadata.agentes_invocados` → chips de agentes.
- `citations` → bloques de evidencia con botón de trazabilidad.
- `view_spec` → si no es `null`, hay que renderizar un componente.
- `mode` → `"stub"` significa **respuesta simulada**; hay que marcarlo en pantalla.

**Una cita NO trae `quote` ni `score`.** El texto está en `fragmento` y la
procedencia en `fuente`. Los cinco últimos campos (`formato`, `posicion`,
`total_fragmentos`, `anio`, y a veces `fuente`) son **opcionales**: una cifra
agregada o el modo stub pueden no traerlos, así que hay que ocultar la parte que
falte, no pintar "undefined". Esquema exacto: `Citation` en `src/api/contracts.py`.

### Endpoints de soporte

Todos responden **200 siempre**. Un fallo o un dato inexistente llega como
`{"disponible": false, "motivo": "…"}`, para poder distinguir "no hay dato" de
"el servicio se cayó". Todos cuestan 0 tokens.

| Ruta | Devuelve |
|---|---|
| `GET /api/components` | Catálogo de componentes y valores reales de cada dimensión |
| `GET /api/aggregate?metrica=&group_by=&fenomenos=&organizacion=&desde=&hasta=&limite=` | `filas[{clave, valor, doc_ids}]`, `total`, `cobertura` |
| `GET /api/timeline?fenomenos=&desde=&hasta=` | Serie **anual**, con `cobertura` y `aviso` |
| `POST /api/view` | Resuelve un `ViewSpec` completo a sus datos |
| `GET /api/geo` | **Siempre `disponible: false`**: el corpus no tiene lugar |
| `GET /api/evidence/{chunk_id}` | Fragmento original completo, con su procedencia |
| `GET /api/document/{doc_id}?chunk_id=&posicion=&ventana=` | El documento reconstruido con los fragmentos vecinos |
| `GET /api/progress?sesion=` | Por dónde va el turno en curso (agentes y tools ya reportados) |

Dos detalles que cuestan tiempo si se descubren tarde:

- El filtro de fenómeno es **`fenomenos`, en plural**, y admite varios separados
  por coma (`?fenomenos=F1,F2`). `?fenomeno=F3` se ignora en silencio.
- `desde` y `hasta` son **años enteros** (`2024`), no fechas.

**`GET /api/graph` no existe.** No hay extracción de entidades en el sistema, así
que no hay nodos ni aristas que pedir.

---

## ViewSpec — cómo se renderiza

Cuando `view_spec` no es `null`:

```json
{
  "chart": "timeline",
  "metrica": "conteo_documentos",
  "fenomenos": ["F3"],
  "desde": "2024",
  "hasta": null,
  "group_by": "anio",
  "titulo": "Actividad territorial desde 2024",
  "nota": "Solo el 34% de los documentos declara año."
}
```

El esquema es **cerrado** (`extra="forbid"` en `src/api/contracts.py`): un campo
que no esté en la lista hace fallar la validación entera y la vista se pierde.
Lo que hay, y nada más:

| Campo | Valores admitidos |
|---|---|
| `chart` | `timeline`, `bar`, `stacked_bar`, `donut`, `table`, `kpi` |
| `metrica` | `conteo_documentos`, `conteo_fragmentos` |
| `group_by` | `fenomeno`, `organizacion`, `fuente`, `formato`, `anio` |
| `fenomenos` | `F1`, `F2`, `F3` (vacío = los tres) |
| `desde`, `hasta` | año de 4 dígitos como texto (`"2024"`), patrón `^\d{4}$` |
| `titulo`, `nota` | texto libre |

Lo que **no** existe, y por qué: `map` y `network` (el corpus no trae lugar ni
actores), `lugar` y `actor` (mismos datos que no hay), `mes` y `trimestre` (el
año es la única granularidad que el corpus sostiene). Pedir cualquiera de ellos
no falla "un poco": invalida el `ViewSpec` completo.

`viewspec.js` (función `cargar`) traduce el spec en la llamada de datos:

| `chart` | Endpoint | Render |
|---|---|---|
| `timeline` | `/api/timeline` (o `/api/aggregate` con `group_by=anio`) | Chart.js, línea por fenómeno |
| `bar`, `stacked_bar`, `donut`, `table`, `kpi` | `/api/aggregate` | Chart.js o tabla HTML |

Alternativa en un solo paso: mandar el `ViewSpec` tal cual a `POST /api/view` y
recibir `filas`, `total`, `cobertura` y `aviso` ya resueltos, validados contra el
mismo esquema que emite el agente. Es lo preferible cuando el spec viene del chat.

**`nota` y `aviso` se muestran siempre junto a la vista.** No son decoración:
solo el 34% de los documentos declara año, y una serie temporal que oculte eso
convierte un conteo honesto en una cifra engañosa.

Un componente activo a la vez. La especificación es explícita: *el sistema no
debe limitarse a mostrar todos los componentes a la vez en un dashboard
estático.*

---

## Tres detalles de UI que valen puntos

Los tres están **implementados**; se documentan aquí para que nadie los rompa al
refactorizar.

**1. Chips de agentes invocados.** Bajo cada respuesta del asistente, una fila
con los agentes que participaron, leída de `metadata.agentes_invocados`, más
interacciones, latencia y tokens. Hace visible la arquitectura multiagente a
quien evalúa sin que tenga que abrir el código.

**2. Evidencia con trazabilidad.** Vive en `js/referencias.js` y
`css/referencias.css`, y la usan el chat y el tablero. Tres gestos, de menor a
mayor costo: pasar el ratón por un `doc_id` abre un tooltip con su procedencia y
el fragmento (0 peticiones, sale de `citations`); un clic abre el fragmento
completo (`/api/evidence/{chunk_id}`); dentro del visor, "Ver el documento" trae
los fragmentos vecinos con el citado resaltado (`/api/document/{doc_id}`).
Funciona con teclado: Enter abre, Escape cierra y devuelve el foco. Es un
requisito obligatorio de la especificación.

**3. Puente entre los dos retos.** Una respuesta del chat con `view_spec` enlaza
al tablero con `#vista=<json>`, y el tablero la resuelve por `POST /api/view`.

**4. Progreso en vivo.** Mientras el turno corre, `GET /api/progress?sesion=`
dice qué agentes y herramientas ya reportaron. Son datos reales: un paso solo
aparece cuando su span cerró de verdad. Nada se estima.

---

## Distribución del dashboard

Lo que hay montado en `dashboard.html`: asistente a la izquierda, cuatro paneles
a la derecha.

```
┌──────────────────┬──────────────────────────────────────┐
│                  │  Evolución temporal  │ Sin ubicación │
│  asistente:      │  (línea/fenómeno)    │ (el corpus no │
│  pregunta en     │                      │  trae lugar)  │
│  lenguaje        ├──────────────────────┼───────────────┤
│  natural         │  Distribución de     │ Sin relaciones│
│                  │  eventos             │ (no hay       │
│  fuente + botón  │  (la elige el agente)│  actores)     │
│  "abrir doc"     │                      │               │
└──────────────────┴──────────────────────────────────────┘
```

Cada panel lleva una **insignia de origen**: "Del corpus" cuando los datos vienen
de `/api/aggregate` al abrir, "Del agente" cuando los reemplaza un `ViewSpec`, y
"Simulado" solo en modo stub. Los dos paneles sin datos explican por qué están
vacíos, con el motivo que devuelve el propio backend. **No se dibujan marcadores,
nodos ni series de ejemplo**: `RETO.md` no admite datos simulados en la versión
desplegada, y `tests/test_tablero_sin_datos_inventados.py` falla si vuelven.

---

## Accesibilidad

- Contraste suficiente entre texto y fondo; verificar los grises secundarios.
- Nunca depender solo del color: acompañar con etiqueta, forma o patrón.
- Leyendas, títulos y unidades explícitas en cada visualización.
- Leyendas fuera del área de datos, nunca tapando información.

---

## Seguridad: todo texto del backend entra como texto

**`textContent`, nunca `innerHTML`.** El corpus viene de fuentes externas y un
fragmento puede traer marcado o instrucciones escritas para un modelo. Convertir
eso en HTML es la vía de inyección más barata que existe, y la defensa contra
prompt injection es el 15% del Reto 1 (`RETO.md` §Defensa).

La única excepción es el render de la respuesta en `chat.js` (`renderTexto`),
que construye párrafos, listas, negritas y código **nodo a nodo**: interpreta un
subconjunto mínimo de marcado creando elementos, sin pasar nunca una cadena por
`innerHTML`. Si hace falta ampliarlo, se amplía con la misma técnica.

Un detalle de tamaño: un fragmento llega a 18.000 tokens. `/api/document`
recorta cada uno a 4.000 caracteres y marca `truncado: true`; el texto completo
sigue disponible en `/api/evidence/{chunk_id}`.

---

## Fronteras de archivos — no tocar

Esta guía es para trabajar **solo dentro de `src/ui/static/`**.

No tocar: `src/api/`, `src/agents/`, `src/tools/`, `src/retrieval/`,
`Dockerfile`, `pyproject.toml`.

Si hace falta un endpoint nuevo o cambiar la forma de una respuesta, **no lo
implementes**: anótalo y avísale al arquitecto. El contrato se cambia en un
solo lugar y por una sola persona. Y si el backend cambia, **este documento se
actualiza en el mismo commit**: las nueve discrepancias que tuvo hasta el 19 de
septiembre nacieron de no hacerlo.

## Git

Esta sesión **nunca** ejecuta `git add`, `git commit` ni `git push`. Puede leer
(`git status`, `git diff`). Cuando algo esté listo, escribe los comandos y para.
