# Meta-prompt — Pitch deck de A.R.P.I.A.

> Para Claude Design, Gamma, Canva u otra herramienta de generación de slides.
>
> **Los campos ya están rellenos con valores medidos** el 19/09/2026 contra el
> sistema desplegado y el corpus real. La fuente de cada cifra, y las que no
> caben en el deck, están en [`../pitch-recontexto.md`](../pitch-recontexto.md).
>
> Si una cifra cambia, se cambia **primero en el recontexto** y luego aquí: dos
> copias que divergen son peores que una sola desactualizada, porque nadie sabe
> cuál mirar.

---

## Prompt

```
Genera una presentación de 8 diapositivas para un pitch técnico de 5 minutos
ante un jurado de fuerza aérea, academia e industria.

PROYECTO
Nombre: A.R.P.I.A. (Asistente de Recuperación y Producción de Inteligencia
Analítica)

Qué es: un sistema multi-agente que responde preguntas en lenguaje natural
sobre un corpus de 326.866 fragmentos documentales y construye el tablero que
cada respuesta necesita, con cada cifra rastreable hasta el documento que la
sostiene.

Problema que resuelve: un analista con 1.826 documentos de 20 organizaciones no
tiene un problema de búsqueda, tiene un problema de PROCEDENCIA. Encontrar una
cifra le cuesta minutos; justificar de dónde salió, ante quien decide, le cuesta
horas. Y cuando la base documental está sesgada —el 68 % del material sobre IA
estratégica viene de dos centros estadounidenses— ese sesgo viaja dentro de la
conclusión sin que nadie lo vea.

CIFRAS VERIFICADAS (usar estas, no redondear ni estimar)
- Corpus: 326.866 fragmentos · 1.826 documentos · 20 organizaciones · 3 fenómenos
- Ocho agentes, CUATRO de ellos a coste cero de tokens
- Coste por pregunta: 1 a 3 llamadas. Medido: 2.662 tokens y 11,9 s para una
  pregunta que generó 4 visualizaciones, 2 hallazgos y 8 citas
- Seguridad: 28 vectores de inyección probados. 21 bloqueados sin gastar una
  sola llamada, 4 neutralizados dentro del documento, 0 fugas, 0 falsos
  positivos sobre 14 consultas legítimas
- 541 pruebas Python y 35 de JavaScript, todas en verde
- Cobertura temporal del corpus: 621 de 1.826 documentos declaran año (34 %)

DIAPOSITIVA 6 — decisiones, incluida una descartada con datos
Usar estas dos, que son las más fuertes:
1. Se descartó dar al modelo el campo `serie_por`: con él visible, el modelo
   cambiaba el fenómeno filtrado de F3 a F1 en 4 de 4 corridas. Lo rellena
   ahora un agente determinista, que no se equivoca de fenómeno.
2. Se descartó el mapa geográfico. El corpus no trae ubicación, y geocodificar
   topónimos habría dado un mapa denso, convincente y sin respaldo trazable.
   Es el descarte más doloroso —F3 son dinámicas territoriales— y el más
   defendible.

DIAPOSITIVA 7 — límites, dichos antes de que los pregunten
El 66 % de los documentos no declara año · no hay geografía · no hay grafo de
relaciones · un solo worker (3,8 GB medidos con 4 peticiones concurrentes).

SISTEMA VISUAL (obligatorio, no improvisar colores)
Fondo principal:      #040C1D
Superficies/paneles:  #0F1B30
Superficie elevada:   #16243A
Bordes:               #233E4D
Azul primario:        #3566CC
Cian/espacio:         #54B1DC
Verde operacional:    #10B981
Ámbar (evidencia):    #F59E0B
Rojo (crítico):       #EF4444
Texto principal:      #F0F6FC
Texto secundario:     #A1A5A9

Tipografía: sans-serif muy legible para texto; monoespaciada SOLO para
identificadores, coordenadas, métricas y salida de máquina.

DIRECCIÓN VISUAL
Debe sentirse: analítico, aeroespacial, técnico, preciso, profesional, denso en
información pero controlado.
Evitar: estética cyberpunk, neón, glow, elementos sci-fi decorativos, degradados
llamativos, iconografía genérica de IA (cerebros, robots, redes neuronales).
La identidad viene de composición, jerarquía y densidad, no de adornos.
Esquinas poco redondeadas. Sombras suaves o ninguna. Bordes de 1px para separar.

ESTRUCTURA
1. Portada — nombre, expansión de la sigla, una línea de propósito.
2. Problema — el dolor, con una cifra o un hecho concreto que lo dimensione.
3. Solución — qué hace el sistema, en lenguaje de usuario, no de framework.
4. Arquitectura — diagrama de bloques limpio: entrada, agentes, fuentes,
   salida. Máximo 6 cajas. Sin logos de librerías.
5. Demo — 2 o 3 capturas reales de la interfaz. Sin mockups inventados.
6. Decisiones técnicas — 3 decisiones y por qué, incluyendo al menos una cosa
   que se probó y se DESCARTÓ con datos.
7. Resultados y límites — qué se logró y qué no. Declarar las limitaciones
   explícitamente.
8. Siguiente paso — qué haría falta para llevarlo a producción.

REGLAS DE CONTENIDO
- Máximo 30 palabras por diapositiva. El que habla es la persona, no el slide.
- Sin bullets de más de una línea.
- Cada número que aparezca debe ser medido, no estimado.
- Nada de "revolucionario", "disruptivo", "de última generación".
- Vocabulario: "análisis estratégico" antes que "chatbot"; "fusión de fuentes"
  antes que "pipeline"; "apoyo a la decisión" antes que "automatización".
```

---

## Notas de uso

**La diapositiva 6 es la que gana puntos ante un jurado técnico.** Mostrar algo
que se probó, se midió y se descartó demuestra criterio; mostrar solo aciertos
sugiere que no se midió nada.

**La diapositiva 7 no es una debilidad.** Declarar límites conocidos es lo que
separa un prototipo honesto de una demo inflada, y un jurado experto lo detecta
en las preguntas. Mejor decirlo tú.

**Las capturas deben ser reales.** Un mockup se nota, y abre la pregunta de si
el sistema funciona.

## Preguntas que el jurado hará — tener respuesta de 30 segundos

- ¿Por qué multiagente y no un solo agente?
- ¿Qué pasa si el modelo se equivoca? ¿Quién lo detecta?
- ¿Cuánto cuesta ejecutar esto una vez?
- ¿Qué haría falta para llevarlo a producción?
- ¿De dónde salen los datos y con qué licencia?
