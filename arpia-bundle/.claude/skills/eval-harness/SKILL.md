---
name: eval-harness
description: Medir la calidad de recuperacion y del comportamiento agentico. Usar al comparar dos configuraciones, decidir si un componente nuevo mejora el sistema, o construir un conjunto de evaluacion.
---

# Evaluacion y ablacion

## Lo que DeepEval mide realmente
El evaluador del jurado no juzga solo la respuesta final: mide la
**trayectoria**. Eso significa, por request:

- Que tool se llamo, en que orden, con que argumentos.
- Cuantas iteraciones tomo el grafo antes de responder.
- Si el camino fue eficiente o dio vueltas innecesarias (una tool llamada
  dos veces con el mismo argumento, un bucle que llego al tope en vez de
  converger).
- Latencia y costo por request, no solo del sistema en agregado.

Esto es evaluacion **por componente y por paso**, no solo end-to-end. Un
sistema que responde bien pero con una trayectoria erratica puntua peor que
uno que responde igual de bien por el camino directo.

## De donde sale la trayectoria
El endpoint `/analyze` expone la trayectoria en el campo `trace`
(`src/api/main.py`): un `trace_id` de correlacion y una lista de spans
jerarquicos (`span_id`, `parent_id`, `type` — `llm` / `tool` / `retrieval` —,
`name`, `input`, `output`, `start_ms`, `end_ms`), producida por
`src/observability/tracing.py`.

Esta es la estructura que un evaluador de trayectoria consume. Si anades un
nodo nuevo al grafo o una tool nueva, verifica que quede envuelto en un span
(`ToolRegistry.register` ya lo hace automaticamente; para llamadas al LLM
fuera de una tool, envolver explicitamente con `tracing.span("llm", ...)`,
como en `src/agents/graph.py`).

No instales `deepeval` en el runtime de produccion: la evaluacion consume
la traza desde afuera, vía el endpoint HTTP. Ver la frontera mas abajo.

## Protocolo de ablacion
Una variable por experimento. Mismo conjunto de referencia. Registra
configuracion, metrica y delta **antes** de aceptar un cambio. Si el delta esta
dentro del ruido, **descarta**: cada componente extra es superficie de fallo.

Esta disciplina es la que permite justificar ante un jurado por que el sistema
tiene los componentes que tiene, y por que *no* tiene otros.

## Golden set — no construido todavia
No hay corpus ni reto definidos todavia (`CLAUDE.md`), asi que **no existe
un golden set en este repo**. No asumas uno ya construido ni built lo antes
de que el reto se publique — construirlo ahora es apostar a una hipotesis
sobre datos que todavia no existen.

Cuando el reto se conozca, un golden set es un conjunto pequeno de casos
(consulta, documentos esperados, respuesta esperada, y — dado que DeepEval
mide trayectoria — la secuencia de tools esperada) revisados a mano. Empieza
con 5-10; crece cuando aparezcan casos no contemplados. Deriva de casos
reales del corpus del reto, no de metricas genericas.

**Frontera**: el runtime de produccion nunca debe importar el modulo de
evaluacion ni el golden set. Verificalo con una prueba que importe el
pipeline en un proceso limpio y compruebe que modulos quedaron cargados.

## Metricas por capa

**Recuperacion**
- *Recall de contexto*: de lo relevante, cuanto se recupero.
- *Precision de contexto*: de lo recuperado, cuanto era relevante.
- *Hit rate@k*: si al menos un documento relevante aparece en el top-k.

**Generacion**
- *Fidelidad*: la respuesta se sostiene en la evidencia recuperada.
- *Relevancia*: responde lo que se pregunto.
- Evaluables con LLM-as-judge, calibrado contra ejemplos etiquetados a mano.
  Vigila sus sesgos: posicion, verbosidad y auto-preferencia.

**Trayectoria del agente** (lo que DeepEval anade sobre "solo la respuesta")
- ¿Llamo la tool correcta, con argumentos validos?
- ¿El camino fue el necesario, o hubo llamadas redundantes / bucles que
  llegaron al tope de iteraciones (`AGENTS.md` §8) en vez de converger?
- Numero de spans por tipo (`llm` / `tool` / `retrieval`) como proxy barato
  de "cuanto trabajo hizo el agente para llegar a la respuesta".
- Latencia y costo (`tokens_used`, `elapsed_ms` en la respuesta de
  `/analyze`): un sistema correcto que tarda de mas o gasta de mas no es una
  solucion viable.

## Honestidad metodologica
Declara el tamano y el sesgo de tu conjunto de evaluacion. Un devset de 8
consultas sirve para separar alternativas con diferencias grandes; no autoriza
a afirmar significancia estadistica ni a afinar diferencias pequenas. Decirlo
explicitamente vale mas ante un jurado tecnico que presentar numeros como
definitivos.

## Herramientas
`ragas` para metricas de RAG. `deepeval` para trayectoria y evaluacion por
componente, consumiendo el `trace` de `/analyze` como entrada. Ambas
Apache-2.0/MIT: verificar antes de anadir.
