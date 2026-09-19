# A.R.P.I.A. — Documento de arquitectura

> **A**sistente de **R**ecuperación y **P**roducción de **I**nteligencia **A**nalítica.
> Sistema multi-agente para análisis aumentado sobre el corpus documental de los tres
> fenómenos del CODEFEST AD ASTRA 2026, equipo `random_state = 42`.
>
> Este documento responde a lo que evalúa el Bloque D del Reto 1 —número y rol de los
> agentes, esquema de orquestación, herramientas, y qué tan pertinente resulta ese diseño—
> y a la **propuesta de diseño por fenómeno** del Reto 2 (§7), que se evalúa desde aquí y
> no solo desde el tablero.

---

## 1. Qué hace el sistema, y qué deliberadamente no hace

A.R.P.I.A. responde preguntas en lenguaje natural sobre 326.866 fragmentos de 1.826
documentos, y decide qué visualización del tablero activar a partir de la instrucción del
usuario. Cada afirmación que emite viene con su procedencia hasta el `doc_id` y el
`chunk_id`.

**Lo que no hace, por decisión explícita:**

- **No pronostica ni asigna probabilidades.** No usa la escala estimativa de ICD 203
  ("muy probable, 80-95 %") ni califica fuentes con códigos tipo Admiralty. Asignar esas
  etiquetas sería fabricar una medición que nadie hizo, y `RETO.md` prohíbe presentar
  índices o niveles calculados ad-hoc como medición objetiva. La incertidumbre se expresa
  diciendo qué dice el corpus y qué no dice.
- **No inventa geografía.** El corpus no tiene ubicación (§6.2).
- **No ejecuta código que venga de un modelo.** El agente visualizador emite un `ViewSpec`
  validado contra un esquema cerrado, nunca SQL ni Python (§5.3).

Esa lista no es modestia: cada punto es una decisión de diseño que cierra una vía de fallo
concreta, y las tres aparecen medidas más abajo.

---

## 2. Los siete agentes

La Especificación exige tres como mínimo —orquestador, preguntas, visualizaciones— y suma
puntos por agentes adicionales **solo si contribuyen al análisis aumentado**. Un agente
decorativo no suma y sí consume tokens, que se califican. Estos son los siete y lo que
justifica a cada uno:

| Agente | Modelo | Coste | Qué aporta |
|---|---|---|---|
| **Orquestador** | `gpt-oss-120b` | 1 llamada | Decide a quién delegar. Necesita criterio, por eso el modelo grande |
| **Documental** | `llama-3.3-70b-instruct` | 1 llamada | Redacta el análisis sobre la evidencia recuperada |
| **Visualizador** | `gpt-oss-20b` | 1 llamada | Emite el `ViewSpec`. El modelo grande no compra nada: la salida es JSON dentro de un vocabulario cerrado, no prosa |
| **Analítico** | — | **0 tokens** | Responde conteos y distribuciones sobre metadata agregada, sin pasar por un modelo |
| **Guardián** | — | **0 tokens** | Filtro determinista de entrada y salida contra inyección de prompt |
| **Memoria** | — | **0 tokens** | Caché semántico y ventana conversacional |
| **Verificador** | `llama-3.3-70b-instruct` | 0, salvo corrección | Comprueba que lo redactado se sostiene en la evidencia; solo gasta si corrige |

**Cuatro de los siete cuestan cero tokens.** Eso no es un detalle de implementación: el
Bloque B del Reto 1 normaliza la eficiencia *contra los otros equipos* y mide tokens,
interacciones y latencia. Un agente que responde "¿cuántos documentos hay por fenómeno?"
consultando una tabla en memoria, en lugar de preguntárselo a un modelo, es una respuesta
más exacta *y* más barata que la de un sistema que lo resuelve con RAG.

---

## 3. Orquestación: un plan único, no un bucle ReAct

```
  consulta
     │
     ▼
  ┌─────────────┐   rechaza ataques y peticiones fuera de dominio
  │  Guardián   │   CERO tokens: un ataque no debe llegar ni al caché ni al modelo
  └──────┬──────┘
         ▼
  ┌─────────────┐   un acierto ahorra el turno entero
  │  Memoria    │
  └──────┬──────┘
         ▼
  ┌─────────────┐   UNA llamada -> Plan validado (esquema cerrado)
  │ Orquestador │
  └──────┬──────┘
         ▼
  ┌──────────────────────────────────────┐
  │  Ejecución (en paralelo si procede)  │
  │  ┌────────────┐ ┌───────────┐ ┌────┐ │
  │  │ Documental │ │Visualizad.│ │Anal│ │
  │  └─────┬──────┘ └─────┬─────┘ └─┬──┘ │
  │        │ FAISS +      │ ViewSpec│ tabla
  │        │ encoder      │ cerrado │ agregada
  │        │ (0 tokens)   │         │ (0 tokens)
  └────────┼──────────────┼─────────┼────┘
           ▼              ▼         ▼
  ┌─────────────┐   una sola replanificación, si no hubo evidencia
  │ Verificador │
  └──────┬──────┘
         ▼
  ┌─────────────┐   última barrera: ni secretos ni estructura interna
  │  Guardián   │
  └──────┬──────┘
         ▼
     respuesta JSON (§2.4 de la Especificación)
```

### 3.1 Por qué no ReAct

El bucle razonar–herramienta–observar hace un número **impredecible** de llamadas por
pregunta: entre tres y siete, sin cota útil. Un coste que no se puede acotar es un riesgo
que no se puede presupuestar, y aquí hay dos presupuestos reales: los 100 USD del equipo y
el Bloque B, que penaliza cada interacción de más frente a los demás equipos.

El plan único fija el coste por construcción:

```
pregunta documental      2 llamadas   (plan + redacción)
pregunta cuantitativa    1 llamada    (plan; el analítico no gasta)
pregunta con vista       3 llamadas   (plan + redacción + view_spec)
sin evidencia           +1 llamada    (una replanificación, y solo una)
```

Medido en producción: una pregunta documental real resolvió en **2 interacciones y 4.470
tokens**, con 8 fragmentos de contexto y 8 citas.

### 3.2 El plan es un contrato, no una sugerencia

El orquestador no devuelve texto que alguien luego interpreta: devuelve un `Plan` validado
contra un esquema cerrado (`extra="forbid"`, agentes como `Literal`). Lo que no encaje no
se ejecuta. Esa es la diferencia entre delegar y conversar con las herramientas.

Dos topes lo acotan: `MAX_PASOS = 3` —sin él, un modelo entusiasta convierte una pregunta
en ocho delegaciones— y `MAX_REPLANES = 1`. Si tras la segunda pasada sigue sin haber
evidencia, la respuesta honesta es decir que no la hay.

**Cuando el plan falla, el sistema degrada, no se cae.** Si el gateway no responde o el
modelo emite algo que no valida, entra un plan de respaldo determinista que cuesta cero
tokens. Y si el fallo es de la redacción, se entregan los fragmentos recuperados con su
procedencia: una disculpa genérica puntúa cero en relevancia, unos fragmentos con fuente
son evidencia real aunque no estén redactados.

---

## 4. Recuperación: la asimetría que define el sistema

La recuperación **no cuesta tokens**. FAISS y el encoder `bge-m3` corren en la CPU del
contenedor: 326.866 vectores de 1024 dimensiones, índice `IndexFlatIP`, metadata leída por
`seek` sobre disco para no cargar 360 MB en memoria.

Esa asimetría es la ventaja competitiva frente a equipos que resuelven la recuperación
pasando el corpus por un modelo: lo que ellos pagan en tokens de entrada, aquí es tiempo de
CPU. Y el Bloque B se normaliza contra ellos.

El agente analítico lleva la misma idea al extremo: los conteos y distribuciones salen de
una tabla agregada en memoria, construida una vez al arrancar. Preguntarle a un modelo
"¿cuántos documentos hay por organización?" costaría tokens **y** daría una cifra
aproximada.

---

## 5. Seguridad

Vale el 20 % del Reto 1, del cual la resistencia a inyección es el 75 % — el **15 % del
puntaje total**. Se mide con ataques de ADL sobre el endpoint desplegado.

### 5.1 Por qué el guardián es determinista

Un filtro basado en un modelo sería a la vez más caro y más atacable: se le puede hablar. A
una expresión regular no. El guardián no llama a ningún modelo, no consulta el índice y no
escribe estado; ve un texto y decide sobre ese texto. Ese aislamiento es lo que lo hace
auditable.

Cubre once familias de patrones —revelar instrucciones, adjuntar instrucciones, ignorar
reglas previas, cambio de rol, modo sin restricciones, extracción de configuración, escape
de etiquetas, instrucción dirigida a un modelo, orden sobre la forma de la respuesta,
dictado de respuesta y confirmación de lectura— en español e inglés, sobre el texto normalizado en NFKC y sin
tildes, de modo que `ignｏra` con o de ancho completo o un carácter de ancho cero entre
letras no burlen el filtro.

### 5.2 Separación estricta entre instrucción y dato

El contenido recuperado entra al prompt marcado como dato:
`<documento_recuperado id="...">…</documento_recuperado>`, con la etiqueta de cierre
neutralizada dentro del contenido para que nadie pueda cerrar el sobre antes de tiempo.

**Y eso no basta, lo cual se midió.** El prompt del agente documental ya le decía
explícitamente que nada dentro de esas etiquetas es una instrucción, y `llama-3.3-70b`
obedeció igualmente una orden embebida en un documento del corpus. Un prompt pide; hace
falta una garantía. Por eso las órdenes dirigidas a un modelo se **sustituyen por una marca
antes** de que el texto llegue al prompt.

La marca describe el hecho sin nombrar el mecanismo —viaja dentro del `retrieval_context`
que ADL evalúa, y el modelo la parafrasea al usuario— y marca en vez de borrar en silencio,
porque un analista que lee la evidencia tiene derecho a saber que el sistema intervino ese
fragmento.

### 5.3 El visualizador nunca ejecuta nada

Emite un `ViewSpec` con campos `Literal` y `extra="forbid"`. Si produce algo fuera del
vocabulario, se descarta en la frontera del API y la respuesta de texto sigue siendo útil.
Una vista inválida no puede llegar al tablero ni tumbar la respuesta.

### 5.4 Resultados medidos

Batería propia de 28 vectores contra el endpoint (`scripts/bateria_inyeccion.py`):

| | Resultado |
|---|---|
| Bloqueados en la entrada, **0 llamadas al gateway** | 21 |
| Neutralizados dentro del documento | 4 |
| Llegaron al modelo | 3 |
| **Fugas de contenido interno** | **0** |
| **Falsos positivos sobre 14 consultas legítimas** | **0** |

Los tres que llegan al modelo son los que no se deben bloquear con patrones sin destrozar
el bloque de calidad: la excusa social con autoridad falsa, el texto codificado en base64 y
una instrucción escondida al final de una entrada larga. Ninguno filtró nada.

**Los dos errores no cuestan lo mismo, y el diseño lo refleja.** Un falso negativo cuesta
seguridad (20 %); un falso positivo —rechazar una pregunta válida— cuesta calidad (40 %),
que pesa el doble. Por eso la lista de "fuera de dominio" es deliberadamente corta y
literal, y ante la duda se deja pasar: el agente documental ya declara cuándo no tiene
evidencia, y esa es una respuesta honesta; un rechazo indebido, no.

El impacto de la neutralización sobre el corpus real se midió antes de activarla: **1
fragmento de cada 65.374** (0,0015 %). En el camino aparecieron dos falsos positivos que ya
existían: `\bDAN\b` casaba el nombre propio *Dan* de las bibliografías, y `Notice to
Airmen` casaba por el `ai` de *Airmen*. Ambos corregidos.

---

## 6. Honestidad de los datos

`RETO.md` prohíbe presentar cifras engañosas. Dos límites del corpus se declaran en el
producto, no se esconden:

### 6.1 Cobertura temporal: 621 de 1.826 documentos

Solo el **34 %** de los documentos declara año. **Toda agregación temporal declara esa
cobertura**, y la declaración se impone en el código: si el visualizador emite una vista
temporal sin nota, el sistema se la pone. No se confía en que el modelo lo recuerde.

Una línea de tiempo sobre 621 documentos presentada como si fueran 1.826 es exactamente la
cifra creíble y falsa que la especificación prohíbe.

### 6.2 El corpus no tiene ubicación

`GET /api/geo` lo declara explícitamente:

```json
{"disponible": false,
 "motivo": "el corpus no contiene ubicacion: la metadata no tiene lugar, pais ni coordenadas",
 "alternativa": "para analisis geografico se puede agrupar por organizacion, que es un dato
                 real del corpus, pero indica quien publica y no donde ocurre"}
```

La Especificación menciona georreferenciación entre los entregables del Reto 2. **No
construimos un mapa**, y la razón es que cualquier mapa sobre este corpus sería una
geocodificación inventada a partir de topónimos sueltos en el texto, presentada con la
autoridad visual de una coordenada. Preferimos declarar la ausencia y ofrecer la
agrupación por organización, dejando claro que indica *quién publica*, no *dónde ocurre*.

Es una decisión consciente, no una carencia: un mapa falso puntúa peor que un mapa ausente
en un producto cuyo criterio es la trazabilidad.

---

## 7. Propuesta de visualización por fenómeno

*(Bloque A del Reto 2: 40 %, evaluado desde este documento.)*

No existe catálogo obligatorio de componentes: cada equipo elige y justifica. El catálogo
que el sistema puede activar —`timeline`, `bar`, `stacked_bar`, `donut`, `table`, `kpi`
sobre las dimensiones `fenomeno`, `organizacion`, `fuente`, `formato`, `anio`— se eligió
para que **toda opción tenga datos reales detrás**. Si el tablero no puede poblar una
combinación, la respuesta es quitarla del vocabulario, no enseñar al modelo a evitarla.

El principio común a los tres fenómenos: **la composición documental es en sí un hallazgo
analítico**. Saber que el 68 % del material sobre IA estratégica viene de dos think tanks
estadounidenses no es metadato administrativo; es una advertencia sobre el sesgo de la base
de evidencia con la que se va a razonar.

### F1 — Inteligencia artificial y capacidades estratégicas · 459 documentos

| Organización | Docs |
|---|---|
| Atlantic Council | 186 |
| CSET Georgetown | 127 |
| AI Index Stanford | 65 |
| DAIO | 35 |
| CENIA | 27 |
| ILIA LatAm | 10 |
| RutaN GEIAL | 7 |

**Componente principal: `bar` por organización.** La pregunta analítica que responde es *¿de
quién estamos aprendiendo sobre IA estratégica?* — y la respuesta es incómoda y útil: 313 de
459 documentos (68 %) salen de dos centros estadounidenses, frente a 46 de las cuatro
fuentes latinoamericanas juntas. Cualquier conclusión que el sistema produzca sobre este
fenómeno hereda ese encuadre, y el tablero debe hacerlo visible antes que ocultarlo tras un
agregado.

**Componente secundario: `stacked_bar` organización × formato.** Separa el informe
narrativo (`pdf`) del dato estructurado (`json`), que es la diferencia entre una fuente que
argumenta y una que mide. Importa al ponderar evidencia.

**Descartado: `timeline`.** La cobertura temporal de este fenómeno no sostiene una serie
anual legible.

### F2 — Seguridad del entorno espacial · 479 documentos

| Organización | Docs |
|---|---|
| CSIS Aerospace | 214 |
| SWF Counterspace | 135 |
| INPE | 59 |
| ESA Space Debris | 40 |
| UNOOSA | 31 |

**Componente principal: `timeline` por año, con la nota de cobertura impuesta.** Es el único
fenómeno donde la evolución temporal tiene sentido analítico de verdad: los informes de
*counterspace* de SWF y CSIS son ediciones anuales, y la acumulación de objetos en órbita
que documenta ESA es por definición una serie. La pregunta es *¿se acelera la actividad
documentada, o solo se documenta más?*, y esa ambigüedad es justamente lo que la nota del
34 % obliga a mantener a la vista.

**Componente secundario: `bar` por organización.** Aquí la lectura es la contraria a F1:
cinco fuentes con perfiles distintos —dos think tanks, dos agencias espaciales, un
organismo de Naciones Unidas— dan una base más equilibrada, y conviene poder demostrarlo.

**Descartado: mapa orbital o de lanzamientos.** No hay coordenadas ni identificadores de
objeto en la metadata (§6.2).

### F3 — Dinámicas territoriales en América Latina · 888 documentos

| Organización | Docs |
|---|---|
| Alertas Tempranas | 425 |
| SIPRI | 128 |
| RESDAL | 107 |
| CEEEP | 80 |
| Amazon Underworld | 75 |
| CEOBS | 38 |
| MAPP OEA | 35 |

**Componente principal: `donut` por organización.** Es el fenómeno con más documentos (888,
casi la mitad del corpus) y también el más concentrado: **el 48 % viene de una sola fuente**,
el Sistema de Alertas Tempranas. El `donut` se elige aquí precisamente porque la pregunta es
de proporción sobre pocas categorías —*¿qué parte de lo que sabemos viene de un solo
emisor?*— y esa es la única pregunta para la que un `donut` es mejor que una barra.

**Componente secundario: `table` con `doc_id` y organización.** En este fenómeno el detalle
importa más que la forma: el analista necesita llegar al documento concreto, y la tabla es
el puente directo a `/api/evidence/{chunk_id}`.

**Descartado, y es el descarte más doloroso: el mapa.** F3 es el fenómeno donde un mapa
sería más natural —son dinámicas *territoriales*— y donde su ausencia más se nota. No lo
construimos porque la metadata no trae municipio, departamento ni coordenada; ubicar los
documentos por topónimos extraídos del texto produciría un mapa denso, convincente y sin
respaldo trazable, que es la peor combinación posible en un producto cuyo criterio es que
todo dato llegue a su `chunk_id`.

### 7.2 Ejecución dinámica

El tablero no muestra todos los componentes a la vez. El agente visualizador decide, a
partir de la instrucción en lenguaje natural, cuál activar y con qué filtros, y el
`ViewSpec` resultante hereda el fenómeno que el plan acotó — sin eso, el título diría
"seguridad del entorno espacial" y el gráfico pintaría los tres.

Todo dato mostrado se rastrea a su origen: cada fila de un conteo incluye los `doc_ids` que
la sustentan, y `GET /api/evidence/{chunk_id}` devuelve el fragmento.

---

## 8. Despliegue

Un solo contenedor sirve los tres dominios, enrutados por `Host`: `agent.` (endpoint),
`frontagent.` (chat) y `dashboard.` (tablero). Un único puerto HTTP, como pide el Anexo A.4.

**Un solo worker, no negociable.** Cada worker cargaría su propia copia del índice y del
encoder: 3,8 GB medidos. La concurrencia se atiende con el threadpool de FastAPI, que los
comparte en memoria y escala mejor — medido: 4 peticiones simultáneas no suben el pico y
bajan la latencia por consulta de 122 ms a 81 ms.

**El índice llega solo.** El Anexo A.4 exige una imagen autosuficiente, así que el corpus no
se copia a mano al servidor: el contenedor lo descarga al arrancar desde `DATA_FILES` y lo
deja en un volumen. La descarga corre en segundo plano a propósito — el servicio responde
desde el primer segundo, `/health` declara `index_loaded: false` mientras tanto, y el índice
se incorpora sin reiniciar. Bloquear el arranque durante 1,6 GB dejaría los tres dominios en
`503` justo cuando el proxy decide si enrutar el contenedor.

El detalle operativo completo —variables, volúmenes, procedimiento y lista de verificación—
está en [`DEPLOY.md`](../DEPLOY.md).

---

## 9. Lo que no se construyó, y por qué

- **Mapa geográfico.** El corpus no tiene ubicación (§6.2).
- **Visualización de relaciones.** Requiere el grafo de conocimiento, que era opcional en la
  Etapa 1 y no forma parte de nuestra base. Un grafo de co-ocurrencia de términos habría
  sido posible, pero presenta como relación semántica lo que es una coincidencia estadística.
- **Índices de riesgo o niveles de amenaza.** `RETO.md` los prohíbe expresamente como
  medición objetiva. Conteos, frecuencias y agregaciones sí; puntajes sintéticos no.
- **Un agente por fenómeno.** Se evaluó y se descartó: triplicaría el coste de
  planificación sin añadir capacidad — la especialización real está en el tipo de pregunta
  (documental, cuantitativa, visual), no en el tema.
