# Contrato API ↔ grafo (Reto 1)

Frontera entre dos responsabilidades:

- **API** (`src/api/`): recibe la pregunta, resuelve la sesión y devuelve el JSON
  exacto de ADL (§2.4 de la especificación). Es lo que evalúa ADL.
- **Grafo** (`src/agents/`, `src/tools/`): decide cómo responder.

El API no conoce nodos, prompts ni memoria. Para llenar el JSON de ADL solo
necesita lo que sigue.

## Orden del turno

El API ejecuta cinco pasos y el grafo es solo el tercero:

```
guardian.revisar_entrada  ->  memoria.buscar  ->  GRAFO  ->  guardian.revisar_salida  ->  memoria.guardar
   (0 tokens, veto)          (0 tokens, atajo)                (0 tokens, veto)
```

Consecuencias para quien trabaja en el grafo:

- El grafo **nunca ve** una consulta que el guardian rechazó, ni una que el
  caché resolvió. No hace falta defenderse otra vez de la inyección en el
  prompt de sistema — conviene, pero la primera barrera ya pasó.
- El texto que llega está **saneado**: normalizado NFKC, sin caracteres
  invisibles y recortado a 4000 caracteres.
- Todo documento recuperado debe entrar al prompt con
  `guardian.envolver_documento(texto, chunk_id)`. El corpus es de fuentes
  externas y un documento puede traer instrucciones escritas para un modelo.

## Qué llama el API

```python
graph = build_graph()  # sin argumentos, una vez
result = graph.invoke(
    {"question": texto},
    config={"configurable": {"thread_id": sesion_id}},  # sesión de la conversación
)
respuesta = result["answer"]  # obligatorio, texto
```

## De dónde sale cada campo del JSON de ADL

| Campo de ADL | Quién lo produce | Cómo |
|---|---|---|
| `respuesta`, `evaluacion.actual_output` | grafo | `result["answer"]` |
| `evaluacion.input` | API | el texto recibido |
| `evaluacion.tools_called` | tools | `@registry.register` lo anota solo (`observability/turnlog.py`) |
| `evaluacion.retrieval_context` | tools de recuperación | `turnlog.add_context([...])`; `buscar_corpus` ya lo hace |
| `metadata.tokens`, `num_interacciones` | grafo | `usage.record_usage(...)` en **cada** llamada al LLM |
| `metadata.tokens_por_agente`, `agentes_invocados` | grafo | igual, pasando `agent=` y `model=` |
| `metadata.latencia_ms`, `estado` | API | medido de principio a fin |
| `citations` | tools de recuperación | `turnlog.add_citations([...])`; `buscar_corpus` ya lo hace |
| `view_spec` | agente visualizador | `ViewSpec` validado contra esquema cerrado (`contracts.py`) |
| `mode` | API | `stub` o `live`, para que una demo simulada no pase por real |

## Lo que el grafo debe cumplir

0. **Los nombres de las tools coinciden con `agent_card.json`** (`buscar_corpus`,
   `detalle_documento`, `emitir_view_spec`, ...). ADL evalúa el bloque de diseño
   contra la card, y `tools_called` reporta el nombre de la función.
1. **Anotar cada llamada al LLM** con agente y modelo:
   `usage.record_usage(response.usage_metadata, agent="agente_qa", model=<modelo>)`.
   Sin `agent=`/`model=` el total de tokens sale bien, pero `tokens_por_agente` y
   `agentes_invocados` quedan vacíos (ADL los usa en el Bloque B y para calcular
   el costo). Los ids de agente deben coincidir con los de la agent card.
2. **`tokens.total` cubre todos los agentes**, no solo el orquestador (requisito
   obligatorio de ADL). Se cumple solo si *todas* las llamadas pasan por `record_usage`.
3. **Tools con `@registry.register`**, y devolviendo texto de error en vez de lanzar.
4. **Sin estado global entre requests.** ADL puede mandar preguntas en paralelo;
   el registro por turno usa `contextvars` (ver `turnlog.py`, `usage.py`).
5. **Tope de iteraciones** en todo bucle (AGENTS.md §8). Cada llamada cuenta en el
   Bloque B (eficiencia).

## Memoria de sesión

El API pasa `sesion_id` como `thread_id`. Si el grafo compila con un checkpointer,
recuerda la conversación; si no, cada pregunta es independiente y no pasa nada.

**Ya está activada y resuelta** (Fase 3). El nodo `begin` de `src/agents/graph.py`
abre cada turno haciendo tres cosas, y cada una cierra un fallo que sí se midió
con memoria encendida:

1. Agrega la pregunta **siempre**, no solo cuando el historial está vacío: si no,
   el turno 2 nunca vería la pregunta nueva.
2. Reinicia los campos del turno (`TURNO_LIMPIO` en `state.py`): si no, la
   evidencia del turno 1 se cita en el turno 5 como si fuera de esta pregunta.
3. Borra del historial los mensajes de herramientas de turnos anteriores
   (`RemoveMessage`) y recorta la ventana a `VENTANA_TURNOS`: arrastrarlos sube
   los tokens de cada turno (Bloque B) y contamina el `retrieval_context` que ADL
   mide en Faithfulness.

La persistencia vive en `src/agents/checkpoint.py`: SQLite en `state/`, no
`InMemorySaver`, precisamente porque el de memoria crece sin límite durante las
24 horas del evento y se pierde en cada redespliegue. Si la ruta no es escribible
se cae a memoria y lo avisa; `/health` lo reporta en `memoria_persistente`.

Lo que un agente recibe de la conversación previa no es el historial crudo:
`memory.conversacion_previa` arma las últimas vueltas, recortadas, sin mensajes
de herramientas y sin la pregunta actual. En el primer turno de una sesión eso
cuesta **cero tokens extra**.

## Estados de `metadata.estado`

| Valor | Cuándo |
|---|---|
| `ok` | respuesta normal |
| `error_grafo` | el grafo lanzó una excepción; se responde con fragmentos recuperados |
| `error_llm_no_configurado` | faltan `LLM_BASE_URL`/`LLM_API_KEY` |
| `error_respuesta_vacia` | el grafo devolvió `answer` vacío |
| `error_entrada_invalida` | el cuerpo no traía una pregunta |
| `stub` | `ARPIA_MODE=stub`: la respuesta es simulada |
| `cache:<similitud>` | la resolvió el caché semántico, sin llamar al modelo |
| `rechazado:inyeccion` | el guardián detectó un intento de inyección |
| `rechazado:fuera_de_dominio` | petición ajena a los tres fenómenos |
| `rechazado:salida_bloqueada` | la respuesta filtraba configuración |

Ningún fallo interno se convierte en 500: siempre 200 con el código en `estado`.
