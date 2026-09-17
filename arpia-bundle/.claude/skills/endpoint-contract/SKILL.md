---
name: endpoint-contract
description: Disenar y cambiar el contrato HTTP que consume el jurado. Usar al anadir o modificar un endpoint de src/api/, al cambiar un esquema Pydantic de respuesta, o antes de desplegar un cambio que toque /analyze, /retrieve, /health o /usage.
---

# Contrato del endpoint

## Por que esto importa mas que el resto del codigo
El jurado no evalua el repositorio. Un pipeline automatizado (DeepEval)
consume la aplicacion desplegada en Coolify a traves de su endpoint HTTP. Si
el contrato no coincide con lo que el evaluador espera, o si el servicio no
responde, la solucion vale cero — sin importar que tan bueno sea el agente
por dentro.

## Esquemas aislados en un solo modulo
Todos los `BaseModel` que forman el contrato publico viven en
`src/api/main.py`, en la seccion `# -- contrato --`. No los repartas por
otros modulos: un evaluador (o un companero de equipo bajo presion de
tiempo) debe poder ver el contrato completo sin saltar de archivo en
archivo.

Los modelos de dominio interno (p.ej. `Hit` en `src/retrieval/index.py`)
son libres de cambiar de forma; los del contrato, no sin versionar.

## Versionado
Este repo no versiona la URL (`/v1/analyze`) porque el contrato lo fija el
handbook del reto, no el equipo. En su lugar:

- El campo `mode` en cada respuesta (`stub` | `live`) evita que una demo
  simulada se confunda con una real.
- Si el contrato cambia DESPUES de desplegado (por una aclaracion tardia del
  reto), documenta el cambio en el mensaje de commit con el texto exacto de
  la aclaracion citada, no solo "ajuste de esquema".

## Campos de degradacion y advertencias
Todo endpoint que pueda fallar parcialmente expone su estado, en vez de
elegir entre "todo bien" o "error":

- `warnings: list[str]` — que se degrado y por que, en texto legible.
- `mode` — bajo que modo se genero la respuesta.
- Para `/health`: `status` en `"ok" | "degraded" | "down"`, nunca solo
  boolean. Ver `resilience-and-degradation` para el criterio completo.

Una respuesta 200 con `warnings` puntua mejor en una evaluacion automatica
que un 500: DeepEval puede leer y calificar una degradacion explicada, no
puede calificar una excepcion.

## Que NO cambiar una vez desplegado
Una vez que el jurado empieza a apuntar al endpoint desplegado:

- **No renombres un campo existente.** Anade uno nuevo y, si hace falta,
  deja el viejo con el mismo valor un tiempo.
- **No cambies el tipo de un campo** (`str` -> `int`, `list` -> `dict`). Un
  evaluador con esquema fijo rompe en el primer parseo.
- **No agregues un campo obligatorio nuevo** a un modelo de *request*: eso
  rompe toda llamada existente del evaluador. Los campos nuevos de request
  llevan default.
- **No cambies el codigo HTTP de exito** de un endpoint ya usado (p.ej. de
  200 a 201).
- Si de verdad hace falta un cambio incompatible, es una decision de equipo
  explicita, no un ajuste de paso — y se hace ANTES de que el pipeline de
  evaluacion empiece a correr, idealmente durante el feature freeze de las
  20h (ver `CLAUDE.md`).

## Al conocer el reto
Ajusta unicamente `AnalyzeRequest` / `AnalyzeResponse` (o los modelos que el
handbook indique) para que coincidan EXACTAMENTE con el contrato publicado.
No toques `/health`, `/usage` ni la estructura de `trace` salvo que el
handbook lo pida explicitamente: esos son contrato de operacion, no del
reto.
