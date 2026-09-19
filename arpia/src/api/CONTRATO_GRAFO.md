# Contrato API ↔ grafo (Reto 1)

Frontera entre dos responsabilidades:

- **API** (`src/api/`): recibe la pregunta, resuelve la sesión y devuelve el JSON
  exacto de ADL (§2.4 de la especificación). Es lo que evalúa ADL.
- **Grafo** (`src/agents/`, `src/tools/`): decide cómo responder.

El API no conoce nodos, prompts ni memoria. Para llenar el JSON de ADL solo
necesita lo que sigue.

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
| `evaluacion.retrieval_context` | tools de recuperación | `turnlog.add_context([...])`; `search_corpus` ya lo hace |
| `metadata.tokens`, `num_interacciones` | grafo | `usage.record_usage(...)` en **cada** llamada al LLM |
| `metadata.tokens_por_agente`, `agentes_invocados` | grafo | igual, pasando `agent=` y `model=` |
| `metadata.latencia_ms`, `estado` | API | medido de principio a fin |

## Lo que el grafo debe cumplir

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

Si se activa la memoria, el grafo actual tiene tres problemas (verificados con un
LLM falso; no están corregidos aquí porque el grafo no es del API):

1. `reason` solo agrega la pregunta cuando `messages` está vacío: con memoria, el
   turno 2 nunca vería la pregunta nueva.
2. `turns` (y `queries`/`evidence`) usan `operator.add` y acumulan entre turnos: el
   tope de iteraciones se agotaría a los pocos mensajes.
3. El historial conserva los mensajes de herramientas de turnos anteriores: cada
   turno arrastra evidencia vieja, sube los tokens (Bloque B) y contamina el
   contexto que ADL mide en Faithfulness.

Solución probada: un nodo `begin` que agrega la pregunta y reinicia `turns`, y un
`compose` que al cerrar borra los mensajes de herramientas del turno
(`RemoveMessage`), dejando en el historial solo pregunta/respuesta. Además, recortar
el historial a las últimas N vueltas y limpiar mensajes huérfanos de un turno que
falló a medias. Un checkpointer `InMemorySaver` crece sin límite: necesita expiración
y tope de sesiones.

## Estados de `metadata.estado`

| Valor | Cuándo |
|---|---|
| `ok` | respuesta normal |
| `error_grafo` | el grafo lanzó una excepción; se responde con fragmentos recuperados |
| `error_llm_no_configurado` | faltan `LLM_BASE_URL`/`LLM_API_KEY` |
| `error_respuesta_vacia` | el grafo devolvió `answer` vacío |
| `error_entrada_invalida` | el cuerpo no traía una pregunta |

Ningún fallo interno se convierte en 500: siempre 200 con el código en `estado`.
