# Recontexto para el pitch — A.R.P.I.A.

> **Fuente única de cifras para el deck y para responder al jurado.**
> Todo lo de aquí está medido contra el sistema desplegado o contra el corpus
> real, con la fecha en que se midió. Lo que no se pudo medir se marca como
> **[no medido]** en lugar de estimarse: una cifra inventada en un pitch
> técnico se cae en la primera pregunta, y el jurado de este reto es de fuerza
> aérea, academia e industria.
>
> Acompaña a [`prompts/pitch-deck.md`](prompts/pitch-deck.md), que trae los
> `<<campos>>` a rellenar y el sistema visual.
>
> Medido el **19 de septiembre de 2026**.

---

## 1. Los `<<campos>>` del prompt, rellenos

**Nombre:** A.R.P.I.A. — Asistente de Recuperación y Producción de Inteligencia
Analítica.

**Qué es (una frase):**
> Un sistema multi-agente que responde preguntas en lenguaje natural sobre un
> corpus de 326.866 fragmentos documentales y construye el tablero que cada
> respuesta necesita, con cada cifra rastreable hasta el documento que la
> sostiene.

**Problema que resuelve (en términos del usuario):**
> Un analista con 1.826 documentos de 20 organizaciones no tiene un problema de
> búsqueda: tiene un problema de **procedencia**. Puede encontrar una cifra en
> minutos; justificar de dónde salió, ante quien decide, le cuesta horas. Y
> cuando la base documental está sesgada —el 68 % del material sobre IA
> estratégica viene de dos centros estadounidenses— ese sesgo viaja dentro de
> la conclusión sin que nadie lo vea.

---

## 2. El corpus, en cifras

| Dato | Valor |
|---|---|
| Fragmentos indexados | **326.866** |
| Documentos | **1.826** |
| Organizaciones | **20** |
| Fenómenos | 3 (F1 IA estratégica, F2 seguridad espacial, F3 dinámicas territoriales) |
| Índice | FAISS `IndexFlatIP`, 1.024 dimensiones, encoder `BAAI/bge-m3` |
| Tamaño | 1,7 GB (`index.faiss` 1,3 GB + `metadata.jsonl` 360 MB) |

**Reparto por fenómeno:** F3 = 888 · F2 = 479 · F1 = 459.

**Concentración de fuentes** — el hallazgo que el sistema produce solo, y que
sirve de ejemplo en el pitch:

| Fenómeno | Concentración medida |
|---|---|
| F1 · IA estratégica | Atlantic Council + CSET Georgetown = **313 de 459 (68 %)** |
| F2 · Seguridad espacial | CSIS Aerospace + SWF Counterspace = **349 de 479 (73 %)** |
| F3 · Dinámicas territoriales | Alertas Tempranas = **425 de 888 (48 %)**, una sola fuente |

**Cobertura temporal: 621 de 1.826 documentos declaran año (34 %).** Toda vista
temporal lo declara, y la declaración se impone en código: si el agente emite
una serie sin ese aviso, el sistema se lo pone.

---

## 3. Arquitectura — slide 4

Ocho agentes. **Cuatro cuestan cero tokens**, y esa es la decisión de diseño que
define el sistema.

| Agente | Modelo | Coste por turno |
|---|---|---|
| Orquestador | `gpt-oss-120b` | 1 llamada |
| Documental | `llama-3.3-70b-instruct` | 1 llamada |
| Visualizador | `gpt-oss-120b` | 1 llamada, solo si se pide vista |
| Analítico | `gpt-oss-20b` | 0 en preguntas de conteo |
| **Compositor** | — | **0 siempre** |
| **Guardián** | — | **0 siempre** |
| **Memoria** | — | **0 siempre** |
| Verificador | `llama-3.3-70b-instruct` | 0 salvo que corrija |

**Coste acotado por construcción, no por suerte:**

```
pregunta documental     2 llamadas
pregunta cuantitativa   1 llamada
pregunta con vista      3 llamadas
sin evidencia          +1  (una replanificación, y solo una)
```

**Medición real en producción** (19/09/2026, pregunta *"Gráfica quién publica
sobre seguridad del entorno espacial"*):

```
2 llamadas · 2.662 tokens · 11,9 s
4 vistas generadas · 2 hallazgos · 8 citas con doc_id y chunk_id
```

La recuperación no cuesta tokens: FAISS y el encoder corren en la CPU del
contenedor. Es la ventaja frente a equipos que pasan el corpus por un modelo.

---

## 4. Decisiones técnicas — slide 6 (la que gana puntos)

El prompt pide **al menos una cosa probada y descartada con datos**. Hay seis.

### Descartado: bucle ReAct → plan único
El bucle hace entre 3 y 7 llamadas por pregunta, sin cota. El bloque de
eficiencia se normaliza *contra los otros equipos*. Un coste que no se puede
acotar es un riesgo que no se puede presupuestar.

### Descartado: mapa geográfico
`GET /api/geo` lo declara: *"el corpus no contiene ubicación: la metadata no
tiene lugar, país ni coordenadas"*. Geocodificar topónimos sueltos habría dado
un mapa denso, convincente y sin respaldo trazable. **Es el descarte más
doloroso** —F3 son dinámicas *territoriales*— y el más defendible.

### Descartado: `serie_por` visible para el modelo
Con el campo en el esquema, `gpt-oss-20b` cambiaba el fenómeno filtrado de F3 a
F1 **en 4 de 4 corridas**. Se ocultó del esquema y lo rellena el compositor,
que es determinista y no se equivoca de fenómeno.

### Descartado: `gpt-oss-20b` en el visualizador
El razonamiento era que un vocabulario cerrado no necesita capacidad. Lo medido
dice lo contrario: el pequeño devolvía las claves con la capitalización del
esquema y **gastaba más** (3.128 tokens frente a 2.662 del grande en la misma
pregunta), porque fallaba y degradaba.

### Descartado: datos de ejemplo en el tablero
El prototipo abría con una serie inventada y tres marcadores sobre Colombia.
Se eliminaron y **un test mecánico impide que vuelvan**. Con ellos se fue
Leaflet, que además cargaba tiles de `tile.openstreetmap.org`: una dependencia
de red externa en plena ventana de evaluación.

### Descartado: copiar el corpus al servidor a mano
El Anexo A.4 exige una imagen autosuficiente. El contenedor descarga el índice
al arrancar, **en segundo plano**: el servicio responde desde el primer segundo
y el índice se incorpora sin reiniciar. Medido: **1,7 GB en 24 segundos**.

---

## 5. Seguridad — 15 % del puntaje del Reto 1

Batería propia de **28 vectores** (`scripts/bateria_inyeccion.py`):

| | Resultado |
|---|---|
| Bloqueados en la entrada, **0 llamadas al gateway** | 21 |
| Neutralizados dentro del documento | 4 |
| Llegaron al modelo | 3 |
| **Fugas de contenido interno** | **0** |
| **Falsos positivos sobre 14 consultas legítimas** | **0** |

**El hallazgo que vale contar:** `llama-3.3-70b` **obedeció** una instrucción
escondida dentro de un documento del corpus, pese a que el prompt le decía
explícitamente que no lo hiciera. Un prompt pide; hizo falta una garantía. Las
órdenes dirigidas a un modelo se sustituyen por una marca **antes** de llegar
al prompt.

**Daño colateral medido antes de activarlo: 1 fragmento de cada 65.374
(0,0015 %).** En el camino aparecieron dos falsos positivos que ya existían:
`\bDAN\b` casaba el nombre propio *Dan* de las bibliografías, y `Notice to
Airmen` casaba por el `ai` de *Airmen*.

---

## 6. Calidad del código

| | |
|---|---|
| Pruebas Python | **541** |
| Pruebas JavaScript | **35** |
| Fallos | **0** |
| Linter (`ruff`) | limpio |

---

## 7. Resultados y límites — slide 7

**Lo que funciona, verificado en el endpoint desplegado:**
- `POST /chat` en `live`, con `retrieval_context`, citas y `doc_id`/`chunk_id`
- El tablero se organiza solo: de 2 vistas a 4 por respuesta, a coste cero
- Hallazgos deterministas con su procedencia
- Progreso en vivo del turno, sin publicar el contenido de las preguntas

**Límites, dichos antes de que los pregunten:**
1. **El 66 % de los documentos no declara año.** Toda vista temporal lo avisa.
2. **No hay geografía.** El corpus no trae lugar. No hay mapa.
3. **No hay grafo de relaciones.** Era opcional en la Etapa 1 y no se construyó.
   Un grafo de co-ocurrencia habría sido posible, pero presenta como relación
   semántica lo que es una coincidencia estadística.
4. **Un solo worker.** Cada worker carga su copia del índice y del encoder:
   3,8 GB medidos con 4 peticiones concurrentes.
5. **Certificado TLS pendiente.** Traefik sirve su certificado por defecto; la
   configuración es correcta (`certresolver=letsencrypt` en los tres routers) y
   el challenge ACME responde. Depende de la infraestructura del evento.
6. **Sin autenticación.** Los tres dominios son públicos, como exige el reto.

---

## 8. Las cinco preguntas del jurado — respuesta de 30 segundos

**¿Por qué multiagente y no un solo agente?**
Porque los costes son distintos. Contar documentos es una consulta a una tabla:
exacta y gratis. Redactar con fidelidad a la evidencia necesita un modelo
grande. Un solo agente paga el precio del caso más caro en todos los casos.
Cuatro de nuestros ocho agentes cuestan cero tokens.

**¿Qué pasa si el modelo se equivoca? ¿Quién lo detecta?**
Tres barreras. El esquema cerrado descarta lo que no encaja antes de llegar al
tablero. El verificador comprueba la redacción contra la evidencia. Y el
guardián revisa la salida. Cuando algo falla, el sistema degrada: entrega los
fragmentos con su procedencia en vez de una disculpa.

**¿Cuánto cuesta ejecutar esto una vez?**
Entre 1 y 3 llamadas según el tipo de pregunta. Medido: 2.662 tokens y 11,9
segundos para una pregunta con cuatro visualizaciones.

**¿Qué haría falta para llevarlo a producción?**
Tres cosas. Autenticación, que hoy no existe porque el reto exige acceso
público. Un almacén compartido para el estado si se levantan varios workers.
Y resolver la cobertura temporal en origen: el 34 % limita todo análisis
longitudinal, y eso no se arregla en el sistema, se arregla en la ingesta.

**¿De dónde salen los datos y con qué licencia?**
Fuentes abiertas de 20 organizaciones —SIPRI, CSIS, Secure World Foundation,
ESA, UNOOSA, Atlantic Council, CSET Georgetown, entre otras— provistas por ADL
para el reto. **[Verificar la licencia con ADL antes del pitch.]**

---

## 9. Para las capturas — slide 5

El prompt exige capturas **reales**. Las tres que mejor cuentan la historia:

1. **El chat con el progreso en vivo**: los agentes apareciendo mientras el
   turno corre. Demuestra que hay un sistema, no una llamada a un modelo.
2. **El tablero con las cuatro vistas de una sola pregunta**, con los hallazgos
   debajo. Es la ejecución dinámica que evalúa el Reto 2.
3. **Una cita abierta en el visor**, mostrando el fragmento exacto con su
   `chunk_id`. Es la trazabilidad, que es el argumento del producto.

**[Pendiente: tomarlas del despliegue, no del entorno local.]**
