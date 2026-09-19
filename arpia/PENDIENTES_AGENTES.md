# Pendientes de los agentes: hallazgos de las pruebas con el modelo real

> **Para:** Davinson (grafo y agentes). **De:** Juan (API del Reto 1).
> **Contexto:** pruebas manuales del 19 de septiembre con el índice de la Etapa 1
> (326.866 fragmentos), `bge-m3` en CPU y LiteLLM (`gpt-oss-120b`, `gpt-oss-20b`,
> `llama-3.3-70b-instruct`), servidor en `ARPIA_MODE=live`.
> **Base:** `main` @ `adea37f` + el commit de trazabilidad de conteos (sección 1). Lo que ya cerraste en
> `cfa7c79` y `adea37f` está en la sección 2.1.
>
> Las 279 pruebas de la suite pasan, pero **casi todas usan modelos falsos**: por eso
> nada de lo que sigue lo detectaba. Cada hallazgo trae evidencia, propuesta de arreglo
> y cómo comprobarlo. Detalle general del sistema en [`API.md`](API.md); decisiones de
> despliegue en [`DEPLOY.md`](DEPLOY.md).

---

## 1. Lo que ya cambié (para que lo revises)

**Trazabilidad de las cifras del agente analítico.** Toca tus archivos `executors.py`
(función `analitico`) y `verifier.py`, y agrega `citar_documentos` en `corpus.py`.

### Qué hace ahora una respuesta cuantitativa

| Antes | Ahora |
|---|---|
| El texto listaba hasta 25 cifras **sin ningún `doc_id`** | Cada cifra cita 3 documentos de muestra: `CSIS_Aerospace: 214 documentos (ej.: F2-CSIS-014, F2-CSIS-015, F2-CSIS-016)` |
| `citations` vacío | Una cita por cifra, con el `chunk_id` real del primer fragmento y su texto (se abre con `/api/evidence/{chunk_id}`) |
| `retrieval_context` vacío | Una línea por cifra (`(agregado por organizacion) CSIS_Aerospace: 214 documentos. Documentos de ejemplo: …`) y la línea de cobertura si el texto la afirma |
| La evidencia respaldaba solo las 10 primeras filas del texto | Respalda todas las filas mostradas |

### Por qué

`RETO.md` ("todo dato mostrado debe rastrearse a su `doc_id` y `chunk_id`") y el PDF de
ADL lo exigen para los datos de un componente (§3.3, punto 3) y para las variables
derivadas como `organizacion` y `anio` (B.1.3). Además Faithfulness (30% del Bloque A) se
calcula contra `retrieval_context`: vacío, cada cifra del texto se juzga como una
afirmación sin sustento.

### Cómo se relaciona con tu commit `8d96e8d`

Tu ajuste (no exigir citas a la evidencia agregada) frenó el falso disparo del
verificador, y lo mantengo. Pero por sí solo deja las respuestas cuantitativas sin
trazabilidad, y **choca** con citar: si el analítico cita `F2-CSIS-014`, tu `diagnosticar`
lo lee como **cita fabricada** (porque `disponibles` excluye la evidencia agregada) y
reescribiría con un modelo cada conteo. El cambio en `verifier.py` son 2 líneas:

- `disponibles` vuelve a contar **toda** la evidencia (los `doc_id` de la muestra son
  documentos reales).
- `sin_citas` sigue mirando **solo la evidencia documental**, como lo dejaste.

### Resultado medido (misma pregunta de vista, modelo real)

| | Antes | Ahora |
|---|---|---|
| Tokens del turno | 3.284 | 2.342 (ya no se llama al verificador: 1.190 tokens) |
| Documentos citados en el texto | 0 | 20 filas × 3 |
| `citations` / `retrieval_context` | 0 / 0 | 20 / 20 |

Pruebas nuevas en `tests/test_trazabilidad_analitico.py` (12). Comprobé con mutantes que
fallan si se reinstala tu verificador anterior o si se quitan las citas.

### Dos cosas que necesito que valides

1. **`retrieval_context` para conteos.** El PDF dice que el campo aplica "si el agente hizo
   uso de recuperación", y un conteo no es una búsqueda vectorial. Lo llené (una línea por
   cifra) porque vacío deja las cifras sin sustento ante Faithfulness, pero **es una
   interpretación nuestra**. Si hay canal con ADL, conviene confirmar cómo tratan el campo
   vacío en respuestas cuantitativas.
2. **Muestra de 3 documentos por cifra** (`MUESTRA_POR_CIFRA` en `executors.py`). Citar los
   425 documentos de una organización saturaría el texto. La lista completa quedaría para un
   endpoint del tablero. Si prefieres otro tamaño, es una constante.

---

## 2. Por corregir, en orden de prioridad

| # | Prioridad | Hallazgo | Archivos probables |
|---|---|---|---|
| 1 | **P0** | El orquestador falla en preguntas cuantitativas de un solo paso: el modelo devuelve la clave `Pasos` y `Plan` la rechaza | `plan.py`, `orchestrator.py` |
| 2 | **P0** | El caché semántico guarda como buena la respuesta del plan de respaldo | `chat.py`, `memory.py`, `orchestrator.py` |
| 3 | P1 | Ningún agente lee la conversación | `graph.py`, `orchestrator.py`, `executors.py` |
| 4 | P1 | Calidad de la redacción: introducción de "la pregunta busca…" y mezcla de idiomas | `executors.py` (`REDACCION_PROMPT`) |
| 5 | P1 | La reescritura del verificador puede filtrar estructura interna | `verifier.py`, `guardian.py` |

### 1. El orquestador falla en preguntas cuantitativas de un solo paso (P0)

**Qué pasa.** Con `gpt-oss-120b`, "¿Cuántos documentos hay por fenómeno?" devuelve el plan
como `{"Pasos": [...]}` (con mayúscula). `Plan` tiene `extra="forbid"`, así que la validación
falla, `planificar` cae al plan de respaldo, y el respaldo **siempre** manda al agente
documental. El agente analítico (el de los puntos extra) no corre.

**Evidencia.** Reproducido 2 de 2 con "¿Cuántos documentos hay por fenómeno?" y "¿Cuántos
documentos publica cada organización?". En el log:

```
WARNING src.agents.orchestrator | fallo la planificacion (1 validation error for Plan
Pasos
  Extra inputs are not permitted [type=extra_forbidden, input_value=[{'agente': 'agente_anali…
```

Las preguntas documentales y las de vista sí se planifican bien (en la de vista: analítico con
`group_by: organizacion` + visualizador). La misma pregunta cuantitativa **funcionaba antes de
`c9f48f5`** (896 tokens, 1 llamada, F3 = 888, F2 = 479, F1 = 459), así que puede ser una
regresión del esquema nuevo.

**Causa probable.** `Plan.model_json_schema()` pone `"title": "Pasos"` a la propiedad `pasos`,
y el modelo devuelve ese título como clave.

**Por qué importa.** La pregunta de conteo es el uso más típico del analítico. Se contesta por
búsqueda semántica ("no se proporciona un número específico") en vez de con el conteo exacto.

**Propuesta.**
- Que `Plan` acepte la clave sin importar mayúsculas (un `model_validator(mode="before")` que
  normalice `Pasos` → `pasos`), y/o quitar los `title` del esquema que se envía al modelo.
- Que `plan_de_respaldo` mande a `agente_analitico` cuando la pregunta sea claramente de conteo
  ("cuántos", "cuántas", "distribución"), en vez de siempre al documental. Es determinista y
  cuesta 0 tokens.

**Cómo comprobar.** Con `.env` real, este script llama al orquestador una vez (~900 tokens):

```python
# uv run --extra retrieval python este_script.py   (con PYTHONPATH=.)
from src.agents import orchestrator
from src.agents.plan import Plan

print(list(Plan.model_json_schema()["properties"]), Plan.model_json_schema()["properties"]["pasos"].get("title"))
cliente = orchestrator._llm()
for q in ["¿Cuántos documentos hay por fenómeno?", "¿Qué reporta el corpus sobre capacidades antisatélite?"]:
    try:
        p = cliente.with_structured_output(Plan, include_raw=True).invoke(orchestrator._mensajes(q, "", []))["parsed"]
        print("OK  ", q, [(s.agente, s.group_by) for s in p.pasos])
    except Exception as e:
        print("FALLA", q, str(e).splitlines()[1])
```

Falta también una prueba automática: que `Plan` valide `{"Pasos": [...]}` y que el respaldo de
una pregunta de conteo elija al analítico.

### 2. El caché semántico guarda como buena la respuesta del plan de respaldo (P0)

**Qué pasa.** Cuando el plan cae al respaldo, el turno termina con `estado: "ok"` y
`chat.run_chat` lo guarda en el caché (solo excluye `error*` y `rechazado*`). Repetir la pregunta
devuelve la respuesta mala con `cache:1.00`, hasta reiniciar el proceso.

**Evidencia.** Es consecuencia directa del hallazgo 1: la respuesta documental a "¿Cuántos
documentos hay por fenómeno?" quedó en el caché de ese proceso.

**Propuesta.** No cachear turnos cuyo plan fue de respaldo. Por ejemplo, que `planificar`
deje una marca en `turnlog` y `run_chat` la lea, o un estado propio (`ok:respaldo`).

### 3. Ningún agente lee la conversación (P1)

**Qué pasa.** El historial se guarda en SQLite (`memoria_persistente: true`) pero
`orchestrator.planificar(pregunta, …)` y `executors.redactar(pregunta, evidencia)` solo reciben
el texto de la pregunta.

**Evidencia.** En la misma sesión, después de la pregunta sobre capacidades antisatélite,
"Resúmelo en una sola frase" respondió sobre documentos de IA sin relación, con 3 llamadas y
4.442 tokens (el orquestador planificó una búsqueda con la frase literal, sin contexto, y
replanificó).

**Por qué importa.** ADL evalúa preguntas sueltas, así que no cambia la nota, pero el chat de
demostración las necesita.

**Propuesta.** Pasar las últimas 1 o 2 vueltas (`state["messages"]`) al orquestador para que
reescriba una pregunta de seguimiento como una consulta autónoma, y al redactor. Ojo con el
caché semántico: desde `adea37f` distingue conversaciones (un seguimiento solo acierta dentro
de su sesión), así que ya no hay riesgo de que "¿y en 2023?" reciba la respuesta de otra conversación.

### 4. Calidad de la redacción (P1)

**Qué pasa.** En la respuesta documental real: abre con "La pregunta busca información sobre…"
(una frase que reformula la pregunta y no aporta), y mezcla palabras en francés copiadas de las
fuentes ("répercussions mundiales", "ascension directe"). Cierra con "La evidencia encontrada es
parcial…", lo cual está bien.

**Por qué importa.** El Tono (25% del Bloque A) evalúa "profesional, clara y empática".

**Propuesta.** En `REDACCION_PROMPT`: responder siempre en español, sin repetir la pregunta y
empezando por el hallazgo; si una fuente está en otro idioma, traducir la idea y no copiar los
términos. Ajustar con 3 o 4 preguntas reales y comparar.

### 5. La reescritura del verificador puede filtrar estructura interna (P1)

**Qué pasa.** En una prueba, el verificador reescribió una respuesta y el texto final decía
`(fuente: documento_recuperado id="agregado:organizacion:SIPRI")`. Tu commit `8d96e8d` eximió a
los conteos, con lo que ese caso concreto ya no se da; pero la ruta de reescritura sigue
enviando los documentos envueltos en `<documento_recuperado id=…>` y el modelo puede repetir
esa sintaxis. El guardián de salida bloquea la etiqueta con `<…>`, pero no la forma sin
corchetes.

**Propuesta.** Sanear la salida del verificador (quitar `documento_recuperado id="…"`), o pedir
explícitamente en `VERIFICACION_PROMPT` que nunca cite el sobre. Además, una respuesta que salió
de código determinista no debería reescribirse con un modelo.

## 2.1 Ya resuelto en `main` (gracias)

Cinco de los pendientes que listé en la primera versión de este documento ya los cerraste. Los dejo
anotados para que quede constancia de que se comprobaron contra el código:

| Pendiente | Commit | Qué se hizo |
|---|---|---|
| El verificador no estaba en la agent card | `adea37f` | Declarado en `agent_card.json` |
| Sin tope de tiempo por turno | `adea37f` | `budget.py`: `TURN_BUDGET_S=75`, `REQUEST_TIMEOUT_S=25` y tres puntos de control |
| La tabla del tablero se cacheaba vacía | `adea37f` | No se cachea el fallo; los endpoints responden `disponible: false` |
| `/health` cargaba el índice en su primera llamada | `adea37f` | El arranque precalienta índice, tabla y encoder |
| `delegar_*` no aparecía en `tools_called` | `cfa7c79` | `executors.DELEGACIONES` anota cada delegación; la card gana `delegar_analitico` |

También cerraste que el caché distinga conversaciones (`adea37f`).

---

## 3. Otros datos útiles medidos

- Consumo de una tanda completa de pruebas (9 llamadas al modelo): ~12.000 tokens.
- Carga del índice: 4 s. Descarga y carga de `bge-m3` la primera vez: 473 s.
- El snapshot de `BAAI/bge-m3` trae los pesos **duplicados** (`model.safetensors` y
  `pytorch_model.bin`, 2,12 GB cada uno): 8,6 GB en disco. Para la imagen basta una copia
  (detalle en `DEPLOY.md` §3.1, decisión D3).
- Cuando el orquestador funcionó, los tres modelos por agente respondieron bien a través del
  proxy: la traducción de nombres (`gateway_model_for`) está confirmada en real.

## 4. Mensaje sugerido para Davinson

> Davinson: gracias por cerrar los pendientes de `API.md`. Hice pruebas con el modelo real (índice de la Etapa 1, `bge-m3` y LiteLLM) y dejé
> todo en `arpia/PENDIENTES_AGENTES.md`. Lo urgente son dos cosas: (1) el orquestador falla en
> preguntas de conteo de un solo paso porque `gpt-oss-120b` devuelve `Pasos` y `Plan` la rechaza,
> así que el analítico no corre; (2) el caché guarda como buena esa respuesta de respaldo. También
> toqué `analitico` y `verifier.py` para que las cifras citen documentos reales; la sección 1
> explica por qué y qué necesito que valides.
