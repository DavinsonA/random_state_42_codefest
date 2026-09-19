# Arquitectura agéntica y resumen de los retos — material para diseño

> Listo para pegar en la herramienta de slides. Las cifras salen de
> [`pitch-recontexto.md`](pitch-recontexto.md); si cambian, se cambian allí
> primero.

---

## A. Diagrama para la diapositiva 4 — seis cajas

El prompt del deck limita a seis cajas y prohíbe logos de librerías. Esta es la
versión que cabe:

```
  ┌──────────────┐
  │   PREGUNTA   │  lenguaje natural
  └──────┬───────┘
         ▼
  ┌──────────────┐
  │   GUARDIÁN   │  filtro determinista · 0 tokens
  └──────┬───────┘  rechaza el ataque antes del modelo
         ▼
  ┌──────────────┐
  │ ORQUESTADOR  │  1 llamada → plan validado
  └──────┬───────┘  decide a quién delegar
         ▼
  ┌──────────────────────────────────────────┐
  │        AGENTES ESPECIALIZADOS            │
  │  documental · analítico · visualizador   │
  └──────┬───────────────────────────────────┘
         ▼
  ┌──────────────┐
  │    CORPUS    │  326.866 fragmentos · FAISS en CPU
  └──────┬───────┘  recuperación a 0 tokens
         ▼
  ┌──────────────┐
  │  RESPUESTA   │  texto + tablero + procedencia
  └──────────────┘
```

**La línea que acompaña el diagrama:**
> Ocho agentes. Cuatro no gastan un solo token.

---

## B. Los ocho agentes — tabla de respaldo

Para la versión larga, o para responder si el jurado pregunta.

| Agente | Modelo | Coste | Qué aporta |
|---|---|---|---|
| **Orquestador** | `gpt-oss-120b` | 1 llamada | Decide a quién delegar. Emite un plan validado, no texto libre |
| **Documental** | `llama-3.3-70b` | 1 llamada | Redacta sobre la evidencia recuperada, con la fuente al lado de cada afirmación |
| **Visualizador** | `gpt-oss-120b` | 1 llamada | Traduce la instrucción a una vista de vocabulario cerrado |
| **Analítico** | `gpt-oss-20b` | **0** | Conteos exactos sobre metadata agregada, sin pasar por un modelo |
| **Compositor** | — | **0** | Lee la forma de los datos y añade las vistas que la primera hace evidente |
| **Guardián** | — | **0** | Filtro de inyección de entrada y salida. Determinista: a una regex no se le habla |
| **Memoria** | — | **0** | Caché semántico y ventana conversacional |
| **Verificador** | `llama-3.3-70b` | 0 salvo corregir | Comprueba la redacción contra la evidencia |

---

## C. Las tres ideas que sostienen el diseño

Si solo caben tres frases en el slide, estas:

**1. El coste está acotado por construcción.**
```
pregunta documental    2 llamadas
pregunta cuantitativa  1 llamada
pregunta con vista     3 llamadas
sin evidencia         +1  (una sola replanificación)
```
Se descartó un bucle ReAct porque hace entre 3 y 7 llamadas sin cota, y la
eficiencia se puntúa contra los demás equipos.

**2. Lo que se puede calcular, no se pregunta.**
Contar documentos es una consulta a una tabla: exacta y gratis. Preguntárselo a
un modelo cuesta tokens y da una cifra aproximada. Cuatro de ocho agentes viven
de esa distinción.

**3. Lo que no se puede sostener, no se muestra.**
Sin ubicación en el corpus, no hay mapa. Con el 34 % de cobertura temporal, toda
serie lo declara —y la declaración se impone en código, no se confía al modelo—.

---

## D. Resumen de los retos

### Reto 1 — Asistente conversacional
**Entrega:** sábado 08:00 · **Evaluación:** 08:00 → 12:30

Un endpoint desplegado que ADL interroga con su propio conjunto de preguntas, y
un frontend de chat para uso manual.

```
puntaje = 0,40·calidad + 0,20·eficiencia + 0,20·seguridad + 0,20·diseño
```

| Bloque | Qué mide | Dónde nos jugamos algo |
|---|---|---|
| **Calidad 40 %** | Relevancia 30 · Fidelidad 30 · Toxicidad 15 · **Tono 25** | La fidelidad se calcula contra `retrieval_context`: si hay RAG y no se reporta, se pierde el 30 % |
| **Eficiencia 20 %** | Tokens 40 · Interacciones 30 · Latencia 30 | **Normalizada contra los otros equipos.** Menos es mejor |
| **Seguridad 20 %** | Resistencia a inyección 75 · Análisis estático 25 | La resistencia es el **15 % del total** del reto |
| **Diseño 20 %** | Arquitectura multi-agente | Se evalúa desde la agent card y el documento, no desde el código |

### Reto 2 — Visualización y tablero
**Entrega:** sábado 12:30 · **Evaluación:** desde las 12:30, sin cierre fijo

Expertos del dominio interactúan con el tablero y formulan sus propias
preguntas en lenguaje natural.

| Bloque | Peso | Qué mide |
|---|---|---|
| **Propuesta de diseño** | 40 % | Qué componentes se construyeron para cada fenómeno y por qué. **Se evalúa desde el documento de arquitectura**, no solo desde el tablero |
| **Ejecución dinámica** | 55 % | Que el agente active el componente correcto, con los datos correctos, ante cada pregunta |
| **Calidad del código** | 5 % | Análisis estático |

### Restricciones duras que atraviesan ambos

- **Repositorio privado**, siempre
- **100 USD de presupuesto** por equipo. Al superarlo, la API Key muere
- **Datos reales.** No se aceptan datos simulados en la versión desplegada
- **Trazabilidad.** Todo dato mostrado se rastrea a su `doc_id` y `chunk_id`
- **Prohibido inventar puntajes.** Conteos, frecuencias y agregaciones sí;
  índices de riesgo calculados ad-hoc, no

---

## E. Cómo responde el sistema a cada bloque

La tabla que conecta lo construido con lo que se puntúa. Útil si el jurado
pregunta *"¿y esto por qué lo hicieron así?"*.

| Exigencia | Respuesta del sistema |
|---|---|
| Fidelidad 30 % | `retrieval_context` viaja en cada respuesta, con 8 fragmentos y sus citas |
| Tono 25 % | Un solo módulo define la voz (`voz.py`); hay pruebas que fallan si un texto no sale de ahí |
| Eficiencia | 4 de 8 agentes a 0 tokens; recuperación en CPU; coste acotado por construcción |
| Inyección 15 % | 28 vectores probados: 21 bloqueados sin gastar una llamada, 0 fugas, 0 falsos positivos |
| Diseño 20 % | Agent card con los 8 agentes y documento de arquitectura de 400 líneas |
| Propuesta por fenómeno 40 % | Un componente justificado por fenómeno, con el descarte del mapa argumentado |
| Ejecución dinámica 55 % | De 2 vistas a 4 por respuesta, decididas por la forma de los datos, a 0 tokens |
| Trazabilidad | Cada hallazgo y cada cifra arrastran sus `doc_ids`; `/api/evidence` abre el fragmento |
