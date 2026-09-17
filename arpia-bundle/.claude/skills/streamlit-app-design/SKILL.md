---
name: streamlit-app-design
description: Estructurar y optimizar una app de Streamlit. Usar al crear o modificar src/ui/, al decidir cache o session_state, al organizar en paginas o fragments, o cuando la UI se siente lenta o pierde estado entre interacciones.
---

# Diseno y desarrollo de apps Streamlit

## El modelo de ejecucion primero
Streamlit reejecuta el script completo en cada interaccion. Cache,
session_state y fragments existen para vivir bien con ese modelo, no para
evitarlo. Antes de "arreglar" algo lento, confirma que el problema es un
recalculo caro en cada rerun, no otra cosa.

## Cache: la primera herramienta de performance
- `@st.cache_data` — datos serializables (DataFrames, resultado de una
  busqueda). Cachea por valor: cada llamada devuelve una copia independiente.
- `@st.cache_resource` — objetos vivos no serializables (el indice vectorial
  cargado, una conexion). Cachea por referencia: todas las sesiones
  comparten la misma instancia.
- No combines cache y `@st.fragment` en la misma funcion: no es compatible.

```python
@st.cache_resource
def get_index():
    return VectorIndex(...)   # una sola carga para todo el proceso
```

## session_state: inicializa antes de leer
Leer una clave que no existe lanza `KeyError`. Inicializa al inicio del
script, antes de que cualquier widget la referencie:
```python
if "top_k" not in st.session_state:
    st.session_state.top_k = 8
```
Si el widget que crea una clave deja de ejecutarse en un rerun (por ejemplo,
detras de un `if` que ya no es verdadero), Streamlit borra su estado.

## Fragments: rerun parcial, no otro modelo de ejecucion
`@st.fragment` reejecuta solo el bloque decorado. Usalo cuando una sola
visualizacion cambia con un filtro y el resto de la pagina no depende de el.

```python
@st.fragment
def panel_evidencia(top_k: int):
    hits = _get_index().search(query, k=top_k)
```

Limites reales: los widgets de un fragment solo pueden vivir en su cuerpo
(no en un contenedor externo); `parallel=True` sirve para operaciones lentas
e independientes, no por costumbre.

## Formularios y modales
`st.form` agrupa varios inputs para que el rerun ocurra una vez, al enviar,
en vez de uno por widget tocado — usalo para cualquier entrada con mas de un
campo. `st.dialog` sirve para una accion puntual que interrumpe el flujo
(confirmar, editar un registro); cualquier valor que la UI necesite despues
de cerrarlo va a `session_state`, no al valor de retorno de la funcion.

## Feedback de progreso segun duracion
| Situacion | Usar |
|---|---|
| Confirmacion corta y desechable | `st.toast` (no sirve si el usuario debe poder revisarlo despues) |
| Proceso de varios pasos (retrieval -> razonamiento -> redaccion) | `st.status`, expandible |
| Espera indefinida sin pasos discretos | `st.spinner` |

## Layout: exploracion antes de decoracion
- `st.columns` para comparacion o lectura lado a lado. No anides mas de un
  nivel: si hace falta mas, la estructura de la pagina esta mal, no falta
  otra columna.
- `st.sidebar` para controles globales persistentes (modo, top_k), no para
  contenido que cambia con cada consulta.
- `st.tabs` / `st.expander` / `st.popover` ocultan detalle secundario, nunca
  informacion que el usuario necesita ver primero.

## Paginas: `st.Page` + `st.navigation`, no la carpeta `pages/`
Si la app crece a mas de una vista, usa `st.Page`/`st.navigation` en el
entrypoint: da control sobre titulo, icono y agrupacion, y el entrypoint
puede definir elementos comunes alrededor de cada pagina.

```python
pg = st.navigation([st.Page(vista_retrieval), st.Page(vista_analisis)])
apply()          # tema comun, SIEMPRE antes de pg.run()
pg.run()
```

## Dataframes grandes: nunca vuelques todo
`st.dataframe` serializa la tabla entera a JSON para el navegador; con miles
de fragmentos del corpus eso congela la pagina. Pagina o trunca antes de
mostrar:
```python
st.dataframe(df.head(200))   # nunca el DataFrame completo sin filtrar
```

## Claves de widgets
Asigna `key` explicito a cualquier widget que se repita en un bucle o que
pueda coexistir con otro igual — sin `key` unico, Streamlit lanza
`DuplicateWidgetID`. La `key`, no el label, es la identidad real del widget:
cambiar la etiqueta no reinicia su valor si la key no cambia.

## Testing: `st.testing.v1.AppTest`
Prueba la UI sin navegador antes de asumir que "funciona":
```python
from streamlit.testing.v1 import AppTest

at = AppTest.from_file("src/ui/app.py").run()
assert not at.exception
```
Corre en `pytest` junto al resto de `tests/`. Detecta una excepcion
silenciosa que solo se ve al abrir el navegador.

## Limite que no cambia
`AGENTS.md` §6: nada de esto autoriza a construir paginas, fragments o
navegacion antes de que el reto lo pida. Son herramientas para cuando la
complejidad ya existe, no una lista de tareas para antes del 18. Para
colores y tokens visuales, ver la skill `arpia-visual-system`; esta skill no
la repite.
