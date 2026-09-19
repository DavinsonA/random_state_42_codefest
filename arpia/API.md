# A.R.P.I.A. — API del Reto 1: qué está construido y cómo funciona

> **Fuente de verdad de la implementación.** [`../RETO.md`](../RETO.md) dice *qué exige
> ADL*; este documento dice *qué hay construido, cómo funciona y qué falta*.
> Ante conflicto con la Especificación Técnica de ADL, manda la de ADL.
>
> Fecha de corte: `main` @ `f17c7c0` (18–19 de septiembre de 2026).
> Si cambias el contrato o el comportamiento de un endpoint, **actualiza este archivo
> en el mismo commit**. Un documento desactualizado es peor que ninguno.

---

## 1. Estado de un vistazo

| Pieza | Estado | Dónde |
|---|---|---|
| `POST /chat` en el formato exacto de ADL §2.4 | ✅ hecho y probado | `src/api/chat.py`, `main.py` |
| Contratos Pydantic (entrada, salida, `ViewSpec`) | ✅ hecho | `src/api/contracts.py` |
| Sesión (`sesion_id`) | ✅ hecho (servidor + cookie/header) | `src/api/session.py` |
| `GET /agent-card` (formato ADL §2.3) | ✅ hecho | `agent_card.json`, `src/agents/card.py` |
| `GET /health`, `GET /usage` | ✅ hecho | `src/api/main.py` |
| Guardián anti-inyección (0 tokens) | ✅ hecho | `src/agents/guardian.py` |
| Caché semántico (0 tokens en aciertos) | ✅ hecho | `src/agents/memory.py` |
| Registro por turno (tools, contexto, citas, tokens por agente) | ✅ hecho | `src/observability/` |
| Índice vectorial + encoder local + dimensiones derivadas | ✅ hecho | `src/retrieval/` |
| Enrutamiento por `Host` (un contenedor, 3 dominios) | ✅ hecho | `src/api/routing.py` |
| **Agentes reales** (orquestador, documental, visualizador, analítico) | ❌ **no existen**; solo están declarados en la card y simulados en `stub.py` | — |
| Modelo por agente (una variable por agente) | ❌ pendiente de decisión | `src/config.py` |
| Memoria conversacional del grafo (checkpointer) | ❌ no conectada | `src/agents/graph.py` |
| `GET /topics` | ⏳ solo el contrato (`TopicsResponse`); sin endpoint | `contracts.py` |
| `GET /api/evidence/{chunk_id}` | ⏳ mencionado en `contracts.py`; sin endpoint | — |
| Interfaces `chat.html` / `dashboard.html` | ❌ `static/` no existe todavía (la mantiene otra sesión) | `routing.py` |

**Lo más importante que hay que saber:** hoy `POST /chat` en modo `live` ejecuta el
`graph.py` original (una plantilla de **un solo agente**, con un solo modelo,
`LLM_MODEL`). La agent card, en cambio, declara **cuatro** agentes. Esa diferencia
la evalúa ADL en el Bloque D (Diseño, 20%). Ver §12.

---

## 2. Endpoints

| Método y ruta | Para qué | Quién lo consume |
|---|---|---|
| `POST /chat` | Un turno de conversación. **Es lo que evalúa ADL.** | ADL, frontend de chat, dashboard |
| `GET /agent-card` | Agent card en JSON (formato ADL §2.3, no A2A) | ADL, expertos |
| `GET /health` | Estado y capacidades del servicio | Coolify, humanos |
| `GET /usage` | Consumo acumulado del proceso y eficacia del caché | Nosotros (vigilar los 100 USD) |
| `GET /` | Sirve `chat.html` o `dashboard.html` según el `Host` | Navegador |

### Regla dura: nunca un 500 ni un 422

Ningún camino devuelve un error de servidor ni de validación. Un fallo interno, una
dependencia caída o un cuerpo raro se responden con **HTTP 200** y el detalle en
`metadata.estado`. Un 422 delante del evaluador puntúa cero en esa pregunta; una
respuesta degradada y explicada, no. Hay un manejador de `RequestValidationError`
como red de seguridad (`main.py`).

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
- Un id del cliente solo se acepta si cumple `^[A-Za-z0-9_-]{8,64}$`: se usa como
  `thread_id` de la memoria y no puede ser una cadena arbitraria.
- **Por qué sin id = sesión nueva:** el evaluador de ADL probablemente no manda
  `sesion_id` y hace preguntas independientes. Compartir sesión arrastraría historial
  (más tokens, peor Faithfulness) y dejaría que un ataque de inyección contamine las
  preguntas siguientes.
- El `sesion_id` viaja al grafo como `config["configurable"]["thread_id"]`. **Hoy el
  grafo no tiene checkpointer, así que no hay memoria conversacional efectiva**: el
  id llega pero no se usa (ver §12).

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
      { "name": "buscar_corpus", "input_parameters": {"query": "…", "k": 8}, "output": "…" }
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
| `respuesta`, `actual_output` | grafo | `result["answer"]` |
| `evaluacion.input` | API | el texto recibido (ya saneado por el guardián) |
| `tools_called` | tools | el decorador `@registry.register` lo anota solo en `turnlog` |
| `retrieval_context`, `citations` | tools de recuperación | `turnlog.add_context(...)` / `turnlog.add_citations(...)`; `buscar_corpus` ya lo hace |
| `tokens`, `tokens_por_agente`, `num_interacciones` | grafo | `usage.record_usage(usage_metadata, agent=…, model=…)` en **cada** llamada al LLM |
| `latencia_ms`, `estado`, `mode` | API | medidos en `chat.py` |
| `view_spec` | agente visualizador | `ViewSpec` validado contra esquema cerrado |

Regla del validador de `Metadata`: si hay `tokens_por_agente`, `tokens` se **recalcula**
como su suma. ADL marca como inconsistencia reportar en `tokens.total` menos de lo que
suma el desglose. No lanza: un descuadre aritmético no puede convertirse en un 500.

### 3.5 Valores de `metadata.estado`

| Valor | Cuándo | Costo |
|---|---|---|
| `ok` | respuesta normal | tokens del turno |
| `stub` | `ARPIA_MODE=stub`: respuesta **simulada** | 0 |
| `cache:0.97` | la resolvió el caché semántico (la cifra es la similitud) | 0, y `agentes_invocados=["memoria"]` |
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
  por eso toda vista temporal debe llevar una `nota` declarando su cobertura.

---

## 5. Ciclo de un turno (`chat.run_chat`)

```
guardian.revisar_entrada → memoria.buscar → EJECUCIÓN → guardian.revisar_salida → memoria.guardar
     (0 tokens, veto)      (0 tokens, atajo)   stub o grafo    (0 tokens, veto)     (solo si fue ok)
```

El orden importa: rechazar un ataque cuesta cero y no debe llegar ni al caché ni al modelo;
un acierto de caché ahorra el turno entero; la revisión de salida es la última barrera.

### Guardián (`src/agents/guardian.py`) — determinista, 0 tokens

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
- `envolver_documento(texto, chunk_id)` marca el contenido recuperado como **dato, nunca
  instrucción** (`<documento_recuperado>…</documento_recuperado>`). **Está definido pero
  ninguna tool ni el grafo lo usa todavía** (§12).

### Caché semántico (`src/agents/memory.py`) — 0 tokens en aciertos

- Compara la consulta por similitud coseno con el **encoder local** (`bge-m3`, en la CPU
  del contenedor, no en el gateway). Umbral **0,95**, tope de **256** entradas.
- Un acierto devuelve la respuesta previa con `metadata` reescrita: 0 llamadas, 0 tokens,
  `estado="cache:<similitud>"`. No infla cifras del turno original.
- Sin encoder cargado cae a coincidencia exacta sobre el texto normalizado. El caché
  **nunca** provoca la carga del modelo.
- No se cachean errores ni rechazos.
- ⚠️ **El caché es global, no por sesión**: dos usuarios que hagan la misma pregunta
  comparten la respuesta.
- `ventana_historial` (recorta a 6 turnos) existe pero **no está conectada** al grafo.

---

## 6. Agentes y modelos

### Agent card (`agent_card.json`)

Formato propio de ADL (§2.3), **no** el estándar A2A. Se sirve tal cual en
`GET /agent-card`. Es la fuente de verdad de los ids de agente y de su modelo fijo, que
ADL usa para calcular el costo por pregunta (`src/agents/card.py`).

| Id | Modelo declarado | Tools declaradas |
|---|---|---|
| `orquestador` | `gpt-oss-120b` | `delegar_documental`, `delegar_visualizacion` |
| `agente_documental` | `llama-3.3-70b-instruct` | `buscar_corpus`, `detalle_documento` |
| `agente_visualizador` | `gpt-oss-20b` | `componentes_disponibles`, `emitir_view_spec` |
| `agente_analitico` | `gpt-oss-20b` | `consultar_agregado` |
| `guardian`, `memoria` | — (deterministas) | no van en la card; **sí** aparecen en `agentes_invocados` |

Regla: **los nombres de las tools en el código coinciden exactamente con los de la card**
(`buscar_corpus`, `detalle_documento`). `tools_called` reporta el nombre de la función y
ADL evalúa el diseño contra la card; una discrepancia es detectable.

### Lo que existe y lo que no

| | Estado |
|---|---|
| `buscar_corpus`, `detalle_documento` | ✅ implementadas (`src/tools/corpus.py`) |
| `delegar_documental`, `delegar_visualizacion`, `emitir_view_spec`, `componentes_disponibles`, `consultar_agregado` | ❌ solo en la card y en `stub.py` |
| Orquestador, documental, visualizador, analítico como agentes | ❌ no existen |
| `graph.py` | plantilla de **un** agente (`reason → tools → compose`), un modelo (`LLM_MODEL`) |

### Modelos disponibles (LiteLLM del evento)

Los ids que acepta el proxy no coinciden 1:1 con los nombres del PDF:

| Nombre en el PDF / card | Id en LiteLLM (el que va en el código) |
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
evaluador; gastarían la bolsa y contrarían las reglas de modelos). Las cuatro llamadas
útiles del proxy son `GET /v1/models`, `POST /v1/chat/completions`, `GET /key/info` y
`GET /health/liveliness`; el resto de su Swagger es administración.

⚠️ **Pregunta abierta para ADL:** qué nombre espera la card para calcular costo
(`llama-3.3-70b-instruct` del PDF o `meta.llama3-3-70b-instruct` del proxy).

---

## 7. Observabilidad (`src/observability/`)

Todo el estado por turno vive en `ContextVar` con objetos mutables, para que **dos
requests simultáneas no mezclen su evaluación** (ADL puede mandar preguntas en paralelo).

| Módulo | Qué registra |
|---|---|
| `turnlog.py` | tools llamadas, `retrieval_context`, `citations` (deduplicadas por `chunk_id`) |
| `usage.py` | tokens y llamadas, **con desglose por agente y modelo**; cuenta la llamada aunque el proveedor no devuelva cifras (los tokens quedan en 0, nunca inventados) |
| `tracing.py` | spans jerárquicos de la trayectoria (depuración) |

`registry.calls` (uso de depuración local) está acotado a 200 entradas: en un servidor de
24 horas, una lista sin tope es una fuga de memoria.

---

## 8. Recuperación (`src/retrieval/`)

- **Índice:** FAISS con 326.866 chunks (~1,3 GB en RAM). La metadata (344 MB de JSONL)
  **no se carga**: se indexan los offsets (2,6 MB) y cada fila se lee por `seek`.
  Bajó de 810 MB a 3 MB.
- **Encoder:** `bge-m3`, una sola instancia compartida entre búsqueda y caché (~2,3 GB en
  RAM). **Corre local: no gasta tokens del presupuesto**, que es la ventaja que `RETO.md`
  señala en el Bloque B.
- **Carga explícita, nunca implícita:** la primera carga descarga ~2 GB y tarda ~90 s. Se
  hace al arrancar (`lifespan` → `encoder.warmup()` en un hilo aparte) para que un
  evaluador nunca la pague como latencia. `/health` responde antes de que termine.
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
| `LLM_MODEL` | modelo del grafo actual (hoy uno solo para todo) | — |
| `VECTOR_INDEX_PATH` | ruta del índice dentro del contenedor | `data/encoder_bge_m3` |
| `AGENT_CARD_PATH` | ruta de la card | `agent_card.json` |
| `SESSION_TTL_S` | vida de la cookie de sesión | `3600` |
| `MAX_AGENT_ITERATIONS` | tope de iteraciones de todo bucle | `6` |
| `REQUEST_TIMEOUT_S` | timeout de llamadas al modelo | `60` |
| `LOG_LEVEL` | nivel de log | `INFO` |

> ⛔ **`ARPIA_MODE=live` antes de las 08:00 del sábado.** En `stub` el endpoint responde
> 200 con la forma perfecta y contenido inventado; `RETO.md` prohíbe datos simulados en
> lo desplegado. Se ve en `mode`, en `metadata.estado` y en `GET /health` (`degraded`
> permanente). Revisarlo antes de la entrega.

---

## 10. Despliegue

- **Un solo contenedor, tres dominios.** `agent.*`, `frontagent.*` y `dashboard.*` apuntan
  al mismo servicio; `routing.py` decide qué HTML servir en `/` según el `Host`
  (`dashboard.*` → tablero; cualquier otro → chat). No hay segundo servicio que pueda
  caerse durante la ventana de evaluación.
- **Coolify:** build pack `Dockerfile`, Base Directory `/arpia`, puerto `8000`, `www
  redirect` en *No redirect*. El `Dockerfile` hace `COPY . .` y **la frontera de qué entra
  la define `.dockerignore`**.
- **Healthcheck:** `/health` responde 503 solo si *nada* funciona; `degraded` sigue siendo
  un despliegue útil.
- **Persistencia del encoder:** `HF_HOME=/app/.cache/huggingface` debe ser un **volumen
  persistente**, o cada despliegue baja 2,2 GB otra vez.
- ⚠️ **El índice no está en la imagen.** `.dockerignore` excluye `data/`, `*.faiss` y
  `*.jsonl`. `docker-compose` lo resuelve con un volumen (`./data`), pero **Coolify no usa
  ese compose**: hace falta un *Storage* persistente con el índice, o meterlo en la imagen.
  **Decisión pendiente** (§12).
- **Ventana de evaluación:** el endpoint del Reto 1 **no se toca entre las 08:00 y las
  12:30**. Un redeploy ahí puede tumbar la evaluación.
- **Calentamiento:** en la prueba de escritorio, la primera llamada tardó ~19 s (arranque
  en frío) y las siguientes ~3 s. Conviene una llamada de calentamiento tras cada despliegue.

---

## 11. Cómo correrlo y probarlo

```bash
cd arpia
uv sync                                                    # el extra `retrieval` (faiss, torch) es pesado
cp .env.example .env                                       # y rellenar; ARPIA_MODE=stub por defecto
uv run uvicorn src.api.main:app --reload --port 8000

uv run ruff check src tests --fix && uv run ruff format src tests
uv run pytest tests -q                                     # 153 pruebas
```

153 casos en total (algunas funciones están parametrizadas; la columna cuenta funciones).

| Archivo de pruebas | Qué protege | Funciones |
|---|---|---|
| `test_contract.py` | contratos, alias, `ViewSpec` cerrado, validador de tokens | 27 |
| `test_chat.py` | formato ADL, sesión, `thread_id`, aislamiento entre requests simultáneas, degradación (con un `FakeGraph`, sin modelo) | 16 |
| `test_memory.py` | caché semántico: umbral, tope, cero falsos aciertos | 13 |
| `test_guardian.py` | ataques rechazados **y** consultas legítimas que no deben rechazarse | 11 |
| `test_enrich.py` | `organizacion` y `anio` derivados | 7 |
| `test_theme.py` | ningún color hexadecimal fuera de `src/theme/` | 6 |

### Prueba de escritorio con modelo real (previa a la integración en `main`)

`POST /chat` con `"Hola mundo"`, `ARPIA_MODE=live`, `gpt-oss-20b` vía LiteLLM: HTTP 200,
formato ADL completo, `tokens.total` = input + output (741), `num_interacciones=2`,
`X-Session-Id` devuelto. **No verificado aún:** recuperación real contra el índice (no
había `faiss` en el entorno local) y `tokens_por_agente` (el grafo actual no informa
agente ni modelo).

---

## 12. Pendientes y decisiones abiertas

Ordenados por impacto en la nota.

| # | Tema | Por qué importa |
|---|---|---|
| 1 | **Implementar los agentes reales** (orquestador, documental, visualizador, analítico) y que la card refleje solo lo que existe | La card declara 4 agentes y el código tiene 1. El Bloque D (Diseño, 20%) juzga la card contra la realidad; el Reto 2 (55% ejecución dinámica) depende del visualizador |
| 2 | **Modelo por agente** (`MODEL_ORQUESTADOR`, `MODEL_AGENTE_DOCUMENTAL`… con `LLM_MODEL` como respaldo) | Hoy un `LLM_MODEL` global; la card y el costo dependen del modelo por agente |
| 3 | Que el grafo pase `agent=` y `model=` a `usage.record_usage` | Sin eso, `tokens_por_agente` y `agentes_invocados` salen vacíos (el total sí es correcto) |
| 4 | Usar `guardian.envolver_documento` al meter contenido recuperado en el prompt | `RETO.md` §Defensa puntos 1 y 4; el vector de ataque más probable en un RAG |
| 5 | Índice y encoder en Coolify (Storage persistente o dentro de la imagen) | Sin índice, `/chat` cae siempre a `error_grafo` |
| 6 | Tono profesional/empático y regla de dominio en el prompt de sistema | El Tono vale el 25% del Bloque A |
| 7 | Saludos y preguntas fuera de tema: hoy el grafo responde "no hay evidencia" | Un enrutador o una regla lo resolvería |
| 8 | `GET /topics` y `GET /api/evidence/{chunk_id}` | El primero lo pide el frontend; el segundo, la trazabilidad del tablero |
| 9 | Memoria conversacional (checkpointer) | Ver los 3 problemas del grafo actual en `src/api/CONTRATO_GRAFO.md` |
| 10 | `static/chat.html` y `static/dashboard.html` | `routing.py` degrada a un aviso legible mientras no existan |
| 11 | Coste de un saludo: ~579 tokens de entrada (prompt de sistema + esquemas de tools) | Tokens pesa el 40% del Bloque B |
| 12 | Nombre de modelo en la card vs id de LiteLLM | Preguntar a ADL |
| 13 | **Endpoint de datos para el tablero**: dado un `ViewSpec`, devolver los datos agregados (conteos por fenómeno, organización, año…) con su `doc_id`/`chunk_id` | Sin él, el `view_spec` que emite el agente no tiene con qué dibujarse; es el backend de agregación que pide el Anexo B.6.4 |
| 14 | **Documento de arquitectura y propuesta de diseño por fenómeno**, dentro del repo y fuera de `docs/` (ignorado por git) | Entregable obligatorio: vale el Bloque D (20%) del Reto 1 y el 40% del Reto 2. `docs/architecture.md` está desactualizado |
| 15 | **Tope de tiempo por turno**: hoy cada llamada al modelo tiene timeout, pero un bucle de hasta 6 iteraciones puede sumar varios minutos | Un turno que excede el timeout del evaluador se pierde entero |

### Documentos del repo que están desactualizados

- `arpia-bundle/AGENTS.md` §7 dice "código bajo Apache 2.0 / repo público" y habla de un
  "gateway"; **`RETO.md` manda**: repositorio **privado**, modelos vía LiteLLM/Bedrock.
- `arpia/README.md`: la sección *Estado* (antes de esta actualización) decía "Reto no definido".
- `src/api/CONTRATO_GRAFO.md`: usa `agente_qa` en un ejemplo; los ids reales son los de
  `agent_card.json`.

---

## 13. Decisiones de diseño y su porqué

- **Alcance de la API.** El API no conoce nodos, prompts ni la memoria del grafo. La
  frontera está en [`src/api/CONTRATO_GRAFO.md`](src/api/CONTRATO_GRAFO.md). Quien trabaja
  en el grafo lee ese archivo; quien trabaja en el API no toca el grafo.
- **Contrato tolerante, respuesta estricta.** Se acepta casi cualquier entrada; se emite
  exactamente el formato de ADL.
- **200 con `estado`, nunca 500/422.** Una respuesta degradada y explicada puntúa; una
  excepción no.
- **Lo determinista primero.** Guardián y caché cuestan 0 tokens. La eficiencia se
  normaliza contra los demás equipos, así que todo turno que no llega al modelo es ventaja.
- **Honestidad de los datos.** Tokens en cero cuando no hubo llamada, no una estimación;
  `mode` y `estado="stub"` para que lo simulado sea inconfundible; vocabulario de
  `ViewSpec` recortado a lo que el corpus soporta.
- **Un contenedor, tres dominios.** Menos piezas que puedan caerse en la ventana de
  evaluación.

### Historia (para ubicar los commits)

| Commit | Qué trajo |
|---|---|
| `2a110ca` Fase 1 | contrato ADL completo, `/chat` en stub, agent card, enrutamiento por host |
| `4b3987e` | índice con metadata por `seek` (810 MB → 3 MB), `enrich.py`, `ViewSpec` podado |
| `faa21af` Fase 2 | guardián y caché semántico, deterministas y sin tokens |
| `cfb0aaf` | un solo servicio, caché persistente del encoder |
| `f17c7c0` | integración: `session.py`, `turnlog.py`, `usage` por agente, `CONTRATO_GRAFO.md` y su suite con `FakeGraph` |
