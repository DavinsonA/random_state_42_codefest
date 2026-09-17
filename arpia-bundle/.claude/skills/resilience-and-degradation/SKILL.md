---
name: resilience-and-degradation
description: Timeouts, reintentos y fallback por capa. Usar al integrar un servicio externo (gateway, indice, API de terceros), al decidir que devuelve un endpoint cuando algo falla, o cuando un fallo en un componente tumba mas de lo que deberia.
---

# Resiliencia y degradacion

## La regla central
**Ningun componente propaga una excepcion sin capturar al siguiente.** Cada
capa decide que hacer con su propio fallo — reintentar, degradar, reportar —
pero nunca deja que la excepcion cruda suba y tumbe al que lo llama.

Esto ya es explicito para tools (`AGENTS.md` §9, `tool-integration`) y para
la API (`endpoint-contract`). Esta skill cubre el patron general y donde
mas se olvida: el gateway del LLM y el indice vectorial.

## Timeouts explicitos, siempre
Sin timeout, un servicio lento no falla — cuelga, y cuelga todo lo que
depende de el (el grafo, el endpoint, el proceso entero bajo carga).

- Llamadas HTTP a servicios externos: `httpx` con `timeout=` explicito.
  Nunca el default implicito.
- Chequeos de disponibilidad (`/health`): timeout corto a proposito (2s).
  Un health check no debe tardar mas que el propio sintoma que reporta.
- El gateway del LLM: `request_timeout_s` en `src/config.py`, ya
  centralizado — no hardcodear otro valor en un cliente nuevo.

## Reintentos con limite
Un reintento sin tope es un bucle disfrazado, y el dashboard de LiteLLM lo
va a registrar como consumo real aunque el equipo no lo haya "programado a
proposito". Antes de anadir un reintento:

1. Define el tope como constante nombrada, no como numero suelto en medio
   del codigo.
2. Reintenta solo errores transitorios (timeout, 429, 5xx). Un 400 o un
   error de validacion no se arregla reintentando igual.
3. Backoff simple (ni siquiera exponencial hace falta para este volumen) si
   el reintento es contra el gateway compartido del evento — un reintento
   inmediato en bucle rapido puede agravar un problema de capacidad
   compartida entre equipos.

## Fallback por capa
Cuando un componente falla, la capa que lo envuelve decide el siguiente
peldano, no el mas bajo posible de golpe:

```
grafo agentico completo
  -> falla el LLM o se agota el presupuesto de iteraciones
  -> recuperacion pura (sin LLM, solo el indice)
    -> falla tambien el indice
    -> respuesta vacia + warnings explicando ambos fallos, HTTP 200
```

Cada peldano se prueba antes de rendirse al siguiente. Ver la implementacion
de referencia en `analyze()` en `src/api/main.py`.

## El criterio de estado en `/health`
Tres niveles, nunca solo dos:

- `"ok"` — todo lo requerido por el modo activo funciona.
- `"degraded"` — el servicio responde y es parcialmente util, pero algo
  fallo (indice caido, gateway inalcanzable). HTTP 200.
- `"down"` — nada funciona. Solo aqui HTTP 503.

Un jurado o un pipeline de monitoreo que recibe 503 no puede distinguir
"el proceso no arranco" de "arranco pero esta degradado". La distincion
importa: lo segundo puede seguir puntuando, lo primero no.

## Que NO hacer
- No envolver una excepcion en un `try/except` vacio que la descarta sin
  registrar nada — usa el logger de `src/config.py` antes de continuar.
- No convertir cualquier fallo en HTTP 500 "porque es mas simple". El costo
  de ese atajo lo paga la evaluacion automatica, no quien escribe el codigo.
- No reintentar contra el gateway sin tope pensando que "en produccion casi
  nunca falla": el evento mide justamente ese caso.
