# Meta-prompt — Pitch deck de A.R.P.I.A.

> Para Claude Design, Gamma, Canva u otra herramienta de generación de slides.
> Rellena los `<<campos>>` **después** de conocer el reto. Un deck genérico
> con los huecos sin llenar se nota de inmediato.

---

## Prompt

```
Genera una presentación de 8 diapositivas para un pitch técnico de 5 minutos
ante un jurado de fuerza aérea, academia e industria.

PROYECTO
Nombre: A.R.P.I.A.
Qué es: <<una frase: qué hace el sistema y para quién>>
Problema que resuelve: <<el dolor concreto, en términos del usuario, no
técnicos>>

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
