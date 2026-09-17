---
name: agent-tracing
description: Instrumentar observabilidad y depurar el comportamiento de agentes. Usar cuando un agente responde mal sin lanzar error, cuando hay que medir latencia o consumo de tokens, o al anadir trazabilidad a un flujo nuevo.
---

# Trazabilidad y depuracion de agentes

## Principio
Un sistema que no puedes observar no lo puedes corregir. Los fallos agenticos
rara vez lanzan excepciones: el agente responde algo plausible por el camino
equivocado. **Lee la traza completa, no solo la respuesta final.**

## Lo minimo, ya incluido
`src/tools/registry.py` registra cada invocacion con nombre, argumentos,
duracion y exito:
```bash
uv run python scripts/run_node.py --graph --input "..." --json
```

## ID de correlacion
Propaga un identificador unico por ejecucion a cada llamada de modelo, cada
tool y cada recuperacion. Es la base de toda la observabilidad: sin el no
puedes reconstruir que paso cuando hay ramas en paralelo.

## Langfuse (si se instrumenta)
Open source, autohospedable via Docker Compose, agnostico al framework
(funciona con LangGraph, CrewAI, ADK). Se integra con decoradores en Python.
Instrumentarlo cuesta poco y se paga solo en cuanto hay mas de un agente.

Alternativa: LangSmith. **Aviso de privacidad**: sus trazas incluyen el
contexto y las respuestas completas del agente. Evaluar antes de usarlo con
datos sensibles.

## Que medir
- **Latencia por paso**, no solo total: localiza el cuello de botella.
- **Tokens y costo por llamada**: el presupuesto del evento es finito.
- **Numero de iteraciones**: si el agente itera de mas, el problema esta en el
  docstring de una tool o en el prompt de sistema, casi nunca en el modelo.
- **Que tool se llamo y con que argumentos**: revela si el agente entendio mal
  la herramienta.

## Diagnostico por sintoma
| Sintoma | Donde mirar primero |
|---|---|
| Respuesta plausible pero incorrecta | consultas que lanzo a las tools |
| Agente no termina | tope de iteraciones en la arista condicional |
| Consumo de tokens alto | bucle reintentando; revisa la traza |
| No invoca la tool correcta | docstring de la tool: ampliar "cuando usar / cuando no" |
