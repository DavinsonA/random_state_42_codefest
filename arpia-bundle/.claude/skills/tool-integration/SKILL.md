---
name: tool-integration
description: Crear tools para el agente e integrar APIs o fuentes externas. Usar al anadir una capacidad nueva al agente, envolver un servicio externo, o cuando el agente no invoca una tool que deberia usar.
---

# Tools e integracion de APIs

## El docstring ES el prompt
El modelo decide si invoca una tool leyendo su nombre, firma tipada y
docstring. Un docstring de una linea produce un agente erratico. **Mejorar el
docstring rinde mas que cambiar de modelo.**

Estructura obligatoria (ver `src/tools/corpus.py` como referencia):

```python
@registry.register
def nombre_tool(arg: str, k: int = 8) -> str:
    """Una linea: que hace.

    Usar cuando <condiciones concretas>.

    NO usar para <casos concretos>. Para <caso limite>, hacer <alternativa>.

    Args:
        arg: que es, en que formato, con que restriccion.
        k: que controla y cuando conviene cambiarlo del valor por defecto.

    Returns:
        Que devuelve y que pasa si no hay resultados.
    """
```

## Reglas
1. **Una tool nunca lanza excepcion hacia el grafo.** El decorador
   `@registry.register` captura y devuelve texto de error legible para que el
   agente decida que hacer.
2. **Devuelve texto o dicts serializables**, nunca objetos arbitrarios.
3. **Clasifica por riesgo**: lectura libre; escritura acotada a su espacio;
   accion irreversible con confirmacion humana.
4. **Minimo privilegio** en credenciales de servicios externos.

## MCP: cuando SI y cuando NO
MCP anade una capa de orquestacion entre agente y tools. Vale la pena si varios
agentes comparten muchas tools, o si el control de permisos debe centralizarse.
**No vale la pena** si es un agente con pocas tools: anade latencia y una
dependencia mas. Una funcion de Python simple no necesita envolverse en MCP.

## Integracion de APIs externas
- `httpx` con `timeout` explicito. Sin timeout, un servicio lento cuelga el grafo.
- Cachea respuestas de APIs con rate limit.
- Credenciales por variable de entorno, jamas en codigo.
- Ante fallo del servicio, devuelve un mensaje util: el agente puede recurrir a
  otra fuente si sabe que esta fallo.
