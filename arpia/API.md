# A.R.P.I.A. — API del Reto 1: qué está construido y cómo funciona

> **Fuente de verdad de la implementación.** [`../RETO.md`](../RETO.md) dice *qué exige
> ADL*; este documento dice *qué hay construido, cómo funciona y qué falta*.
> Ante conflicto con la Especificación Técnica de ADL, manda la de ADL.
>
> Fecha de corte: `main` @ `1f23b11` — Fases 1 a 4 (19 de septiembre de 2026).
> Si cambias el contrato o el comportamiento de un endpoint, **actualiza este archivo
> en el mismo commit**. Un documento desactualizado es peor que ninguno.

---

## 1. Estado de un vistazo

| Pieza | Estado | Dónde |
|---|---|---|
| `POST /chat` en el formato exacto de ADL §2.4 | ✅ hecho y probado | `src/api/chat.py`, `main.py` |
| Contratos Pydantic (entrada, salida, `ViewSpec`) | ✅ hecho | `src/api/contracts.py` |
| Sesión (`sesion_id`) y memoria conversacional (SQLite) | ✅ hecho | `src/api/session.py`, `src/agents/checkpoint.py` |
| `GET /health`, `GET /usage`, `GET /agent-card` | ✅ hecho | `src/api/main.py` |
| Guardián anti-inyección (0 tokens) | ✅ hecho | `src/agents/guardian.py` |
| Caché semántico (0 tokens en aciertos) | ✅ hecho | `src/agents/memory.py` |
| Grafo LangGraph: orquestador de plan único + replanificación | ✅ hecho | `src/agents/graph.py`, `orchestrator.py`, `plan.py` |
| Ejecutores: documental, analítico, visualizador | ✅ hechos (probados con LLM falso) | `src/agents/executors.py` |
| Registro por turno (tools, contexto, citas, tokens por agente), también en planes paralelos | ✅ hecho y corregido (§12 #2) | `src/observability/` |
| Índice vectorial, encoder local, agregaciones | ✅ hecho | `src/retrieval/` |
| Enrutamiento por `Host` (un contenedor, 3 dominios) | ✅ hecho | `src/api/routing.py` |
| Traducción del modelo de la card al id de LiteLLM (`gateway_model_for`) | ✅ hecho (§6) | `src/agents/card.py` |
| **Nada se ha probado aún con el modelo real** | ❌ | — |
| `GET /topics` | ⏳ solo el contrato; sin endpoint | `contracts.py` |
| `GET /api/evidence/{chunk_id}` | ⏳ mencionado en `contracts.py`; sin endpoint | — |
| Endpoint que entregue al tablero los datos de un `ViewSpec` | ⏳ no existe (la agregación sí: `aggregates.py`) | — |
| Interfaces `chat.html` / `dashboard.html` | ❌ `static/` no existe todavía (lo mantiene otra sesión) | `routing.py` |

**Lo más importante que hay que saber:** el sistema completo está construido y sus
214 pruebas pasan, **pero todas usan modelos falsos**. Al revisarlo aparecieron dos
fallos que las pruebas originales no veían y que **ya están corregidos** (§12 #1 y #2:
nombre de modelo y metadata en planes paralelos). Falta probar el grafo con el modelo
real (#3) antes de la entrega de las 08:00.

---

## 2. Endpoints

| Método y ruta | Para qué | Quién lo consume |
|---|---|---|
| `POST /chat` | Un turno de conversación. **Es lo que evalúa ADL.** | ADL, frontend de chat, dashboard |
| `GET /agent-card` | Agent card en JSON (formato ADL §2.3, no A2A) | ADL, expertos |
| `GET /health` | ¿Está vivo el contenedor y con qué capacidades? | Coolify (healthcheck), humanos |
| `GET /usage` | Consumo acumulado del proceso y eficacia del caché | Nosotros (vigilar los 100 USD) |
| `GET /` | Sirve `chat.html` o `dashboard.html` según el `Host` | Navegador |

### Regla dura: nunca un 500 ni un 422

Ningún camino devuelve un error de servidor ni de validación. Un fallo interno, una
dependencia caída o un cuerpo raro se responden con **HTTP 200** y el detalle en
`metadata.estado`. Un 422 delante del evaluador puntúa cero en esa pregunta; una
respuesta degradada y explicada, no. Hay un manejador de `RequestValidationError`
como red de seguridad (`main.py`).

### `GET /health` — "¿está vivo el contenedor?"

Existe y devuelve, sin autenticación:

| Campo | Significado |
|---|---|
| `status` | `ok` \| `degraded` \| `down` (nunca solo un boolean) |
| `mode` | `live` o `stub` |
| `index_loaded`, `encoder_listo` | índice FAISS y encoder en memoria |
| `gateway_reachable` | LiteLLM responde (solo alcanzabilidad de red, no valida la key ni el modelo) |
| `agent_card_loaded`, `agentes_registrados` | la card cargó y qué ids expone |
| `memoria_persistente` | el checkpointer escribe en disco; `false` = la memoria vive en RAM |
| `tools_registered`, `warnings` | tools disponibles y avisos legibles |

Semántica: `200` con `ok`/`degraded`; **`503` solo si nada funciona**. En `stub` nunca es
`ok`. El `HEALTHCHECK` del `Dockerfile` usa este endpoint (`raise_for_status`), por eso
`degraded` no debe marcar el contenedor como *unhealthy*.

---

## 3. `POST /chat`

### 3.1 Entrada

Acepta **JSON** o **texto plano**. La especificación de ADL solo dice "texto plano o
JSON" y no fija los nombres de campo, por eso el contrato es tolerante.

```bash
# JSON
curl -X POST http://localhost:8000/chat -H 'content-type: application/json' \
     -d '{"texto": "¿Qué dice el corpus sobre satélites en órbita baja?", "sesion_id": "mi-sesion-001"}'

# Texto plano
curl -X POST http://localhost:8000/chat -H 'content-type: text/plain' \
     -d '¿Qué dice el corpus sobre satélites en órbita baja?'
```

| Campo | Alias aceptados | Obligatorio |
|---|---|---|
| Pregunta | `texto`, `pregunta`, `query`, `input`, `message`, `question`, `prompt` | No (cuerpo vacío → 200 cortés) |
| Sesión | `sesion_id`, `session_id`, `thread_id`, `conversation_id` | No |

Los campos desconocidos se ignoran (`extra="ignore"`).

### 3.2 Sesión: quién la define y cómo

El `sesion_id` es una etiqueta de conversación, como un número de ticket. **La define
quien llama**: el frontend crea un uuid al abrir el chat y lo manda en cada mensaje.
`resolve_session` (`src/api/session.py`) corre **solo en el servidor**; el frontend no
lo importa. Orden de resolución:

1. campo del cuerpo (con sus alias);
2. header `X-Session-Id`;
3. cookie `sesion_id`;
4. si no hay ninguno válido, el servidor genera un `uuid4` nuevo.

- El id se devuelve **siempre** en el header `X-Session-Id`. La cookie
  (`HttpOnly`, `SameSite=Lax`, vida `SESSION_TTL_S`) solo se emite cuando el servidor
  generó el id.
- Un id del cliente solo se acepta si cumple `^[A-Za-z0-9_-]{8,64}$`.
- **Por qué sin id = sesión nueva:** el evaluador de ADL probablemente no manda
  `sesion_id` y hace preguntas independientes. Compartir sesión arrastraría historial
  (más tokens, peor Faithfulness) y dejaría que un ataque de inyección contamine las
  preguntas siguientes.
- **El `sesion_id` viaja al grafo como `thread_id`** y hoy sí significa algo: el grafo
  compila con un checkpointer SQLite (`src/agents/checkpoint.py`), guarda el estado por
  hilo y el turno siguiente continúa donde quedó el anterior. Dos sesiones no comparten
  historial. El historial se recorta a las últimas 6 vueltas (`VENTANA_TURNOS`).

### 3.3 Salida

Los tres primeros bloques son el contrato de ADL y **no se renombran ni cambian de
tipo**. Los otros tres son campos propios (ADL exige que los tres bloques estén, no
prohíbe que haya más).

```jsonc
{
  "respuesta": "…",                      // texto para el usuario
  "evaluacion": {                        // insumo del Bloque A (calidad, 40%)
    "input": "…",                        // la pregunta recibida
    "actual_output": "…",                // igual a `respuesta`
    "retrieval_context": ["(doc-12) …"], // chunks del turno, textuales. [] si no hubo RAG
    "tools_called": [
      { "name": "consultar_agregado", "input_parameters": {"group_by": "anio"}, "output": "…" }
    ]
  },
  "metadata": {                          // insumo del Bloque B (eficiencia, 20%)
    "num_interacciones": 2,              // llamadas a modelos en el turno
    "agentes_invocados": ["orquestador", "agente_documental"],
    "tokens": { "input": 2130, "output": 410, "total": 2540 },   // suma de TODOS los modelos
    "tokens_por_agente": [
      { "agente": "orquestador", "modelo": "gpt-oss-120b", "input": 1420, "output": 180, "total": 1600 }
    ],
    "latencia_ms": 2340,                 // la medimos nosotros, de extremo a extremo
    "estado": "ok"                       // "ok" o un código de degradación (§3.5)
  },

  "mode": "live",                        // "live" | "stub"
  "citations": [ { "doc_id": "…", "chunk_id": "…", "fuente": "…", "fragmento": "…" } ],
  "view_spec": null                      // ViewSpec (§4) solo si el turno pide una vista
}
```

### 3.4 De dónde sale cada campo

Nada se fabrica: todo sale de lo que el turno **realmente registró**.

| Campo | Lo produce | Cómo |
|---|---|---|
| `respuesta`, `actual_output` | grafo (`componer`) | `result["answer"]` |
| `evaluacion.input` | API | el texto recibido (ya saneado por el guardián) |
| `retrieval_context`, `citations` | `corpus.recuperar()` | **punto único de recuperación**: todo lo que busca en el corpus pasa por ahí y lo anota en `turnlog` |
| `tools_called` | `@registry.register`, o `turnlog.record_tool_call` a mano | ver hallazgo §12 #4: el documental hoy **no** anota `buscar_corpus` |
| `tokens`, `tokens_por_agente`, `num_interacciones` | orquestador, `redactar`, visualizador | `usage.record_usage(..., agent=, model=)` en cada llamada al LLM |
| `latencia_ms`, `estado`, `mode` | API | medidos en `chat.py` |
| `view_spec` | agente visualizador | `ViewSpec` validado; uno inválido se descarta (`_leer_view_spec`) |

Regla del validador de `Metadata`: si hay `tokens_por_agente`, `tokens` se **recalcula**
como su suma. ADL marca como inconsistencia reportar en `tokens.total` menos de lo que
suma el desglose. No lanza: un descuadre aritmético no puede convertirse en un 500.

### 3.5 Valores de `metadata.estado`

| Valor | Cuándo | Costo |
|---|---|---|
| `ok` | respuesta normal | tokens del turno |
| `stub` | `ARPIA_MODE=stub`: respuesta **simulada** | 0 |
| `cache:0.97` | la resolvió el caché semántico (la cifra es la similitud) | 0, `agentes_invocados=["memoria"]` |
| `rechazado:inyeccion` | el guardián detectó un intento de inyección | 0, `agentes_invocados=["guardian"]` |
| `rechazado:fuera_de_dominio` | petición evidentemente ajena a los tres fenómenos | 0 |
| `rechazado:salida_bloqueada` | la respuesta filtraba configuración o estructura interna | los del turno |
| `error_entrada_invalida` | el cuerpo no traía una pregunta | 0 |
| `error_llm_no_configurado` | faltan `LLM_BASE_URL` / `LLM_API_KEY` | 0 |
| `error_grafo` | el grafo lanzó una excepción | los consumidos hasta el fallo |
| `error_respuesta_vacia` | el grafo devolvió `answer` vacío | los del turno |

Ante `error_*` no se responde con una disculpa genérica: se entregan **los fragmentos
más relevantes con su procedencia** (`_retrieval_fallback`). Una disculpa puntúa cero en
relevancia; evidencia real, no.

---

## 4. Contratos (`src/api/contracts.py`)

Es el **único** lugar donde viven los esquemas Pydantic. `main.py` importa de aquí y
nunca declara un modelo propio.

- **Entrada:** `ChatRequest`.
- **Salida:** `AgentResponse` (alias `ChatResponse`) con `Evaluacion`, `ToolCall`,
  `Metadata`, `Tokens` (alias `TokenCount`), `TokensPorAgente`, `Citation`, `ViewSpec`.
- **Operación:** `HealthResponse`, `UsageResponse`.
- **Definido, sin endpoint aún:** `Topic`, `TopicsResponse`.

### `ViewSpec` — la frontera de seguridad del agente visualizador

El visualizador **nunca ejecuta código ni SQL**: solo emite un `ViewSpec` validado contra
un esquema cerrado (`extra="forbid"` + campos `Literal`). Lo que no esté en estas listas
no se puede emitir.

| Campo | Valores permitidos |
|---|---|
| `chart` | `timeline`, `bar`, `stacked_bar`, `donut`, `table`, `kpi` |
| `metrica` | `conteo_documentos`, `conteo_fragmentos` |
| `fenomenos` | subconjunto de `F1`, `F2`, `F3` (vacío = los tres) |
| `group_by` | `fenomeno`, `organizacion`, `fuente`, `formato`, `anio` |
| `desde` / `hasta` | año `YYYY` inclusive |
| `titulo`, `nota` | texto; `nota` es la advertencia que el tablero **debe** mostrar |

**El vocabulario está podado a propósito.** El índice trae ocho campos (`doc_id`,
`chunk_id`, `fuente`, `formato`, `fenomeno`, `posicion`, `num_tokens`, `texto`) y **ni
fecha, ni lugar, ni actor**. Por eso se retiraron `map`, `network`, `lugar`, `actor`,
`mes` y `trimestre`: un agente que propone una vista que el tablero no puede poblar
cuesta el 55% del Reto 2. **Volver a añadirlos exige primero el dato, no al revés.**

Solo hay **conteos y frecuencias**. No existe métrica de "riesgo", "amenaza" ni ningún
índice: `RETO.md` prohíbe presentar como medición objetiva un puntaje calculado ad-hoc.

**Dos dimensiones derivadas** (`src/retrieval/enrich.py`), leídas de la ruta del archivo
fuente, no inventadas:
- `organizacion`: segundo nivel de la ruta (`CSIS_Aerospace`, `CSET_Georgetown`…).
- `anio`: año en el nombre del archivo. **Cubre solo 622 de 1.826 documentos (34%)**;
  el visualizador impone una `nota` con esa cobertura en toda vista temporal.

---

## 5. Ciclo de un turno

### 5.1 En el API (`chat.run_chat`)

```
guardian.revisar_entrada → memoria.buscar → GRAFO → guardian.revisar_salida → memoria.guardar
     (0 tokens, veto)      (0 tokens, atajo)                (0 tokens, veto)     (solo si fue ok)
```

El orden importa: rechazar un ataque cuesta cero y no debe llegar ni al caché ni al modelo;
un acierto de caché ahorra el turno entero; la revisión de salida es la última barrera.

### 5.2 En el grafo (`src/agents/graph.py`, LangGraph)

```
START → begin → planificar → ejecutar ─┬→ componer → END
                    ▲                  │  (evidencia insuficiente y replans < 1)
                    └──────────────────┘
```

| Nodo | Qué hace | Modelo | Costo |
|---|---|---|---|
| `begin` | agrega la pregunta, reinicia campos del turno, borra mensajes de tools anteriores y recorta la ventana a 6 vueltas | — | 0 |
| `planificar` | el **orquestador** devuelve un `Plan` validado (máx. 3 pasos, agentes de la card, `paralelo`); si falla, `plan_de_respaldo` (documental) | `gpt-oss-120b` | 1 llamada |
| `ejecutar` | corre los pasos (en paralelo si el plan lo pide) y consolida la evidencia | — | ver ejecutores |
| `componer` | **una sola redacción** por turno con la evidencia final; añade cifras del analítico y el aviso de vista | `llama-3.3-70b-instruct` (card) | 1 llamada |
| arista `tras_ejecutar` | replanifica **una** vez si ningún buscador halló evidencia (umbral 0,50) | — | — |

Por qué un plan y no un bucle ReAct: el bucle hace entre 3 y 7 llamadas impredecibles; el
Bloque B normaliza la eficiencia **contra los otros equipos**. Aquí el turno cuesta **2
llamadas** y 3 en el peor caso.

### 5.3 Ejecutores (`src/agents/executors.py`)

| Agente | Qué hace | Tokens |
|---|---|---|
| `agente_documental` | recupera del corpus con `corpus.recuperar()` (sobre-recupera k=40 y aplica filtro **blando** por fenómeno); la redacción es `componer` | 0 aquí |
| `agente_analitico` | conteos exactos sobre la tabla de 1.826 documentos vía `aggregates.agregar`; la dimensión se elige por palabras clave, **sin SQL ni modelo**; declara siempre la cobertura y lo que deja fuera | 0 |
| `agente_visualizador` | pide un `ViewSpec` al modelo pequeño con salida estructurada y catálogo real (`componentes_disponibles`); una vista inválida se descarta y el turno sigue; impone la `nota` de cobertura temporal | 1 llamada |

Un ejecutor **nunca lanza**: un fallo degrada el turno, no lo tumba. Añadir un agente es
registrar una función con `@registrar`, no tocar el grafo.

### 5.4 Guardián (`src/agents/guardian.py`) — determinista, 0 tokens

Vale el 15% del puntaje total del Reto 1 (resistencia a prompt injection). Es determinista
a propósito: un filtro basado en un modelo es más caro y atacable — *se le puede hablar*;
a una expresión regular no.

- **Entrada:** normaliza (NFKC), quita caracteres invisibles y recorta a 4.000 caracteres;
  rechaza 9 familias de inyección (revelar instrucciones, ignorar reglas, cambio de rol,
  modo sin restricciones, extraer configuración, escape de etiquetas…, en español e inglés).
- **Fuera de dominio:** lista deliberadamente **corta y literal** (pedir código, poemas,
  recetas, tareas, consejo médico/legal). Ante la duda deja pasar: un rechazo indebido
  cuesta calidad (40%), mucho más que un falso negativo raro.
- **Salida:** bloquea si la respuesta contiene un secreto real de la configuración
  (`LLM_API_KEY`, `LLM_BASE_URL`) o estructura interna.
- `envolver_documento(texto, chunk_id)` marca cada documento recuperado como **dato, nunca
  instrucción** (`<documento_recuperado>…</documento_recuperado>`). **Ya lo usa `redactar`.**

### 5.5 Caché semántico (`src/agents/memory.py`) — 0 tokens en aciertos

- Compara la consulta por similitud coseno con el **encoder local** (`bge-m3`, en la CPU
  del contenedor, no en el gateway). Umbral **0,95**, tope de **256** entradas.
- Un acierto devuelve la respuesta previa con `metadata` reescrita: 0 llamadas, 0 tokens,
  `estado="cache:<similitud>"`. No infla cifras del turno original.
- Sin encoder cargado cae a coincidencia exacta sobre el texto normalizado. El caché
  **nunca** provoca la carga del modelo. No se cachean errores ni rechazos.
- ⚠️ **El caché es global y compara solo el texto de la pregunta**, no la conversación.
  Ver hallazgo §12 #7.

---

## 6. Agentes y modelos

### Agent card (`agent_card.json`)

Formato propio de ADL (§2.3), **no** el estándar A2A. Se sirve tal cual en
`GET /agent-card`. Es la fuente de verdad de los ids de agente y de su modelo fijo, que
ADL usa para calcular el costo por pregunta. `card.model_for(id)` alimenta el cliente de
cada agente, con `LLM_MODEL` solo como respaldo.

| Id | Modelo declarado (lo que se reporta) | Tools declaradas | Id enviado a LiteLLM |
|---|---|---|---|
| `orquestador` | `gpt-oss-120b` | `delegar_documental`, `delegar_visualizacion` | `gpt-oss-120b` |
| `agente_documental` | `llama-3.3-70b-instruct` | `buscar_corpus`, `detalle_documento` | ✅ traducido: se envía `meta.llama3-3-70b-instruct` |
| `agente_visualizador` | `gpt-oss-20b` | `componentes_disponibles`, `emitir_view_spec` | `gpt-oss-20b` |
| `agente_analitico` | `gpt-oss-20b` | `consultar_agregado` | `gpt-oss-20b` (0 tokens: no llama al modelo) |
| `guardian`, `memoria` | — (deterministas) | no van en la card; **sí** aparecen en `agentes_invocados` | — |

**Dos nombres para un mismo modelo.** La card usa el nombre del PDF de ADL, que es el
que ADL cruza para calcular el costo y el que se **reporta** en `tokens_por_agente`
(`card.model_for`). LiteLLM nombra distinto algunos modelos, y ese es el id con el que
hay que **llamar** (`card.gateway_model_for`, que traduce con `_ALIAS_LITELLM`). Si un id
cambia el día del evento, se corrige **sin tocar código** con la variable de entorno
`MODEL_ALIASES` (JSON: `{"nombre-de-la-card": "id-de-litellm"}`). El agente analitico
declara modelo pero no lo usa: cuesta 0 tokens.

### Modelos disponibles (LiteLLM del evento)

| Nombre en el PDF / card | Id en LiteLLM (el que hay que enviar) |
|---|---|
| gpt-oss-120b / gpt-oss-20b | `gpt-oss-120b`, `gpt-oss-20b` |
| Llama 3.3 70B | `meta.llama3-3-70b-instruct` |
| Llama 4 Scout | `meta.llama4-scout-17b-instruct` |
| Mixtral 8x7B | `mixtral-8x7b-instruct` |
| DeepSeek-R1-Distill | `deepseek.r1` |
| Qwen3-Next-80B | `qwen3-next-80b` |
| Gemma 3 27B | `gemma-3-27b` |

El proxy **también** lista `gpt-4`, `gpt-4o`, `gpt-4o-mini`, `claude-3-haiku` y
`voyage-*`. **No están entre los 8 del reto: no usarlos** (probablemente son del
evaluador; gastarían la bolsa). Las llamadas útiles del proxy son `GET /v1/models`,
`POST /v1/chat/completions`, `GET /key/info` y `GET /health/liveliness`; el resto de su
Swagger es administración.

---

## 7. Observabilidad (`src/observability/`)

Todo el estado por turno vive en `ContextVar` con objetos mutables, para que **dos
requests simultáneas no mezclen su evaluación** (ADL puede mandar preguntas en paralelo).

| Módulo | Qué registra |
|---|---|
| `turnlog.py` | tools llamadas, `retrieval_context`, `citations` (deduplicadas por `chunk_id`) |
| `usage.py` | tokens y llamadas, **con desglose por agente y modelo**; cuenta la llamada aunque el proveedor no devuelva cifras (los tokens quedan en 0, nunca inventados) |
| `tracing.py` | spans jerárquicos de la trayectoria (depuración) |

Un `ContextVar` **no se propaga** a los hilos de un `ThreadPoolExecutor`. `graph.ejecutar`
usa uno cuando el plan tiene 2 o más pasos en paralelo, así que **lanza cada tarea con su
propia copia del contexto** (`contextvars.copy_context().run`); todas comparten los mismos
acumuladores mutables del turno. Como varios hilos escriben en ellos a la vez,
`usage.record_usage` y `turnlog.add_citations` llevan candado. Ver §12 #2.

---

## 8. Recuperación (`src/retrieval/`)

- **Índice:** FAISS con 326.866 chunks (~1,3 GB en RAM). La metadata (344 MB de JSONL)
  **no se carga**: se indexan los offsets (2,6 MB) y cada fila se lee por `seek`.
- **Encoder:** `bge-m3`, una sola instancia compartida entre búsqueda y caché (~2,3 GB en
  RAM). **Corre local: no gasta tokens del presupuesto**, que es la ventaja que `RETO.md`
  señala en el Bloque B.
- **Carga del encoder al arrancar:** la primera carga descarga ~2 GB y tarda ~90 s. Se hace
  en `lifespan` → `encoder.warmup()` en un hilo aparte, para que un evaluador nunca la pague
  como latencia. **El índice, en cambio, se carga en la primera llamada** (ver §12 #8).
- **`aggregates.py`:** conteos y frecuencias sobre la tabla de 1.826 documentos, sin SQL;
  cada resultado trae los `doc_id` que lo sustentan y la cobertura del dato.
- **Modo stub:** `/health` no carga el índice.

---

## 9. Configuración

Lee `os.getenv(...)` (`src/config.py`). En local, desde un `.env` (ignorado por git); en
**Coolify, desde el panel *Environment Variables*, marcadas como *Runtime***. Las
credenciales nunca van en el código ni en la imagen.

| Variable | Para qué | Defecto |
|---|---|---|
| `ARPIA_MODE` | `stub` (simulado) o `live` (real) | `stub` |
| `LLM_BASE_URL` | URL del LiteLLM del evento **terminada en `/v1`** | — |
| `LLM_API_KEY` | key del equipo (bolsa de 100 USD) | — |
| `LLM_MODEL` | **solo respaldo**: cada agente usa el modelo de la card | — |
| `MODEL_ALIASES` | JSON que sobrescribe la traducción *nombre de la card → id de LiteLLM* | — |
| `VECTOR_INDEX_PATH` | ruta del índice dentro del contenedor | `data/encoder_bge_m3` |
| `CHECKPOINT_PATH` | archivo SQLite de la memoria conversacional | `state/checkpoints.sqlite` |
| `AGENT_CARD_PATH` | ruta de la card | `agent_card.json` |
| `SESSION_TTL_S` | vida de la cookie de sesión | `3600` |
| `MAX_AGENT_ITERATIONS` | tope de iteraciones | `6` |
| `REQUEST_TIMEOUT_S` | timeout de **cada** llamada al modelo | `60` |
| `LOG_LEVEL` | nivel de log | `INFO` |

> ⛔ **`ARPIA_MODE=live` antes de las 08:00 del sábado.** En `stub` el endpoint responde
> 200 con la forma perfecta y contenido inventado; `RETO.md` prohíbe datos simulados en
> lo desplegado. Se ve en `mode`, en `metadata.estado` y en `GET /health` (`degraded`
> permanente). Revisarlo antes de la entrega.

---

## 10. Despliegue

> Los requisitos de ADL, los problemas encontrados y **las decisiones aún por tomar**
> (contenedor único, cómo llega el índice, dónde vive el encoder, rama de despliegue) están
> en [`DEPLOY.md`](DEPLOY.md). Esta sección es solo el resumen del estado actual.

- **Un solo contenedor, tres dominios.** `agent.*`, `frontagent.*` y `dashboard.*` apuntan
  al mismo servicio; `routing.py` decide qué HTML servir en `/` según el `Host`
  (`dashboard.*` → tablero; cualquier otro → chat).
- **Coolify:** build pack `Dockerfile`, Base Directory `/arpia`, puerto `8000`, `www
  redirect` en *No redirect*. El `Dockerfile` hace `COPY . .` y **la frontera de qué entra
  la define `.dockerignore`**.
- **Un solo worker de uvicorn, no negociable.** Cada worker carga su propio índice y
  encoder (~3,8 GB medidos); con 8 GB, dos workers rozan el límite. La concurrencia la
  atiende el threadpool de FastAPI.
- **Tres volúmenes persistentes:**
  1. `data/` — el corpus, **solo lectura**.
  2. `state/` — memoria conversacional (SQLite), escribible y **separado** de `data/`.
  3. `HF_HOME=/app/.cache/huggingface` — el encoder; sin él, cada despliegue baja 2,2 GB.
- **`requirements.txt` se regenera siempre con** `uv export --no-hashes --extra retrieval
  --format requirements-txt -o requirements.txt`. Sin `--extra retrieval` la imagen sale sin
  `faiss`, `sentence-transformers` ni `torch`: arranca, responde 200 y no encuentra nada.
- ⚠️ **El índice no está en la imagen** (`.dockerignore` excluye `data/`, `*.faiss`,
  `*.jsonl`). `docker-compose` lo monta como volumen, pero **Coolify no usa ese compose**:
  hay que crear el *Storage* con el índice.
- **Ventana de evaluación:** el endpoint del Reto 1 **no se toca entre las 08:00 y las
  12:30**. Un redeploy ahí puede tumbar la evaluación.
- **Calentamiento:** en la prueba de escritorio, la primera llamada tardó ~19 s (arranque
  en frío) y las siguientes ~3 s. Conviene una llamada de calentamiento tras cada despliegue.

---

## 11. Cómo correrlo y probarlo

```bash
cd arpia
uv sync --extra retrieval                                   # faiss + torch: pesado
cp .env.example .env                                        # y rellenar; ARPIA_MODE=stub por defecto
uv run uvicorn src.api.main:app --reload --port 8000

uv run ruff check src tests --fix && uv run ruff format src tests
uv run pytest tests -q                                      # 214 casos
```

214 casos en total (algunas funciones están parametrizadas; la columna cuenta funciones).

| Archivo de pruebas | Qué protege | Funciones |
|---|---|---|
| `test_contract.py` | contratos, alias, `ViewSpec` cerrado, validador de tokens | 27 |
| `test_graph.py` | plan, replanificación única, coste por turno, memoria, aislamiento de sesiones | 24 |
| `test_modelos.py` | nombre de la card → id de LiteLLM; los clientes reales reciben el id traducido | 7 |
| `test_paralelo.py` | un plan paralelo no pierde `tools_called`, contexto ni tokens; sin mezcla entre turnos | 4 |
| `test_e2e_metadata.py` | un turno completo por `run_chat` con grafo real: lo que lee ADL | 1 |
| `test_executors.py` | documental, analítico y visualizador | 21 |
| `test_chat.py` | formato ADL, sesión, `thread_id`, requests simultáneas, degradación | 16 |
| `test_memory.py` | caché semántico: umbral, tope, cero falsos aciertos | 13 |
| `test_guardian.py` | ataques rechazados **y** consultas legítimas que no deben rechazarse | 11 |
| `test_enrich.py` | `organizacion` y `anio` derivados | 8 |
| `test_theme.py` | ningún color hexadecimal fuera de `src/theme/` | 6 |

> Las pruebas de `test_graph.py` cuentan llamadas con **contadores del LLM falso**; no leen
> `turnlog` ni `usage`. Por eso no detectaban el fallo de §12 #2; `test_paralelo.py` y
> `test_e2e_metadata.py` sí lo leen (y se comprobó que fallan si el bug se reinstala).
> Sigue sin detectarse lo de §12 #4 (`tools_called` del documental).

### Prueba de escritorio con modelo real (única hecha, previa a las Fases 3 y 4)

`POST /chat` con `"Hola mundo"`, `ARPIA_MODE=live`, `gpt-oss-20b` vía LiteLLM: HTTP 200,
formato ADL completo, `tokens.total` = input + output (741), `X-Session-Id` devuelto.
**El grafo actual (plan + ejecutores) aún no se ha probado con el modelo real.**

---

## 12. Pendientes y hallazgos

Ordenados por impacto en la nota. Los #1 a #4 salieron de revisar el código de las Fases 3
y 4 y no los detectaban las pruebas originales. **#1 y #2 ya están corregidos**; #3 y #4
siguen abiertos.

| # | Tema | Por qué importa | Arreglo propuesto |
|---|---|---|---|
| 1 | ✅ **CORREGIDO.** **El modelo del documental no existe en LiteLLM.** La card dice `llama-3.3-70b-instruct`; LiteLLM acepta `meta.llama3-3-70b-instruct`. `redactar()` captura la excepción y entrega fragmentos crudos con `estado: ok` | En `live`, **toda** respuesta documental saldría sin redactar: se pierden Tono (25%) y Answer Relevancy. Falla en silencio | Hecho: `card.gateway_model_for` traduce el nombre de la card al id de LiteLLM (§6); lo reportado sigue siendo el nombre de la card. Override en Coolify con `MODEL_ALIASES`. Falta confirmar con una llamada real de 1 token |
| 2 | ✅ **CORREGIDO.** **Se pierde la metadata en planes paralelos.** `graph.ejecutar` usa `ThreadPoolExecutor` y los `ContextVar` de `turnlog`/`usage` no llegan a esos hilos. Demostrado: con 2 pasos, `tools_called=[]`, `tokens_por_agente=[]`, `num_interacciones=0` | Un plan con 2+ pasos (comparaciones, "datos + vista") pierde `retrieval_context` (**Faithfulness, 30% del Bloque A**), `citations` y los tokens del visualizador (Bloque B) | Hecho: cada tarea corre con `contextvars.copy_context().run`, más candados en `usage`/`turnlog`. Pruebas en `test_paralelo.py` y `test_e2e_metadata.py` |
| 3 | **Nada probado con el modelo real.** `with_structured_output(Plan)` y `(ViewSpec)` dependen de que LiteLLM y `gpt-oss` soporten salida estructurada | Si falla, el orquestador cae siempre al plan de respaldo y el visualizador nunca emite vista (55% del Reto 2) | Prueba en `live` con `gpt-oss-20b` (barata) sobre 1 pregunta documental, 1 cuantitativa y 1 de vista |
| 4 | **`tools_called` no refleja la recuperación.** El documental llama a `recuperar()` directo, no a la tool `buscar_corpus`; el stub sí la anota. El orquestador tampoco anota `delegar_*` | La card promete `buscar_corpus` y `delegar_*`; la traza no los muestra. Es una inconsistencia detectable en el Bloque D | Anotar `buscar_corpus` dentro de `recuperar()`, y o bien anotar `delegar_*` en `planificar` o ajustar la card a lo que existe |
| 5 | **Índice y encoder en Coolify** | Sin índice, `/chat` cae siempre a `error_grafo` | Crear los 3 *Storages* de §10 y las variables como *Runtime* |
| 6 | **Tope de tiempo por turno** | Hoy cada llamada tiene 60 s; el peor caso son 3 llamadas más recuperación. Un turno que exceda el timeout del evaluador se pierde | Plazo global por turno en `run_chat` que degrade a `_retrieval_fallback` |
| 7 | **El caché ignora la conversación.** Compara solo el texto: "¿y en 2023?" puede recibir la respuesta cacheada de otra conversación | Devuelve una respuesta de otra pregunta con `estado: cache:0.96` | No cachear turnos que dependan del historial (con hilo previo), o incluir el hilo en la clave |
| 8 | **`/health` carga el índice en su primera llamada.** `_check_index` → `check()` → `_load()` (1,3 GB) puede exceder los 5 s del healthcheck | Un healthcheck que falla en el arranque puede marcar el despliegue como fallido | Precalentar el índice en `lifespan`, junto al encoder |
| 9 | `GET /topics` | El frontend lo necesita; solo existe el contrato | Endpoint con los 3 fenómenos y conteos reales |
| 10 | `GET /api/evidence/{chunk_id}` | Trazabilidad del tablero (`RETO.md`) | Endpoint que devuelva texto, `doc_id`, fuente y posición |
| 11 | **Endpoint de datos del tablero** | `aggregates.py` ya calcula los conteos; falta exponerlos: dado un `ViewSpec`, devolver los datos con `doc_id`/`chunk_id` | `POST /api/view-data` reutilizando `aggregates.agregar` |
| 12 | **Documento de arquitectura y propuesta de diseño por fenómeno**, dentro del repo y fuera de `docs/` | Entregable: vale el Bloque D (20%) y el 40% del Reto 2. `docs/architecture.md` está obsoleto | Redactarlo con la justificación de cada decisión de §13 |
| 13 | `static/chat.html` y `static/dashboard.html` | `routing.py` degrada a un aviso legible mientras no existan | Lo mantiene otra sesión |
| 14 | Umbral de evidencia `0,50` sin recalibrar | El propio código lo marca; si salta siempre, gasta una llamada extra por turno | Recalibrar con consultas reales (Fase 5) |
| 15 | Batería de prompt injection end-to-end contra el endpoint | Es el 15% del total del Reto 1 | Script con ataques propios sobre el endpoint desplegado |

### Documentos del repo que están desactualizados

- `arpia-bundle/AGENTS.md` §7 dice "código bajo Apache 2.0 / repo público" y habla de un
  "gateway"; **`RETO.md` manda**: repositorio **privado**, modelos vía LiteLLM/Bedrock.
- `src/api/CONTRATO_GRAFO.md`: describe el grafo anterior; los "tres problemas de memoria"
  que enumera ya los corrigió la Fase 3.

---

## 13. Decisiones de diseño y su porqué

- **Alcance de la API.** El API no conoce nodos ni prompts del grafo. La frontera está en
  [`src/api/CONTRATO_GRAFO.md`](src/api/CONTRATO_GRAFO.md).
- **Contrato tolerante, respuesta estricta.** Se acepta casi cualquier entrada; se emite
  exactamente el formato de ADL.
- **200 con `estado`, nunca 500/422.** Una respuesta degradada y explicada puntúa; una
  excepción no.
- **Lo determinista primero.** Guardián, caché, recuperación y agregación cuestan 0
  tokens. La eficiencia se normaliza contra los demás equipos, así que todo turno que no
  llega al modelo es ventaja.
- **Un plan, no un bucle.** El turno cuesta 2 llamadas (3 en el peor caso), no 3 a 7
  impredecibles.
- **Una sola redacción por turno**, sobre la evidencia final: un plan de tres búsquedas
  cuesta una redacción, no tres.
- **Honestidad de los datos.** Tokens en cero cuando no hubo llamada, no una estimación;
  `mode` y `estado="stub"` para que lo simulado sea inconfundible; vocabulario de
  `ViewSpec` recortado a lo que el corpus soporta; cobertura del 34% declarada siempre.
- **Un contenedor, tres dominios.** Menos piezas que puedan caerse en la ventana de
  evaluación.

### Historia (para ubicar los commits)

| Commit | Qué trajo |
|---|---|
| `2a110ca` Fase 1 | contrato ADL completo, `/chat` en stub, agent card, enrutamiento por host |
| `4b3987e` | índice con metadata por `seek` (810 MB → 3 MB), `enrich.py`, `ViewSpec` podado |
| `faa21af` Fase 2 | guardián y caché semántico, deterministas y sin tokens |
| `cfb0aaf` | un solo servicio, caché persistente del encoder |
| `f17c7c0` | integración: `session.py`, `turnlog.py`, `usage` por agente, `CONTRATO_GRAFO.md` |
| `b2672e8` | checkpointer SQLite en volumen propio; `requirements` con `--extra retrieval` |
| `418aa0e` Fase 3 | orquestador de plan único con memoria conversacional |
| `1f23b11` Fase 4 | los tres ejecutores, con el coste del turno acotado |
