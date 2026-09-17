---
name: langgraph-flows
description: Disenar, extender y depurar grafos agenticos con LangGraph. Usar al anadir un nodo, una arista condicional, memoria o persistencia; al decidir entre workflow determinista y agente; o cuando un grafo no termina o cicla.
---

# Flujos agenticos con LangGraph

## Decision previa (hazla antes de escribir codigo)
| Situacion | Solucion |
|---|---|
| Los pasos se conocen de antemano | workflow determinista, **sin agente** |
| Subtareas independientes | paralelizar, no necesariamente con agentes |
| El sistema debe decidir el siguiente paso | agente |
| Hay una accion irreversible | agente + confirmacion humana |

Cada llamada adicional al modelo cuesta tokens, latencia y una superficie mas
de error. Un agente bien equipado supera a tres coordinandose mal.

## Empieza por lo minimo
`create_react_agent(model, tools, prompt)` cubre la mayoria de los casos.
Baja al grafo explicito solo cuando necesites pasos fijos antes/despues del
bucle, ramas condicionales reales o un nodo de redaccion separado.

## Anatomia (ver `src/agents/graph.py`)
- **Estado** (`state.py`): `TypedDict` con reductores. Si un campo no lo lee
  ningun nodo ni arista, no pertenece al estado.
- **Nodos**: funcion que recibe el estado y devuelve una actualizacion
  **parcial**, nunca el diccionario completo.
- **Arista condicional**: aqui vive el diseno real del agente.
- **Arista de retorno** `tools -> reason`: es lo que lo convierte en agente y
  no en pipeline.

## Reglas duras
1. **Tope de iteraciones siempre.** Un agente que no encuentra lo que busca
   reintenta indefinidamente sin lanzar ningun error: solo consume presupuesto.
   El corte va en la arista condicional, no confiado al modelo.
2. **Nodo de redaccion separado y sin tools.** Mezclar "buscar" y "redactar"
   en un solo prompt degrada el texto final.
3. **Reductores**: `add_messages` para el historial (concatena y deduplica),
   `operator.add` para listas acumulativas.

## Persistencia y pausa
- Checkpointers: `InMemorySaver` (pruebas), `SqliteSaver` (evento),
  `PostgresSaver` (produccion).
- `interrupt()` detiene el grafo en el nodo y devuelve el control; se reanuda
  con `Command(resume=...)`. Usar en toda accion sin vuelta atras.

## Depuracion
```bash
uv run python scripts/run_node.py --graph --input "..." --json
```
Lee la **traza completa**, no solo la respuesta. Si las consultas a tools son
malas (cortas, repetidas, fuera de tema), el problema casi nunca es el modelo:
es el docstring de la tool o el prompt de sistema.
