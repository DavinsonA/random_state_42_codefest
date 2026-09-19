# Pendientes de los agentes: hallazgos de las pruebas con el modelo real

> **Para:** Davinson (grafo y agentes). **De:** Juan (API del Reto 1).
> **Contexto:** pruebas manuales del 19 de septiembre con el índice de la Etapa 1
> (326.866 fragmentos), `bge-m3` en CPU y LiteLLM (`gpt-oss-120b`, `gpt-oss-20b`,
> `llama-3.3-70b-instruct`), servidor en `ARPIA_MODE=live`.
> **Base:** `main` @ `c92029b` + el commit de trazabilidad de conteos (sección 1). Lo que ya cerraste en
> `cfa7c79` y `adea37f` está en la sección 2.1.
>
> Las 337 pruebas de la suite pasan, pero **casi todas usan modelos falsos**: por eso
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
| 1 | ✅ **Resuelto** (ver 2.1) | El orquestador fallaba con la clave `Pasos`; ahora 6 de 6 llamadas válidas con el modelo real | `plan.py`, `executors.py` |
| 2 | ✅ **Resuelto** (ver 2.1) | El caché semántico guardaba como buena la respuesta del plan de respaldo | `chat.py`, `turnlog.py`, `orchestrator.py` |
| 3 | ✅ **Resuelto** (ver 2.1) | Ningún agente leía la conversación | `graph.py`, `orchestrator.py`, `executors.py`, `memory.py` |

### 1. ✅ RESUELTO: el orquestador fallaba porque el modelo devolvía la clave `Pasos`

> **Estado:** corregido en `plan.py` y `executors.py` (ver 2.1). Lo de abajo queda como registro
> del diagnóstico original.

**Qué pasa.** Con `gpt-oss-120b`, el plan a veces llega como `{"Pasos": [...]}` (con mayúscula).
`Plan` tiene `extra="forbid"`, así que la validación falla, `planificar` cae al plan de respaldo y
el respaldo **siempre** manda al agente documental. El orquestador y el analítico no corren, y la
respuesta sale de una búsqueda semántica.

**Evidencia.** Dos mediciones con el modelo real, tres preguntas cada una, sin reintentos:

| Pregunta | `4ae60f9` (antes de la voz) | `c92029b` (después de la voz) |
|---|---|---|
| ¿Cuántos documentos hay por fenómeno? | **FALLA** (2 de 2) | OK (analítico, 1.038 tokens) |
| ¿Qué reporta el corpus sobre capacidades antisatélite? | OK | **FALLA** |
| Grafica la cantidad de documentos por organizacion | OK | **FALLA** (también servido por `/chat`) |

**No depende del tipo de pregunta:** cambia con la redacción del prompt. Con el código actual, dos de
tres preguntas típicas se responden sin orquestador. El log:

```
WARNING src.agents.orchestrator | fallo la planificacion (1 validation error for Plan
Pasos
  Extra inputs are not permitted [type=extra_forbidden, input_value=[{'agente': 'agente_anali…
```

**Causa probable.** `Plan.model_json_schema()` pone `"title": "Pasos"` a la propiedad `pasos`,
y el modelo devuelve ese título como clave.

**Por qué importa.** Sin un plan válido no se ve el sistema multiagente: la respuesta sale del documental por
búsqueda semántica. Una pregunta de conteo se contesta con "no se proporciona un número específico" en vez
con el conteo exacto, y una de vista responde texto en vez de emitir el `ViewSpec`. Además el caché guarda
esa respuesta como buena (hallazgo 2).

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

### 2. ✅ RESUELTO: el caché guardaba como buena la respuesta del plan de respaldo

> **Estado:** corregido con la marca en `turnlog` (ver 2.1). Lo de abajo queda como registro.

**Qué pasa.** Cuando el plan cae al respaldo, el turno termina con `estado: "ok"` y
`chat.run_chat` lo guarda en el caché (solo excluye `error*` y `rechazado*`). Repetir la pregunta
devuelve la respuesta mala con `cache:1.00`, hasta reiniciar el proceso.

**Evidencia.** Es consecuencia directa del hallazgo 1: la respuesta documental a "¿Cuántos
documentos hay por fenómeno?" quedó en el caché de ese proceso.

**Propuesta.** No cachear turnos cuyo plan fue de respaldo. Por ejemplo, que `planificar`
deje una marca en `turnlog` y `run_chat` la lea, o un estado propio (`ok:respaldo`).

### 3. ✅ RESUELTO: ningún agente leía la conversación

> **Estado:** corregido (ver 2.1). Lo de abajo queda como registro del diagnóstico.

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

## 2.1 Ya resuelto en `main` (gracias)

Siete de los pendientes que listé en la primera versión de este documento ya los cerraste. Los dejo
anotados para que quede constancia de que se comprobaron contra el código:

| Pendiente | Commit | Qué se hizo |
|---|---|---|
| El verificador no estaba en la agent card | `adea37f` | Declarado en `agent_card.json` |
| Sin tope de tiempo por turno | `adea37f` | `budget.py`: `TURN_BUDGET_S=75`, `REQUEST_TIMEOUT_S=25` y tres puntos de control |
| La tabla del tablero se cacheaba vacía | `adea37f` | No se cachea el fallo; los endpoints responden `disponible: false` |
| `/health` cargaba el índice en su primera llamada | `adea37f` | El arranque precalienta índice, tabla y encoder |
| `delegar_*` no aparecía en `tools_called` | `cfa7c79` | `executors.DELEGACIONES` anota cada delegación; la card gana `delegar_analitico` |
| Calidad de la redacción (introducción "la pregunta busca…", mezcla de idiomas, sin tildes) | `cacadf9`, `c92029b` | `voz.py` concentra el registro: conclusión primero, procedencia caracterizada ("AI Index Stanford (2018, F1-AIINDEX-016)"), tildes. Comprobado con el modelo real en una respuesta documental |
| La reescritura del verificador podía filtrar el sobre (`documento_recuperado id=…`) | `cacadf9`, `c92029b` | El sobre entrega la procedencia etiquetada y el prompt prohíbe repetir el andamiaje. **Sin comprobar** con una reescritura real del verificador |

También cerraste que el caché distinga conversaciones (`adea37f`).

### Hallazgo 1 (orquestador y clave `Pasos`), cerrado en esta sesión

Validado con el modelo real: **1 de 6** llamadas al orquestador producían un plan válido (las otras
fallaban con `Extra inputs are not permitted` sobre `Pasos`). Tras el arreglo: **6 de 6**.

- `plan.py`: `Plan` y `Paso` normalizan las claves del JSON (`Pasos` → `pasos`, `Group By` →
  `group_by`) con un validador `mode="before"`. El esquema sigue cerrado: un campo inexistente se rechaza.
- `plan.py`: `plan_de_respaldo` manda al analítico la pregunta de conteo inequívoca (palabra de cantidad
  + unidad del corpus, sin tildes) y suma el visualizador si piden una gráfica. "¿Cuántos satélites
  lanzó China?" sigue yendo al documental. Cuesta 0 tokens.
- `executors.py`: `_dimension` quita las tildes; antes "por organización" contestaba por `fenomeno`.
- No se añadió reintento antes del respaldo: cada uno cuesta tokens y la causa raíz ya está cerrada.
- Comprobado por `/chat` con el modelo real: conteo por fenómeno → analítico con `doc_id`; pregunta de
  contenido → documental con citas; "Grafica…" → analítico + `view_spec` de barras.
- 9 pruebas nuevas en `tests/test_graph.py` (328 en total).

### Hallazgo 2 (caché y plan de respaldo), cerrado en esta sesión

Se siguió la primera propuesta: una marca en `turnlog`, sin cambiar el `estado`.

- `turnlog.py`: `marcar_no_cacheable(motivo)` y `no_cacheable()`. Mismo canal que ya usan los
  agentes con la API (`record_agent`, `add_citations`), seguro entre hilos porque el objeto es compartido.
- `orchestrator.py`: `planificar` llama a `marcar_no_cacheable("plan_de_respaldo")` en sus dos salidas al
  respaldo (excepción y plan no usable). Son 2 líneas.
- `chat.py`: `run_chat` no guarda en el caché un turno marcado y lo deja en el log
  (`turno no cacheado: plan_de_respaldo`).
- Efecto: un fallo transitorio del modelo ya no se congela; repetir la pregunta vuelve a ejecutar el turno.
- 4 pruebas nuevas (332 en total). Comprobé con un mutante que la de `test_chat.py` falla si se quita el
  cambio de `chat.py`.

### Hallazgo 3 (los agentes no leían la conversación), cerrado en esta sesión

Se siguió la propuesta: pasar las últimas vueltas al orquestador y al redactor. Cambia firmas, así que
conviene que lo revises.

- `memory.py`: `conversacion_previa(mensajes, pregunta)` arma las últimas 2 vueltas como texto
  (`Usuario: …` / `Asistente: …`), con tope de 400 caracteres por mensaje. Excluye la pregunta actual y
  los mensajes de herramientas. Devuelve `""` si no hay conversación.
- `orchestrator.py`: `planificar(…, conversacion="")`. Solo si hay conversación, añade bajo la pregunta un
  bloque que pide reescribir cada `consulta` como autónoma (sin pronombres) si la pregunta es un
  seguimiento, y dejarla igual si se entiende sola. La pregunta sigue siendo la primera línea.
- `executors.py`: `redactar(…, conversacion="")`, con el mismo criterio: solo aclara la referencia y el
  formato; los hechos salen de la evidencia.
- `graph.py`: `planificar` y `componer` leen `state["messages"]` y lo pasan.
- **Costo:** el primer turno de una sesión no cambia (cero tokens extra), así que la evaluación de ADL,
  que manda preguntas sueltas, no se ve afectada. Solo los seguimientos pagan el bloque.
- **Medido con el modelo real** (misma sesión): tras "¿Qué reporta el corpus sobre capacidades
  antisatélite?", "Resúmelo en una sola frase" buscó "Resumen en una sola frase del corpus sobre
  capacidades antisatélite" y respondió sobre el tema correcto, con 2 llamadas y 4.909 tokens. Antes: 3
  llamadas, 4.442 tokens y documentos de IA sin relación.
- **Límite conocido:** el redactor sigue su estructura fija (conclusión, desarrollo, lo no cubierto) y
  no reduce la respuesta a una sola frase aunque se lo pidan. Es una decisión de `voz.py`/`REDACCION_PROMPT`.
- 5 pruebas nuevas (337 en total): primer turno sin historial, seguimiento con historial en ambos agentes,
  sin cruce entre sesiones, recorte y filtrado, y replanificación que conserva la conversación.

Ya no queda ningún hallazgo abierto de esta lista.

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
> todo en `arpia/PENDIENTES_AGENTES.md`. (1) El orquestador fallaba porque `gpt-oss-120b` devolvía `Pasos`
> y `Plan` la rechazaba; ya lo corregí en `plan.py` y `executors.py` (sección 2.1) y lo puedes revisar.
> El caché que guardaba como buena una respuesta de respaldo también quedó cerrado (marca en `turnlog`,
> 2 líneas en `planificar`), y también que los agentes lean la conversación (`memory.conversacion_previa`;
> cambia las firmas de `planificar` y `redactar`, sin costo en el primer turno de una sesión). También
> toqué `analitico` y `verifier.py` para que las cifras citen documentos reales; la sección 1
> explica por qué y qué necesito que valides.
