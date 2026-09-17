# Arquitectura y matriz de adaptabilidad

> El reto no está definido. Este documento describe **cómo se adapta** el
> andamiaje a tres formas plausibles del problema, no qué vamos a construir.
> El día 18, elegir una línea en los primeros 60 minutos y anotarlo en
> `CLAUDE.md` § Estado del proyecto.

---

## 1. Núcleo común (se construye igual en las tres líneas)

```
                 ┌──────────────────────────────┐
  consulta ─────►│  API (FastAPI) /analyze      │◄──── pipeline del jurado
                 └──────────────┬───────────────┘
                                │
                 ┌──────────────▼───────────────┐
                 │  Grafo LangGraph             │
                 │  reason ⇄ tools → compose    │
                 │  (tope de iteraciones)       │
                 └──────────────┬───────────────┘
                                │
                 ┌──────────────▼───────────────┐
                 │  Registry de tools           │
                 │  (traza + captura de error)  │
                 └──────────────┬───────────────┘
                                │
                 ┌──────────────▼───────────────┐
                 │  Índice vectorial existente  │
                 └──────────────────────────────┘

  Streamlit ────► consume la misma API. El tema sale de design-tokens.json.
```

Lo que **nunca** cambia entre líneas: el contrato de la API, el registry de
tools, la capa de tema, el preflight y los topes de iteración.

---

## 2. Línea A — Analista con evidencia citada

**Si el reto pide**: responder preguntas de análisis sobre el corpus, con
trazabilidad a la fuente.

**Adaptación**: es el núcleo tal cual. Se refuerzan las tools de recuperación
(búsqueda multi-hop, filtro por fenómeno o por fecha) y el nodo `compose`
gana reglas de citación estrictas.

**Riesgo principal**: que el agente afirme sin evidencia. Mitigación: prompt de
sistema que obliga a buscar antes de afirmar, y a declarar explícitamente
cuándo no encontró respaldo.

**Esfuerzo**: bajo. Es donde el trabajo previo rinde más.

---

## 3. Línea B — Extracción de estructura y visualización

**Si el reto pide**: convertir documentos en eventos estructurados (actores,
lugares, fechas, relaciones) y presentarlos en mapa o línea de tiempo.

**Adaptación**:
- Añadir `src/extract/` con un nodo de extracción a esquema Pydantic
  (`Evento(actor, accion, lugar, fecha, doc_id)`).
- Activar el skill `geo-temporal-enrichment`: el índice actual **no tiene
  fecha ni lugar**; sin esos campos no hay mapa ni cronología posibles.
- UI: mapa (`pydeck`/`plotly`) + línea de tiempo, enlazados por filtro común.
- Dependencias extra: `pyproject.toml` grupo `geo`.

**Riesgo principal**: subestimar el enriquecimiento geo-temporal. Es la ruta
crítica de esta línea, no la extracción ni la visualización.

**Esfuerzo**: alto. Preparar el enriquecimiento **antes** del evento.

---

## 4. Línea C — Orquestador multi-fuente

**Si el reto pide**: integrar fuentes nuevas (satelital, APIs abiertas,
datos en vivo) junto al corpus.

**Adaptación**:
- Una tool por fuente, en `src/tools/`, con su docstring de política de uso.
- Nodo de enrutamiento: decide qué fuente consultar según la pregunta.
- Caché en disco de respuestas externas: las APIs tienen rate limit y el
  evento dura 24 horas.
- Aquí sí puede justificarse un patrón supervisor con especialistas por
  fuente — pero solo si las fuentes son heterogéneas de verdad.

**Riesgo principal**: gastar el sprint en ingeniería de ingesta de formatos
nuevos en vez de en el análisis. Acotar el número de fuentes a dos o tres.

**Esfuerzo**: medio-alto, dominado por la ingesta.

---

## 5. Decisión de stack

### Frontend (evaluado, decidido)

| Opción | A favor | En contra | Veredicto |
|---|---|---|---|
| **Streamlit** | máxima velocidad; el equipo ya lo conoce; ecosistema de datos | tematización limitada, exige CSS para densidad real | **elegido** |
| NiceGUI | control visual real en Python puro; layouts densos | más código por pantalla; menos inmediato para datos | escape si el listón visual sube |
| Gradio | rapidísimo para demos de modelo | orientado a I/O de modelo, no a dashboards | no |
| Reflex | compila a React, máximo control | paso de build, iteración más lenta | no en 24 h |
| Taipy | pensado para dashboards de datos | comunidad menor, menos ejemplos | no |

**Streamlit** gana por velocidad de iteración, que es la variable dominante en
24 horas. Su límite real es la tematización: `config.toml` solo expone cinco
colores. Por eso todo el CSS vive concentrado en `src/theme/streamlit_theme.py`,
derivado de los tokens — y por eso la versión de Streamlit está fijada en
`pyproject.toml`: sus selectores internos cambian entre versiones.

En una app de datos, la mayor parte del peso visual la cargan los gráficos, no
los widgets. El template de Plotly hace ese trabajo.

### Visualización
**Plotly**: interactivo, template propio desde tokens, `pydeck` para mapas si
la línea B se activa. Altair se descartó: más elegante para gráficos
estadísticos, pero menos control de tema y peor con volumen alto de puntos.

---

## 6. Identidad

El bundle ya fija nombre (**A.R.P.I.A.**) y paleta. Lo que faltaba era la
expansión de la sigla. Tres  opciones coherentes con el sistema visual:

- **A**nálisis y **R**ecuperación para **P**rocesamiento de **I**nteligencia
  **A**eroespacial — descriptiva, literal, segura ante un jurado técnico.
- **A**sistente de **R**azonamiento y **P**rospectiva para **I**nteligencia
  **A**eroespacial — enfatiza anticipación; encaja con el marco de "de la
  información al conocimiento" y con la idea de radar estratégico.
- **A**plicativo  de **R**ecuperación, **P**redicción ea **I**nteligencia
  **A**géntica  — Trata el entregable como un aplicativo funcional basado en analisis agenticos y recuperación vectorial de información .

La primera describe lo que el sistema hace; la segunda, para qué sirve y el tercero el aplicativo como tal.

---

## 7. Contrato de API

`src/api/contracts.py` es el único lugar donde viven los esquemas Pydantic
de entrada/salida. Congelado: la envoltura común (`schema_version`, `mode`,
`elapsed_ms`, `warnings`), `HealthResponse`, `UsageResponse`, el formato de
span/traza, y la invariante de que ningún endpoint devuelve 500 por un fallo
de dependencia externa — siempre 200 con `warnings` poblado. No congelado:
`AnalyzePayload` y `RetrievePayload`, que dependen del reto y se redefinen
el 18 de septiembre.

### Romper un contrato congelado

Congelado significa "cuesta romperlo", no "es imposible". Si hace falta:

1. Lo autoriza el arquitecto del equipo — no se rompe unilateralmente en
   medio de una tarea.
2. Se actualizan juntos, en el mismo cambio: `contracts.py`, `schema_version`
   (incrementar, p. ej. `"1.0"` → `"1.1"`), los tests de
   `tests/test_contracts.py`, y se avisa al equipo (el jurado consume el
   contrato desplegado, no el repositorio).
3. Se registra en un ADR de una línea en `docs/decisions/`: qué cambió, por
   qué, y quién lo autorizó.
