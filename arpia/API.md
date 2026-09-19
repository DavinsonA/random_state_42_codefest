# A.R.P.I.A. — API del Reto 1: qué está construido y cómo funciona

> **Fuente de verdad de la implementación.** [`../RETO.md`](../RETO.md) dice *qué exige
> ADL*; este documento dice *qué hay construido, cómo funciona y qué falta*.
> Ante conflicto con la Especificación Técnica de ADL, manda la de ADL.
>
> Fecha de corte: `main` @ `c92029b` + trazabilidad de los conteos (19 de septiembre de 2026).
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
| Verificador condicional (0 tokens si la respuesta está sana) | ✅ hecho; ⚠️ no está declarado en la card (§12 #16) | `src/agents/verifier.py` |
| Registro por turno (tools, contexto, citas, tokens por agente), también en planes paralelos | ✅ hecho y corregido (§12 #2) | `src/observability/` |
| Índice vectorial, encoder local, agregaciones | ✅ hecho | `src/retrieval/` |
| Enrutamiento por `Host` (un contenedor, 3 dominios) | ✅ hecho | `src/api/routing.py` |
| Traducción del modelo de la card al id de LiteLLM (`gateway_model_for`) | ✅ hecho (§6) | `src/agents/card.py` |
| **Nada se ha probado aún con el modelo real** | ❌ | — |
| Endpoints del tablero: `/api/components`, `/api/aggregate`, `/api/timeline`, `/api/evidence/{chunk_id}`, `/api/trace/{trace_id}` | ✅ hechos | `src/api/dashboard.py` |
| `GET /api/geo` | ⚠️ existe pero responde siempre "no disponible": el corpus no tiene lugar (§14) | `dashboard.py` |
| `GET /api/graph` (lo cita `FRONTEND.md`) | ❌ no existe | — |
| `GET /topics` | ➖ **retirado**: se eliminó el contrato sin ruta ni consumidor (`adea37f`) | — |
| Chat web (`chat.html`), sin CDN | ✅ hecho | `src/ui/static/` |
| Tablero web (`dashboard.html`) y librerías vendorizadas (Plotly, Leaflet) | ❌ **no existen**: `dashboard.*` muestra un aviso (§14) | `src/ui/static/` |

**Lo más importante que hay que saber:** el backend está construido y sus 319 pruebas
pasan; **casi todas usan modelos falsos**, y con el modelo real solo hay pruebas manuales
(§11). Esas pruebas manuales, hechas el 19 de septiembre con el índice de la Etapa 1, el
encoder `bge-m3` y LiteLLM, **funcionan de punta a punta** (pregunta documental, cuantitativa
y de vista) y confirmaron los arreglos de §12 #1 y #2. Encontraron además dos fallos nuevos
que ninguna prueba con modelo falso podía ver (§12 #22 y #23). **El tablero web aún no
existe**: hay endpoints de datos (`/api/*`) pero no `dashboard.html`, así que el dominio
`dashboard.*` hoy muestra un aviso (§14).

---

## 2. Endpoints

| Método y ruta | Para qué | Quién lo consume |
|---|---|---|
| `POST /chat` | Un turno de conversación. **Es lo que evalúa ADL.** | ADL, frontend de chat, dashboard |
| `GET /agent-card` | Agent card en JSON (formato ADL §2.3, no A2A) | ADL, expertos |
| `GET /health` | ¿Está vivo el contenedor y con qué capacidades? | Coolify (healthcheck), humanos |
| `GET /usage` | Consumo acumulado del proceso y eficacia del caché | Nosotros (vigilar los 100 USD) |
| `GET /` | Sirve `chat.html` o `dashboard.html` según el `Host` (`src/ui/static/`) | Navegador |
| `GET /api/components` | Catálogo de componentes y valores reales de cada dimensión | Tablero, agente visualizador |
| `GET /api/aggregate` | Conteos agregados con los `doc_id` que los sustentan | Tablero |
| `GET /api/timeline` | Serie anual de documentos, con su cobertura | Tablero |
| `GET /api/geo` | **Siempre `disponible: false`**: el corpus no tiene lugar | Tablero |
| `GET /api/evidence/{chunk_id}` | El fragmento exacto detrás de una cita | Tablero, chat |
| `GET /api/trace/{trace_id}` | Árbol de ejecución de un turno reciente. **Cerrado por defecto**: solo responde con `ARPIA_DEBUG_TRACE` (expone preguntas, fragmentos y salidas del modelo) | Nosotros (depurar) |
| `POST /api/view` | Resuelve un `ViewSpec` a los datos que el tablero debe pintar, validándolo contra el mismo esquema cerrado del visualizador | Tablero |

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
| `max_llamadas_por_turno` | tope real de llamadas al modelo por turno, calculado desde los topes del grafo (reemplaza al antiguo `max_iterations`, que ya nadie aplicaba) |
| `debug_trace` | `true` si `/api/trace` está publicado; `/health` advierte si queda encendido |
| `tools_registered`, `warnings` | tools disponibles y avisos legibles |

Los endpoints `/api/*` siguen la misma regla: **siempre 200**; un fallo o un dato
inexistente llega como `{"disponible": false, "motivo": "…"}`. Detalle en §14.

Semántica de `/health`: `200` con `ok`/`degraded`; **`503` solo si nada funciona**. En `stub` nunca es
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
  "view_spec": null,                     // ViewSpec (§4) solo si el turno pide una vista
  "trace_id": "…"                        // correlaciona con GET /api/trace/{trace_id}
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
- **Operación:** `HealthResponse` (incluye `memoria_persistente`), `UsageResponse` (incluye
  las estadísticas del `verificador` y del caché).
- `AgentResponse.trace_id` correlaciona cada respuesta con su árbol de ejecución.

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
START → begin → planificar → ejecutar ─┬→ componer → verificar → END
                    ▲                  │  (evidencia insuficiente y replans < 1)
                    └──────────────────┘
```

| Nodo | Qué hace | Modelo | Costo |
|---|---|---|---|
| `begin` | agrega la pregunta, reinicia campos del turno, borra mensajes de tools anteriores y recorta la ventana a 6 vueltas | — | 0 |
| `planificar` | el **orquestador** devuelve un `Plan` validado (máx. 3 pasos, agentes de la card, `paralelo`); si falla, `plan_de_respaldo` (documental) | `gpt-oss-120b` | 1 llamada |
| `ejecutar` | corre los pasos (en paralelo si el plan lo pide) y consolida la evidencia | — | ver ejecutores |
| `componer` | **una sola redacción** por turno con la evidencia final; añade cifras del analítico y el aviso de vista | `llama-3.3-70b-instruct` (card) | 1 llamada |
| `verificar` | contrasta la respuesta contra su evidencia; solo llama al modelo si detecta un problema (§5.6) | `llama-3.3-70b-instruct` (card) | 0, o 1 llamada si se activa |
| arista `tras_ejecutar` | replanifica **una** vez si ningún buscador halló evidencia (umbral 0,50) | — | — |

Por qué un plan y no un bucle ReAct: el bucle hace entre 3 y 7 llamadas impredecibles; el
Bloque B normaliza la eficiencia **contra los otros equipos**. Aquí el turno cuesta **2
llamadas** y 3 en el peor caso (replanificación); el verificador suma una más **solo** si
detecta un problema.

**Presupuesto de tiempo** (`src/agents/budget.py`, `adea37f`): el turno tiene un tope total
(`TURN_BUDGET_S`, 75 s) y `REQUEST_TIMEOUT_S` baja a 25 s por llamada. Al agotarse el tiempo no se
replanifica, no se redacta con modelo y no se verifica: se responde con la evidencia ya recuperada. El
frontend abandona a los 90 s.

### 5.3 Ejecutores (`src/agents/executors.py`)

| Agente | Qué hace | Tokens |
|---|---|---|
| `agente_documental` | recupera del corpus con `corpus.recuperar()` (sobre-recupera k=40 y aplica filtro **blando** por fenómeno); la redacción es `componer` | 0 aquí |
| `agente_analitico` | conteos exactos sobre la tabla de 1.826 documentos vía `aggregates.agregar`; la dimensión la fija el plan (`Paso.group_by`) y la heurística por palabras clave es solo el respaldo; **sin SQL ni modelo**. **Cada cifra cita 3 documentos de muestra** y el turno deja `citations` y `retrieval_context` (ver abajo) | 0 |
| `agente_visualizador` | pide un `ViewSpec` al modelo pequeño con salida estructurada y catálogo real (`componentes_disponibles`); una vista inválida se descarta y el turno sigue; impone la `nota` de cobertura temporal | 1 llamada |

**Trazabilidad de las cifras.** `RETO.md` exige que todo dato mostrado se rastree a su `doc_id` y
`chunk_id` (PDF §3.3 y B.1.3 para los datos de un componente y las variables derivadas como
`organizacion` y `anio`). Un conteo no recupera fragmentos, pero cada cifra descansa sobre documentos
reales, así que `analitico` los hace visibles por construcción:

- **En el texto:** `- CSIS_Aerospace: 214 documentos (ej.: F2-CSIS-014, F2-CSIS-015, F2-CSIS-016)`. La cifra
  es el conteo **total**; los tres documentos son una muestra (`MUESTRA_POR_CIFRA`), no la lista completa.
- **En `citations`:** una cita por cifra, con el `chunk_id` del primer fragmento de ese documento y su texto
  real (`corpus.citar_documentos`); se abre con `GET /api/evidence/{chunk_id}`. No fuerza la carga del índice
  (si no está cargado o falla, no cita y el conteo sigue).
- **En `retrieval_context`:** una línea por cifra (`(agregado por organizacion) CSIS_Aerospace: 214 documentos.
  Documentos de ejemplo: …`), más la cobertura si el texto la afirma. Faithfulness se calcula contra este campo;
  vacío, cada cifra del texto se juzga como una afirmación sin sustento. *Interpretación del equipo:* el PDF
  dice que el campo aplica "si el agente hizo uso de recuperación"; no está confirmado cómo trata ADL un campo
  vacío en una respuesta cuantitativa.
- **La evidencia cubre todas las filas del texto** (antes solo las 10 primeras).

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
- **Distingue conversaciones** (`adea37f`): un primer turno acierta contra cualquier sesión; un
  seguimiento solo dentro de la suya ("¿y en 2023?" tiene el mismo texto en dos hilos y significa cosas
  distintas).
- ⚠️ Guarda como buena la respuesta del plan de respaldo (§12 #23).

### 5.6 Verificador (`src/agents/verifier.py`) — condicional, 0 tokens si la respuesta está sana

Corre al final del turno (`componer → verificar`). Detecta afirmaciones que la evidencia no
respalda, con una comparación de conjuntos que **no cuesta tokens**: solo cuando falla paga
una llamada para corregir. Dos disparadores, ambos de alta precisión a propósito:

- **Cita fabricada:** la respuesta menciona un `doc_id` (`F1-XXXX-001`) que no está en la
  evidencia del turno.
- **Cero citas con evidencia disponible**, y solo si la respuesta tiene ≥ 240 caracteres: se
  recuperó material y la respuesta no se apoya en ninguno.

Si no puede corregir, **degrada** la respuesta a "no hay evidencia suficiente" en vez de
devolver una cita inventada. Se descartó "puntaje de recuperación bajo" como disparador: una
pregunta fuera de dominio puntúa 0,552 y la peor legítima 0,606; cinco centésimas no separan
nada. `GET /usage` expone `verificador` (turnos, activaciones, tasa): si la tasa se acerca a
1, el disparador está mal puesto y se paga una llamada extra por turno.

**Conteos exactos.** La evidencia agregada del analítico (`chunk_id` sintético `agregado:…`) no se
somete a la exigencia de citar: `sin_citas` mira solo la evidencia documental. Pero los `doc_id` de muestra
que el analítico cita **sí cuentan como disponibles** para decidir si una cita es fabricada, porque son
documentos reales. Sin esto, cada respuesta cuantitativa trazable se leería como "cita fabricada" y se
reescribiría con un modelo. La trazabilidad de las cifras la garantiza el propio agente (§5.3), no una
revisión con modelo.

El verificador **está declarado en la agent card** (`adea37f`) con el modelo de `agente_documental`, y
aparece en `agentes_invocados` y `tokens_por_agente` solo cuando llama al modelo.

### 5.7 Voz del sistema (`src/agents/voz.py`)

Desde `cacadf9` y `c92029b`, todo el texto que lee el usuario nace de un solo módulo: el **registro** que
comparten los prompts y las ocho respuestas fijas (rechazos, degradaciones). Es un registro de producto
analítico: conclusión primero, impersonal, procedencia caracterizada (`AI Index Stanford (2018,
F1-AIINDEX-016)` en vez de un identificador opaco) y lo no cubierto por el corpus en su propio párrafo. **Sin
pronósticos ni escalas estimativas** (`RETO.md` prohíbe fabricar una medición) y con **neutralidad técnica**
explícita (Toxicity es el 15% del bloque de calidad y el corpus trata de actores armados y capacidades
antisatélite). El orquestador, el redactor, el verificador y el visualizador usan el mismo registro (el del
visualizador es una versión breve). Coste medido por el equipo: ~20% más de tokens por redacción.

---

## 6. Agentes y modelos

### Agent card (`agent_card.json`)

Formato propio de ADL (§2.3), **no** el estándar A2A. Se sirve tal cual en
`GET /agent-card`. Es la fuente de verdad de los ids de agente y de su modelo fijo, que
ADL usa para calcular el costo por pregunta. `card.model_for(id)` alimenta el cliente de
cada agente, con `LLM_MODEL` solo como respaldo.

| Id | Modelo declarado (lo que se reporta) | Tools declaradas | Id enviado a LiteLLM |
|---|---|---|---|
| `orquestador` | `gpt-oss-120b` | `delegar_documental`, `delegar_visualizacion`, `delegar_analitico` | `gpt-oss-120b` |
| `agente_documental` | `llama-3.3-70b-instruct` | `buscar_corpus`, `detalle_documento` | ✅ traducido: se envía `meta.llama3-3-70b-instruct` |
| `agente_visualizador` | `gpt-oss-20b` | `componentes_disponibles`, `emitir_view_spec` | `gpt-oss-20b` |
| `agente_analitico` | `gpt-oss-20b` | `consultar_agregado` | `gpt-oss-20b` (0 tokens: no llama al modelo) |
| `guardian`, `memoria` | — (deterministas) | no van en la card; **sí** aparecen en `agentes_invocados` | — |
| `verificador` | `llama-3.3-70b-instruct` | — (sin tools) | `meta.llama3-3-70b-instruct` |

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
| `tracing.py` | spans jerárquicos de la trayectoria; conserva las **últimas 50 trazas** en memoria, consultables por `GET /api/trace/{trace_id}` |

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
  como latencia. El arranque también precalienta el índice y la tabla de agregados (`adea37f`), así que `/health` ya no carga 1,3 GB en su
  primera llamada.
- **`aggregates.py`:** conteos y frecuencias sobre la tabla de 1.826 documentos, sin SQL;
  cada resultado trae los `doc_id` que lo sustentan y la cobertura del dato.
- **`index.chunk(chunk_id)`** devuelve un fragmento por su id (lo usa `GET /api/evidence`).
- **El tablero depende del índice.** `aggregates.tabla()` se construye desde `_get_index().document_table()`. Si el
  índice no está, **ya no se cachea una tabla vacía** (`adea37f`): los endpoints responden `disponible: false` y
  reintentan en la siguiente petición.
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
| `ARPIA_DEBUG_TRACE` | publica `GET /api/trace` (preguntas, fragmentos y salidas del modelo). **Solo desarrollo; vacío en el despliegue evaluado** | vacío |
| `REQUEST_TIMEOUT_S` | timeout de **cada** llamada al modelo | `25` |
| `TURN_BUDGET_S` | presupuesto total de un turno; al agotarse no se empieza nada caro nuevo | `75` |
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
  (`dashboard.*` → `dashboard.html`; cualquier otro → `chat.html`). Los archivos viven en
  `src/ui/static/` y entran a la imagen con `COPY . .`. **`dashboard.html` no existe todavía**:
  hasta que exista, `dashboard.*` responde 200 con un aviso.
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
uv run pytest tests -q                                      # 319 casos
```

319 casos en total (algunas funciones están parametrizadas; la columna cuenta funciones).

| Archivo de pruebas | Qué protege | Funciones |
|---|---|---|
| `test_contract.py` | contratos, alias, `ViewSpec` cerrado, validador de tokens | 27 |
| `test_graph.py` | plan, replanificación única, coste por turno, memoria, aislamiento de sesiones | 27 |
| `test_modelos.py` | nombre de la card → id de LiteLLM; los clientes reales reciben el id traducido | 7 |
| `test_paralelo.py` | un plan paralelo no pierde `tools_called`, contexto ni tokens; sin mezcla entre turnos | 4 |
| `test_e2e_metadata.py` | un turno completo por `run_chat` con grafo real: lo que lee ADL | 1 |
| `test_executors.py` | documental, analítico y visualizador | 31 |
| `test_chat.py` | formato ADL, sesión, `thread_id`, requests simultáneas, degradación | 17 |
| `test_memory.py` | caché semántico: umbral, tope, cero falsos aciertos | 16 |
| `test_guardian.py` | ataques rechazados **y** consultas legítimas que no deben rechazarse | 11 |
| `test_enrich.py` | `organizacion` y `anio` derivados | 8 |
| `test_dashboard.py` | endpoints `/api/*`: nunca 500, cobertura, trazabilidad, `geo` no disponible | 23 |
| `test_verifier.py` | disparadores del verificador, degradación y que no salte en respuestas sanas ni en conteos | 13 |
| `test_voz.py` | la voz del sistema vive en un solo módulo; ningún prompt define su propio tono | 15 |
| `test_trazabilidad_analitico.py` | cada cifra cita sus documentos; `citations` y `retrieval_context` llenos; el verificador no reescribe un conteo trazable; el conteo no se cae si el índice falla | 12 |
| `test_theme.py` | ningún color hexadecimal fuera de `src/theme/` | 6 |

> Las pruebas de `test_graph.py` cuentan llamadas con **contadores del LLM falso**; no leen
> `turnlog` ni `usage`. Por eso no detectaban el fallo de §12 #2; `test_paralelo.py` y
> `test_e2e_metadata.py` sí lo leen (y se comprobó que fallan si el bug se reinstala).
> Sigue sin detectarse lo de §12 #4 (`tools_called` del documental).

### Pruebas manuales con el modelo real (19 de septiembre)

Con el índice de la Etapa 1 (326.866 fragmentos), `bge-m3` en CPU y LiteLLM (`gpt-oss-120b`,
`gpt-oss-20b`, `llama-3.3-70b-instruct`), servidor en modo `live`:

| Pregunta | Resultado |
|---|---|
| Documental ("¿qué reporta el corpus sobre capacidades antisatélite?") | 12 s, 3.561 tokens, respuesta redactada con `doc_id` reales, 8 fragmentos en `retrieval_context` y 8 citas |
| Cuantitativa ("¿cuántos documentos hay por fenómeno?") | antes de `c9f48f5`: 3 s, 896 tokens, 1 llamada, F3 = 888, F2 = 479, F1 = 459 (suman 1.826). **Después: falla el orquestador (§12 #22)** |
| Vista ("grafica la cantidad de documentos por organizacion") | `ViewSpec` válido con `gpt-oss-20b`; con la trazabilidad de §5.3: 2.342 tokens, sin llamar al verificador, 20 cifras con 20 citas y 20 líneas de contexto |
| Seguimiento ("resúmelo en una sola frase") | **no usa la conversación**: ningún agente lee el historial (§12 #24) |
| Caché semántico | un acierto sirvió la respuesta en 0 tokens |

Confirmado con el proxy real: la traducción de modelos (§6), la salida estructurada del `Plan` y del
`ViewSpec`, y `memoria_persistente: true`. **No confirmado:** el comportamiento con las preguntas
que evaluará ADL (batería propia de preguntas y ataques) ni la carga concurrente.

---

## 12. Pendientes y hallazgos

Ordenados por impacto en la nota. Los #1 a #4 salieron de revisar el código de las Fases 3
y 4 y no los detectaban las pruebas originales. **#1 y #2 ya están corregidos**; #3 y #4
siguen abiertos. Del #9 al #13 se atendieron con la Fase 5, y Davinson cerró en `cfa7c79` y `adea37f` los
pendientes #6, #7, #8, #9, #16, #17, #21 y la delegación de #4 (ver cada fila); del #16 al #24
son nuevos (el #22, #23 y #24 salieron de las pruebas con el modelo real).

Para quien lleva los agentes: [`PENDIENTES_AGENTES.md`](PENDIENTES_AGENTES.md) resume los hallazgos abiertos del
orquestador, el caché y la memoria con su evidencia, su propuesta de arreglo y cómo comprobarlo.

| # | Tema | Por qué importa | Arreglo propuesto |
|---|---|---|---|
| 1 | ✅ **CORREGIDO.** **El modelo del documental no existe en LiteLLM.** La card dice `llama-3.3-70b-instruct`; LiteLLM acepta `meta.llama3-3-70b-instruct`. `redactar()` captura la excepción y entrega fragmentos crudos con `estado: ok` | En `live`, **toda** respuesta documental saldría sin redactar: se pierden Tono (25%) y Answer Relevancy. Falla en silencio | Hecho: `card.gateway_model_for` traduce el nombre de la card al id de LiteLLM (§6); lo reportado sigue siendo el nombre de la card. Override en Coolify con `MODEL_ALIASES`. Falta confirmar con una llamada real de 1 token |
| 2 | ✅ **CORREGIDO.** **Se pierde la metadata en planes paralelos.** `graph.ejecutar` usa `ThreadPoolExecutor` y los `ContextVar` de `turnlog`/`usage` no llegan a esos hilos. Demostrado: con 2 pasos, `tools_called=[]`, `tokens_por_agente=[]`, `num_interacciones=0` | Un plan con 2+ pasos (comparaciones, "datos + vista") pierde `retrieval_context` (**Faithfulness, 30% del Bloque A**), `citations` y los tokens del visualizador (Bloque B) | Hecho: cada tarea corre con `contextvars.copy_context().run`, más candados en `usage`/`turnlog`. Pruebas en `test_paralelo.py` y `test_e2e_metadata.py` |
| 3 | ✅ **Probado con el modelo real (19-sep).** La salida estructurada del `Plan` y del `ViewSpec` funciona en LiteLLM con `gpt-oss`, con una excepción (#22) | — | Falta una batería propia de preguntas y ataques |
| 4 | ✅ **HECHO en `c9f48f5` y `cfa7c79`.** `recuperar()` registra `buscar_corpus` y cada delegación del orquestador queda como `delegar_*` en `tools_called` (con los argumentos que declara la card) | — | Comprobado con el modelo real para la búsqueda documental |
| 5 | **Índice y encoder en Coolify** | Sin índice, `/chat` cae siempre a `error_grafo` | Crear los 3 *Storages* de §10 y las variables como *Runtime* |
| 6 | ✅ **HECHO en `adea37f`.** Presupuesto de tiempo por turno (`budget.py`) | Antes el peor caso eran 3 × 60 s y el frontend abandona a los 90 s | `TURN_BUDGET_S=75`, `REQUEST_TIMEOUT_S=25` y tres puntos de control. Falta medirlo con el modelo real |
| 7 | ✅ **HECHO en `adea37f`.** El caché distingue conversaciones | Antes un seguimiento ("¿y en 2023?") podía recibir la respuesta cacheada de otra conversación | Un primer turno acierta contra cualquier sesión; un seguimiento solo dentro de la suya |
| 8 | ✅ **HECHO en `adea37f`.** El arranque precalienta índice, tabla y encoder | `/health` cargaba 1,3 GB en su primera llamada y podía superar los 5 s del healthcheck | — |
| 9 | ✅ **HECHO en `adea37f`.** Se retiró el contrato muerto de `/topics` | Sin ruta y sin consumidor | — |
| 10 | ✅ **HECHO en la Fase 5.** `GET /api/evidence/{chunk_id}` | Trazabilidad del tablero (`RETO.md`) | Existe (`dashboard.py`); falta que el chat lo use al hacer clic en una cita (#20) |
| 11 | ✅ **HECHO en la Fase 5.** Endpoint de datos del tablero | Los datos de un `ViewSpec` salen de `GET /api/aggregate` y `/api/timeline`, con `doc_id` y cobertura | Existe; falta el mapeo `ViewSpec → endpoint` en el frontend (§14) |
| 12 | **Documento de arquitectura y propuesta de diseño por fenómeno**, dentro del repo y fuera de `docs/` | Entregable: vale el Bloque D (20%) y el 40% del Reto 2. `docs/architecture.md` está obsoleto | Redactarlo con la justificación de cada decisión de §13 |
| 13 | `chat.html` ✅ hecho; **`dashboard.html` y `vendor/` (Plotly, Leaflet) ❌ no existen** | El dominio `dashboard.*` muestra un aviso: sin él no hay Reto 2 desplegable (55% ejecución dinámica) | Lo mantiene el frontend; faltan además `viewspec.js` y `charts.js` |
| 14 | Umbral de evidencia `0,50` sin recalibrar | El propio código lo marca; si salta siempre, gasta una llamada extra por turno | Recalibrar con consultas reales (Fase 5) |
| 15 | Batería de prompt injection end-to-end contra el endpoint | Es el 15% del total del Reto 1 | Script con ataques propios sobre el endpoint desplegado |
| 16 | ✅ **HECHO en `adea37f`.** El verificador está declarado en `agent_card.json` | ADL cruza los ids de `agentes_invocados` y `tokens_por_agente` contra la ficha | — |
| 17 | ✅ **HECHO en `adea37f`.** La tabla del corpus no se cachea vacía | Antes, si el volumen del índice no estaba al llegar la primera petición, el tablero quedaba en blanco hasta reiniciar | Los endpoints responden `disponible: false` |
| 18 | **`FRONTEND.md` contradice al backend en 7 puntos** (§14): `fenomeno=` vs `fenomenos=`, citas con `quote`/`score`, `chart: "map"`, `lugar`, `group_by: "mes"`, fechas completas, `/api/graph` | Quien construya el tablero con esa guía escribirá código que el backend rechaza o ignora | Corregir `FRONTEND.md` con la tabla de §14 |
| 19 | ✅ `/api/trace` **cerrado en `86e8244`** (solo con `ARPIA_DEBUG_TRACE`). El resto de `/api/*` sigue siendo público y de solo lectura, en los tres dominios | Lo público ya no expone preguntas ni salidas del modelo | Confirmar que `ARPIA_DEBUG_TRACE` queda vacío en Coolify |
| 20 | **El chat no usa `/api/evidence`**: `api.js` no tiene esa función, así que hacer clic en una cita no abre el fragmento | `FRONTEND.md` lo llama "requisito obligatorio de la especificación" | Añadir `obtenerEvidencia(chunk_id)` a `api.js` y enlazarlo en `chat.js` |
| 21 | ✅ **Resuelto con el presupuesto de tiempo (#6).** Timeout del front (90 s) vs peor caso del backend | — | — |
| 22 | ✅ **Resuelto.** El orquestador fallaba con el modelo real: `gpt-oss-120b` devolvía la clave `Pasos` (el `title` del esquema) y `Plan` (`extra="forbid"`) la rechazaba, con lo que el respaldo mandaba todo al documental. Medido antes: 1 de 6 llamadas válidas; después: 6 de 6, y las tres preguntas típicas responden por `/chat` con el agente correcto | — | `plan.py`: `Plan` y `Paso` normalizan las claves (`Pasos` → `pasos`, `Group By` → `group_by`) y siguen rechazando campos inexistentes. `plan_de_respaldo` manda el conteo inequívoco al analítico (y suma el visualizador si piden una gráfica). `executors._dimension` ya no depende de las tildes. No se añadió reintento: la causa raíz está cerrada y cada reintento costaría tokens |
| 23 | ✅ **Resuelto.** El caché guardaba como buena la respuesta del plan de respaldo (`estado: ok`) y repetir la pregunta la devolvía con `cache:1.00` hasta reiniciar | — | `planificar` anota `turnlog.marcar_no_cacheable("plan_de_respaldo")` en sus dos salidas al respaldo y `run_chat` no guarda en el caché un turno marcado (queda en el log). El `estado` sigue siendo `ok`. Cualquier agente puede usar la misma marca para otros degradados |
| 24 | **Ningún agente lee la conversación.** El historial se guarda en SQLite pero `planificar(pregunta)` y `redactar(pregunta, evidencia)` solo reciben el texto de la pregunta | Una pregunta de seguimiento se responde sin contexto y gasta tokens (4.442 en la prueba); ADL evalúa preguntas sueltas, pero el chat real las necesita | Pasar las últimas vueltas al orquestador y al redactor |

### Documentos del repo que están desactualizados

- `arpia-bundle/AGENTS.md` §7 dice "código bajo Apache 2.0 / repo público" y habla de un
  "gateway"; **`RETO.md` manda**: repositorio **privado**, modelos vía LiteLLM/Bedrock.
- `src/api/CONTRATO_GRAFO.md`: describe el grafo anterior; los "tres problemas de memoria"
  que enumera ya los corrigió la Fase 3.
- `FRONTEND.md`: es una guía para la sesión del frontend y **discrepa del backend real**
  (ver la tabla de §14). Ubica los archivos en `static/`; la ruta real es `src/ui/static/`.

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
- **Trazabilidad por construcción, no por revisión.** Toda cifra que se muestra cita los documentos que la
  sustentan (§5.3). Se descartó eximir a los conteos de citar: `RETO.md` exige rastrear "todo dato mostrado" a
  su `doc_id` y `chunk_id`, y el verificador solo detecta el hueco, no lo cierra. El ahorro de tokens que
  resulta (el verificador ya no se activa en un conteo trazable) es una consecuencia, no el objetivo.

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
| `1c1466e` Fase 5 | verificador condicional, traza consultable (`/api/trace`) y endpoints del tablero (`dashboard.py`) |
| `01efafa` (PR #3) | corrige el modelo del documental (nombre de la card → id de LiteLLM) y la metadata perdida en planes paralelos |
| `5c83a71` | frontend del chat en HTML plano (`src/ui/static/`), sin CDN |
| `c9f48f5` | `tools_called` registra la recuperación; `agentes_invocados` incluye al analítico; `Paso.group_by` |
| `8d96e8d` | el verificador no exige citas a la evidencia agregada; `cobertura.excluidos_por_fecha` |
| `86e8244` | `/api/trace` cerrado por defecto; `POST /api/view` |
| `4ae60f9` | preflight en verde; `/health` expone `max_llamadas_por_turno` |
| `29bdf0f` | cada cifra de un conteo cita los documentos que la sustentan (`citations`, `retrieval_context`) |
| `cfa7c79` | las delegaciones del orquestador quedan en `tools_called`; la card gana `delegar_analitico` |
| `adea37f` | presupuesto de tiempo por turno, caché por conversación, arranque que precalienta, verificador en la card |
| `cacadf9` | `voz.py`: el texto que lee el usuario nace de un solo módulo, con registro de producto analítico |
| `c92029b` | los cuatro prompts (orquestador, redactor, verificador, visualizador) usan la misma voz |

---

## 14. Frontend y tablero (`src/ui/static/`)

`FRONTEND.md` es la guía del equipo de frontend. Este apartado dice **qué existe de verdad** y
dónde esa guía no coincide con el backend.

### Qué hay

| Pieza | Estado |
|---|---|
| `chat.html`, `css/tokens.css`, `css/app.css`, `js/api.js`, `js/chat.js` | ✅ existen |
| `dashboard.html` | ❌ no existe: `dashboard.*` responde 200 con un aviso legible |
| `vendor/` (Plotly, Leaflet) | ❌ no existe |
| `viewspec.js`, `charts.js`, `map.js`, `graph.js` | ❌ no existen (los describe `FRONTEND.md`) |
| Streamlit (`src/ui/app.py`) | sigue en el repo pero **ya no se despliega** |

- **HTML plano, sin framework, sin build.** `chat.html` no tiene ninguna referencia externa
  (verificado): sirve aunque la red del venue falle. `FRONTEND.md` prohíbe CDN y exige
  vendorizar las librerías.
- **Una sola capa de red.** `api.js` es el único que hace `fetch()`; expone `enviarChat`
  (timeout de 90 s) y `obtenerSalud`. Manda `{texto, sesion_id}` a `/chat`.
- **Lee los campos reales del backend:** `metadata.agentes_invocados`, `num_interacciones`,
  `latencia_ms`, `tokens`, `estado`, `mode`, `citations[].doc_id/chunk_id/fuente/fragmento`
  y `view_spec`.
- **Cómo se sirve:** `routing.py` monta `src/ui/static/` dos veces (`/static/...` y `/...`) y
  responde `/` según el `Host`. Como la API y la interfaz salen del mismo contenedor, no hay
  CORS ni URL que configurar.

### Endpoints del tablero (`src/api/dashboard.py`)

Todos devuelven **HTTP 200**. Un fallo o un dato inexistente llega como
`{"disponible": false, "motivo": "…"}`, para que el tablero distinga "no hay dato" de
"el servicio se cayó". Todos cuestan **0 tokens**.

| Endpoint | Parámetros | Devuelve |
|---|---|---|
| `GET /api/components` | — | catálogo: `componentes`, `metricas`, `agrupaciones`, valores reales de cada dimensión y una `nota` de cobertura |
| `GET /api/aggregate` | `metrica`, `group_by`, `fenomenos` (`F1,F2`), `organizacion`, `desde`, `hasta` (años enteros), `limite` (1–100, def. 25) | `filas[{clave, valor, doc_ids}]`, `total`, `cobertura{documentos_universo, documentos_en_dimension, documentos_contados, sin_dato_en_la_dimension}` |
| `GET /api/timeline` | `fenomenos`, `desde`, `hasta` | serie anual ordenada, `granularidad: "anio"`, `cobertura` y un `aviso` con el 34% |
| `GET /api/geo` | — | **siempre `disponible: false`**: la metadata no tiene lugar, país ni coordenadas |
| `GET /api/evidence/{chunk_id}` | — | `chunk_id`, `doc_id`, `texto`, `fuente`, `organizacion`, `anio`, `formato`, `fenomeno`, `fenomeno_nombre` |
| `GET /api/trace/{trace_id}` | — | `spans` del turno (últimas 50 trazas). **Solo con `ARPIA_DEBUG_TRACE`**; si no, `disponible: false` |
| `POST /api/view` | cuerpo: un `ViewSpec` | los datos ya resueltos: `filas`, `total`, `cobertura`, `aviso`, `nota`. Valida con el mismo esquema cerrado que el visualizador; una vista temporal agrupa por año |

Cada cifra viene con los `doc_id` que la sustentan, y `/api/evidence` abre el fragmento
exacto: es la trazabilidad que exige `RETO.md`.

**Mapeo `ViewSpec → endpoint` (propuesta, aún no implementada en el frontend).** Los
parámetros de `/api/aggregate` reflejan los campos del `ViewSpec`:

| `chart` | Endpoint sugerido |
|---|---|
| `bar`, `stacked_bar`, `donut`, `table`, `kpi` | `GET /api/aggregate` con `metrica`, `group_by`, `fenomenos`, `desde`, `hasta` |
| `timeline` | `GET /api/timeline` (o `/api/aggregate` con `group_by=anio`) |

### `FRONTEND.md` frente al backend real

Quien construya el tablero debe seguir **esta columna**, no la guía:

| Tema | `FRONTEND.md` dice | El backend real |
|---|---|---|
| Ubicación de archivos | `static/` | `src/ui/static/` |
| Filtro de fenómeno | `?fenomeno=F3` | `?fenomenos=F3` (plural, admite `F1,F2`) |
| Campos de una cita | `doc_id`, `chunk_id`, `quote`, `score` | `doc_id`, `chunk_id`, **`fuente`**, **`fragmento`** (sin `score`) |
| Tipos de gráfico | `timeline`, `bar`, `map`, `table` | `timeline`, `bar`, `stacked_bar`, `donut`, `table`, `kpi` — **sin `map`** |
| Rango de fechas | `"desde": "2024-01-01"` | año de 4 dígitos (`"2024"`), patrón `^\d{4}$` |
| Agrupación temporal | `group_by: "mes"` | solo `anio`; no hay `mes` ni `trimestre` |
| Lugar | `"lugar": null` en el `ViewSpec` | el campo **no existe** (`extra="forbid"` lo rechazaría) |
| Grafo de entidades | `GET /api/graph` | **no existe**: no hay extracción de entidades |
| Mapas | Leaflet con capas por fenómeno | `/api/geo` responde siempre "no disponible"; no hay dato geográfico |

El frontend **ya lee** los campos correctos en `chat.js`; la discrepancia está en la guía y
en lo que aún no se ha construido (el tablero).
