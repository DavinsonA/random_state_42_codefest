# Discurso del pitch — A.R.P.I.A. · 5 minutos

> Para el deck de 8 diapositivas. **Lo que está entre comillas se dice; lo que
> está entre corchetes se hace.** Las cifras salen de
> [`pitch-recontexto.md`](pitch-recontexto.md).
>
> Reparto: 4:40 de discurso y 20 s de margen. Si vas tarde, **recorta la 4**,
> que es la única que repite lo que ya dijo la 3.

---

## Antes de empezar

**Habla a la persona de fuerza aérea, no al ingeniero.** El jurado mezcla
fuerza aérea, academia e industria; quien decide compra *procedencia*, no
arquitectura. La arquitectura es la prueba de que la procedencia es real.

**El número es tuyo, la frase es del slide.** No leas la diapositiva. Di el
dato y explica por qué importa.

**Tres palabras prohibidas:** revolucionario, disruptivo, de última generación.

---

## 01 · Portada — 20 s

> "A.R.P.I.A. Un sistema multi-agente que responde preguntas sobre 326.000
> fragmentos documentales y construye el tablero que cada respuesta necesita.
>
> Con una condición que atraviesa todo el diseño: **cada cifra que muestra se
> rastrea hasta el documento que la sostiene.**"

[No te presentes por nombre: está en el slide. Ganas 10 segundos.]

---

## 02 · El reto — 30 s

> "Dos retos. Un asistente que ADL interroga con sus propias preguntas, y un
> tablero con el que expertos del dominio interactúan en vivo.
>
> De todo lo que se puntúa, hay dos números que condicionaron cada decisión que
> tomamos: **la eficiencia se normaliza contra los demás equipos** —no contra
> un umbral—, y **la resistencia a inyección de prompt es el 15 % del total**.
>
> Y cuatro restricciones duras. La que más nos marcó: **está prohibido inventar
> puntajes**. Conteos y frecuencias sí. Índices de riesgo calculados a ojo, no."

[Señala "Sin puntajes inventados". Volverás a ese punto en la 6 y en la 7.]

---

## 03 · Arquitectura — 50 s

> "Ocho agentes. **Cuatro no gastan un solo token.**
>
> La pregunta entra por el guardián, que es determinista: filtra ataques de
> inyección con expresiones regulares, no con un modelo. A una expresión
> regular no se le puede hablar.
>
> El orquestador hace **una sola llamada** y devuelve un plan validado, no
> texto libre. Lo que no encaja en el esquema no se ejecuta.
>
> Y abajo, el corpus: 326.000 fragmentos, con la recuperación corriendo en la
> CPU del contenedor. **La búsqueda no cuesta tokens.** Eso es lo que otros
> equipos pagan pasando el corpus por un modelo."

[Esta es la diapositiva de la que salen la mitad de las preguntas. No corras.]

---

## 04 · Solución — 45 s

> "Aquí está el principio: **lo que se puede calcular, no se le pregunta a un
> modelo.**
>
> ¿Cuántos documentos hay por organización? Es una consulta a una tabla:
> instantánea, exacta y gratis. Preguntárselo a un modelo cuesta tokens y
> devuelve una cifra aproximada que *parece* correcta.
>
> Por eso el coste de cada pregunta está acotado por construcción, no por
> suerte: una pregunta cuantitativa es **una llamada**; una documental, dos;
> una que pide gráfica, tres. Y si no hay evidencia, se replanifica **una sola
> vez**."

[Si vas con más de 30 segundos de retraso, sáltate esta y ve directo a la demo.]

---

## 05 · Demo — 90 s · **la diapositiva que decide**

> "Voy a hacer una sola pregunta."

[Escribe: *"Gráfica quién publica sobre seguridad del entorno espacial"*]

> "Mientras responde, fíjense en el panel de la izquierda: **son los agentes
> reales ejecutándose**, no una animación. Guardián, memoria, orquestador,
> visualizador. Cada paso aparece cuando termina de verdad."

[Cuando cargue el tablero:]

> "Una pregunta. **Cuatro visualizaciones.** Yo pedí una.
>
> Las otras tres las decidió un agente determinista que lee la forma de los
> datos: como dos organizaciones acumulan el 73 % del material, ofrece la
> proporción; y añade la evolución anual y el reparto por formato. **Eso costó
> cero tokens.**
>
> Y debajo, lo que las cifras dicen: 'CSIS Aerospace y SWF Counterspace acumulan
> 349 de 479 documentos'. No es una opinión del modelo, es aritmética sobre la
> agregación."

[Haz clic en una cita:]

> "Y esto es lo que sostiene todo lo demás: el fragmento exacto, con su
> identificador. **De la conclusión al documento, en un clic.**"

[**Si la demo falla:** no la arregles en vivo. Di: *"Tengo el resultado medido:
dos llamadas, 2.662 tokens, 11,9 segundos, cuatro vistas y ocho citas"*, y pasa
a la 6. Nunca dejes que el jurado te vea depurando.]

---

## 06 · Decisiones — 50 s

> "Tres cosas que probamos y **descartamos**, cada una con un dato.
>
> Empezamos con un bucle ReAct. Hace entre **tres y siete llamadas** por
> pregunta, sin cota. Con la eficiencia normalizada contra los demás equipos,
> un coste que no se puede acotar es un riesgo que no se puede presupuestar. Lo
> cambiamos por un plan único.
>
> La segunda es la que más me gusta. Le dimos al modelo un campo para cruzar
> dos dimensiones. En **cuatro de cuatro corridas** cambió el fenómeno que
> estaba filtrando: pedías F3 y te daba F1. Le quitamos el campo del esquema y
> ahora lo rellena código determinista, que no se equivoca de fenómeno.
>
> Y la tercera: **no hay mapa.** El corpus no trae ubicación. Podríamos haber
> geocodificado los topónimos del texto y habría salido un mapa precioso. Sería
> convincente y no sería trazable, y este sistema se sostiene sobre que todo
> dato llegue a su documento."

[El tercero es el que demuestra criterio. Deja un segundo de silencio después.]

---

## 07 · Resultados y límites — 45 s

> "Seguridad: **28 vectores de inyección**. Veintiuno bloqueados sin gastar una
> sola llamada al modelo. **Cero fugas.** Y —esto importa igual— **cero falsos
> positivos** sobre catorce consultas legítimas: un filtro que rechaza preguntas
> válidas cuesta calidad, que pesa el doble que seguridad.
>
> El hallazgo que más nos enseñó: **el modelo obedeció una instrucción escondida
> dentro de un documento del corpus**, aunque el prompt le decía explícitamente
> que no lo hiciera. Un prompt pide. Hizo falta una garantía: ahora esas órdenes
> se neutralizan antes de llegar al modelo.
>
> Y los límites, que decimos nosotros antes de que los pregunten: **el 66 % de
> los documentos no declara año** —toda serie temporal lo avisa—, no hay
> geografía, no hay grafo de relaciones, y corremos con un solo worker."

[Declarar límites no es debilidad. Un jurado experto los encuentra en las
preguntas; es mejor que los encuentre aquí.]

---

## 08 · Siguiente paso — 20 s

> "Tres cosas para producción. Autenticación, que hoy no existe porque el reto
> exige acceso público. Estado compartido para escalar a varios workers. Y
> fechar los documentos en origen: ese 34 % de cobertura no se arregla en el
> sistema, se arregla en la ingesta.
>
> Gracias."

[Para en seco. No resumas lo que ya dijiste.]

---

## Preguntas del jurado — 30 segundos cada una

**¿Por qué multiagente y no un solo agente?**
> "Porque los costes son distintos. Contar documentos es una consulta a una
> tabla: exacta y gratis. Redactar con fidelidad a la evidencia necesita un
> modelo grande. Un solo agente paga el precio del caso más caro siempre.
> Cuatro de nuestros ocho cuestan cero."

**¿Qué pasa si el modelo se equivoca? ¿Quién lo detecta?**
> "Tres barreras. El esquema cerrado descarta lo que no encaja antes de llegar
> al tablero. El verificador comprueba la redacción contra la evidencia. Y el
> guardián revisa la salida. Cuando algo falla, el sistema degrada: entrega los
> fragmentos con su procedencia en vez de una disculpa."

**¿Cuánto cuesta ejecutar esto una vez?**
> "Entre una y tres llamadas según el tipo de pregunta. Medido: 2.662 tokens y
> 11,9 segundos para la pregunta de la demo, que generó cuatro visualizaciones."

**¿Qué haría falta para producción?**
> [La diapositiva 8, tal cual.]

**¿De dónde salen los datos y con qué licencia?**
> "Fuentes abiertas de veinte organizaciones —SIPRI, CSIS, Secure World
> Foundation, ESA, UNOOSA, Atlantic Council—, provistas por ADL para el reto."
> ⚠️ **Confirmar la licencia con ADL antes del pitch.**

**¿Qué predice el sistema?** ← *la pregunta que abre la sigla*
> "Nada, y es deliberado. El sistema reporta lo que el corpus registra. Asignar
> una probabilidad a un hecho que nadie midió sería fabricar una medición, y el
> reto lo prohíbe expresamente. Tenemos pruebas que fallan si una respuesta dice
> 'tendencia' o 'se espera'."

---

## ⚠️ Decisión pendiente sobre la sigla

La portada dice **"Predicción"**, y el sistema **no predice** —por diseño, con
pruebas que lo impiden—. Tres salidas, en orden de preferencia:

1. **Cambiar la sigla** a algo que el sistema sí hace: *Producción de
   Inteligencia Analítica*. Es un cambio de una línea en la portada.
2. **Dejarla y adelantarte**, diciéndolo tú en la 01: *"la P es de producción
   de inteligencia, no de predicción: este sistema no pronostica"*.
3. Dejarla y usar la respuesta preparada de arriba si preguntan. **Es la peor**:
   te obliga a corregir tu propia portada delante del jurado.

---

## Cronómetro

| Slide | Tiempo | Acumulado |
|---|---|---|
| 01 Portada | 0:20 | 0:20 |
| 02 Reto | 0:30 | 0:50 |
| 03 Arquitectura | 0:50 | 1:40 |
| 04 Solución | 0:45 | 2:25 |
| **05 Demo** | **1:30** | **3:55** |
| 06 Decisiones | 0:50 | 4:45 |
| 07 Resultados | 0:45 | 5:30 |
| 08 Siguiente paso | 0:20 | 5:50 |

**Pasa de 5 minutos.** Recorta así, por orden: la 04 entera (−45 s) y la
segunda mitad de la 02 (−15 s). Quedas en 4:50.
