---
name: structured-extraction
description: Extraccion a esquema Pydantic desde texto. Usar al disenar un modelo de extraccion, al conectar la salida de un LLM a un esquema tipado, o cuando la extraccion alucina campos que el texto no respalda.
---

# Extraccion estructurada

## Campos opcionales, no obligatorios
Un modelo que exige un campo lo va a rellenar con algo, exista o no en el
texto. Eso es alucinacion inducida por el esquema, no por el modelo.

- Todo campo que no sea el identificador minimo del registro debe ser
  `Optional` (o `= None`) en el `BaseModel` de extraccion.
- Si un campo falta en el texto, el valor es `None`, nunca un placeholder
  (`"desconocido"`, `""`, `0`) que se confunda despues con un dato real.
- Reserva campos obligatorios para lo que el pipeline no puede funcionar sin
  (p.ej. un `doc_id` que ya viene del corpus, no del LLM).

## Reporte de cobertura
Cada extraccion debe poder responder "de los N campos del esquema, cuantos
se llenaron para este documento". Sin esto no hay forma de distinguir un
documento pobre en datos de una extraccion que fallo en silencio.

```python
def coverage(record: BaseModel) -> float:
    values = record.model_dump()
    filled = sum(1 for v in values.values() if v not in (None, "", []))
    return filled / len(values)
```

Agrega la cobertura agregada al log de la corrida, no solo por documento:
una caida sistematica de cobertura entre corridas es la senal mas temprana
de que algo se rompio (formato de fuente cambio, prompt se degrado, etc).

## Fecha del documento vs. fecha del evento
Error frecuente: tratar como una sola fecha lo que son dos cosas distintas.

- **Fecha del documento**: cuando se publico/emitio la fuente.
- **Fecha del evento**: cuando ocurrio lo que el documento describe.

Un reporte de enero puede describir un evento de octubre. Colapsarlas en un
solo campo `fecha` produce lineas de tiempo incorrectas en cualquier
visualizacion temporal aguas abajo. Modela ambas explicitamente:

```python
class Extraccion(BaseModel):
    fecha_documento: str | None = None  # cuando se publico la fuente
    fecha_evento: str | None = None     # cuando ocurrio lo descrito
```

Ver tambien `geo-temporal-enrichment` para la normalizacion de estas fechas
a un formato consistente.

## Validacion y reintento ante fallo de esquema
Un LLM que devuelve JSON casi-valido (comillas mal cerradas, un campo con
tipo incorrecto) no es un fallo total: es una oportunidad de un reintento
acotado.

1. Parsear con el `BaseModel`. Si `ValidationError`, reintentar UNA vez con
   el error de validacion insertado en el prompt ("el campo X debia ser
   entero, recibiste texto").
2. Si el segundo intento tambien falla, no lo descartes en silencio:
   registra el documento como `extraccion_fallida` con el texto crudo, para
   poder revisarlo despues. Nunca dejes caer datos sin dejar rastro.
3. Tope de reintentos: 1. Esto es extraccion, no un bucle agentico, pero la
   misma regla de AGENTS.md §8 aplica — ningun bucle sin tope.

## Que NO hacer
- No inventar un valor "razonable" para un campo faltante. Es preferible
  `None` a un dato que parece real y no lo es.
- No usar el mismo modelo Pydantic para extraccion y para el contrato de
  `/analyze`. Son responsabilidades distintas: ver `endpoint-contract`.
