# CODEFEST Ad Astra 2026 — Etapa 2, Sesión 2 (8 de septiembre)

Resumen de conceptos. Cubre solo lo explicado en esta sesión: **"Agentes que colaboran, sistemas que resuelven"** (Blend 360 — Andrés Hurtado y Simón Calderón López) y **"Desarrollo, integración y evaluación de agentes con ADK"** (Google — Andrés Pérez). Es la segunda sesión de la etapa pre-presencial; complementa directamente la [[etapa2-sesion1-resumen]] (infraestructura del reto) con el diseño concreto de sistemas multiagente.

---

## Parte 1 — Agentes que colaboran, sistemas que resuelven (Blend 360)

### 1.1 La pregunta que abre la charla
**¿Cuántos agentes necesita realmente el problema?** En una hackatón, la tentación es asociar "más agentes" con "solución más inteligente". Los ponentes lo contradicen: un sistema con 5 agentes descoordinados puede tardar más y costar más que uno con 1 agente bien equipado. Cada llamada adicional entre agentes agrega **costo, latencia y una nueva superficie de error**. Muchas veces un solo LLM con buen contexto resuelve el problema mejor que varios agentes tratando de coordinarse.

> **Idea central de la evidencia empírica citada más adelante:** cuando un sistema multiagente falla, la causa más común no es que el modelo "no sea suficientemente inteligente" — es que el **diseño y la especificación del sistema** tienen un defecto.

### 1.2 Árbol de decisión: ¿workflow, agente, o multiagente?
Antes de elegir framework, se decide **cuánta libertad necesita el sistema**:
- **Estructura estable y camino conocido** → workflow determinístico, sin agentes.
- **Subtareas independientes** → paralelizar (no necesariamente con agentes).
- **El sistema debe decidir qué hacer después** → ahí empieza a justificarse un agente.
- **Acción irreversible en el camino** → se necesita un punto de confirmación humana, no solo un agente.

**Ejemplos de aplicación del árbol (casos de hackatón ficticios):**
| Caso | Solución |
|---|---|
| Clasificar tickets/documentos por categoría | Modelo de clasificación, no agente |
| Redactar un informe consultando fuentes propias e interpretarlas | Un agente (razonamiento + retrieval) |
| Investigar 20 fuentes independientes y consolidar un documento | Multiagente en paralelo |

### 1.3 Método de cuatro verbos: Dividir → Organizar → Equipar → Validar
No es una secuencia rígida de una sola pasada — es un **ciclo iterativo**: si dos responsabilidades siempre necesitan el mismo contexto, la división era artificial; si una herramienta nunca se usa, sobra.

**Dividir.** Por cada responsabilidad/agente, definir explícitamente:
1. Propósito
2. Entrada que recibe
3. Salida que produce
4. Criterios/métricas de éxito
5. Autoridad que tiene sobre el sistema
6. **Qué NO necesita saber** — esto define la frontera de aislamiento de contexto.

> Menos contexto no es menos capacidad: por lo general es **menos ruido** y una responsabilidad más fácil de evaluar. Un agente validador, por ejemplo, no debería recibir la explicación persuasiva del autor que está validando — eso introduce sesgo de correlación.

**Organizar.** Patrones, de más simple a más complejo (empezar siempre por el más simple que refleje las dependencias reales):
- **Secuencial / pipeline**: cada paso reduce grados de libertad; se puede verificar entre etapas.
- **Paralelo**: subtareas independientes — por reparto (cada rama resuelve una parte) o por votación (varias ramas convergen para aumentar confianza).
- **Supervisor / orquestador**: cuando no se sabe de antemano cuántos especialistas se necesitan. El orquestador no ejecuta la tarea, sino que formula subtareas, las asigna, evita duplicación y decide cuándo hay evidencia suficiente. Los trabajadores por lo general **no conversan entre sí** — más conexiones dificultan saber quién depende de quién.

**Equipar (el "harness").** El modelo es el motor de razonamiento, pero **el harness es todo lo que rodea al modelo** para que opere de forma segura y repetible:
- **Contexto**: la información mínima necesaria para decidir, sin volcar todo el contexto del sistema.
- **Conectores**: acceso a fuentes/servicios externos con identidad propia y **mínimo privilegio**.
- **Tools**: capacidades de ejecución, clasificadas por riesgo (lectura vs. escritura).
- **Validación, feedback y observabilidad**: "un sistema que no se puede medir, no se sabe si hace lo correcto; un sistema que no se puede observar, no se sabe qué pasó dentro."

**Validar.** Se evalúa en cuatro capas separadas:
1. **Componente**: ¿la tool se llamó con los argumentos correctos?
2. **Trayectoria**: ¿el camino recorrido fue el necesario, o hubo bucles/ramas incorrectas?
3. **Resultado**: extremo a extremo, ¿la salida es la esperada?
4. **Sistema**: latencia y costo — un sistema puede acertar en las tres capas anteriores y seguir siendo inviable si tarda 3 horas o gasta 15M de tokens en una tarea simple.

Método recomendado: un **golden set** privado derivado de trazas reales o experimentos definidos por el equipo (no métricas genéricas), con análisis de fallos reales. Para automatizar el juicio de calidad se usa un **LLM-as-judge** — un modelo más avanzado que el del sistema evaluado, calibrado contra 100–200 ejemplos etiquetados a mano, vigilando sesgos conocidos del juez: **sesgo de posición, verbosidad y auto-preferencia** (el juez prefiere respuestas de su propia familia de modelo).

### 1.4 Observabilidad
Instrumentar observabilidad cuesta poco (los ponentes citan ~20 minutos) y es indispensable en cuanto hay más de un agente. Elemento clave: un **trace ID de correlación**, propagado a cada llamada de modelo, cada tool ejecutada y cada contexto extraído — es la base para poder reconstruir qué pasó en la ejecución completa. Para medir: empezar con ~5 casos "gold" revisados a mano, y usar el LLM-as-judge calibrado para el resto.

**Herramienta usada en la demo: Langfuse.** Es agnóstico al framework de agentes (funciona con LangGraph, CrewAI, Strands Agents, Pydantic AI, agentes de Anthropic, etc.), basado en **OpenTelemetry**, y se integra mediante decoradores en Python. Es open-source y autohospedable vía Docker Compose (o Kubernetes/Helm en producción), o se puede usar como servicio cloud gestionado (usado en la demo, por velocidad).

### 1.5 MCP y A2A: adopción alta ≠ necesidad
- **MCP (Model Context Protocol)**: estandariza cómo un agente **descubre y usa herramientas**.
- **A2A (Agent2Agent)**: estandariza cómo un agente **descubre, delega y sigue una tarea ejecutada por otro agente** (típicamente en máquinas/contextos distintos).

Ambos tienen adopción alta en la industria, pero **adopción no implica que el equipo los necesite**: si una tool se puede resolver con una función de Python simple sin servicio externo, no hace falta envolverla en un servidor MCP; si el subsistema está completamente aislado y no necesita hablar con otros agentes, no hace falta A2A. La pregunta clave antes de conectar cualquier herramienta: **¿qué capacidad externa necesita este agente específico para cumplir su responsabilidad?**

### 1.6 Gobernanza: niveles de supervisión humana
- **Human-on-the-loop**: para actividades rutinarias y reversibles — el agente actúa y el humano audita después (ejemplo cotidiano: guiar/corregir a un asistente de código mientras trabaja, sin bloquear cada paso).
- **Human-in-the-loop**: para acciones irreversibles o de alto riesgo — aprobación síncrona en la frontera de la consecuencia; el agente no avanza hasta que un humano decida.

> **Nota de contexto (mencionada en la charla, sin cita textual):** este tipo de exigencia de supervisión humana para sistemas de alto riesgo se está formalizando como obligación regulatoria en Europa — coincide con los requisitos de supervisión humana del **EU AI Act** para sistemas de IA de alto riesgo. Es una referencia de contexto, no una cita literal de los ponentes.

### 1.7 Antipatrones (con evidencia empírica)
| Antipatrón | Descripción | Cómo evitarlo |
|---|---|---|
| Multiagente por defecto | Se asume que el problema necesita multiagente sin evaluarlo — 15x tokens sin ganancia, subagentes duplicando trabajo | Empezar con un agente único bien equipado |
| Escrituras en paralelo sin consenso | Varios agentes escriben/deciden a la vez sobre el mismo artefacto y no convergen | Un solo escritor, o un coordinador que consolide las respuestas |
| Handoffs con pérdida de contexto | Al pasar una tarea de un agente a otro no se especifica bien qué contexto va con ella | Tareas autocontenidas: objetivo, límites, exclusiones y formato de salida explícitos |
| Aprobación única sobre un "plano opaco" | El humano aprueba un plan, no la acción real que se ejecuta | Puertas de aprobación (gates) en la frontera de cada consecuencia, no solo al final |
| Sin límites de dominio | El usuario saca al agente de su tarea con una excusa social/emocional (jailbreak conversacional) | Definir explícitamente el dominio permitido y detener la ejecución fuera de él |

**Cifras citadas y verificadas:** provienen del paper **"Why Do Multi-Agent LLM Systems Fail?"** (Cemri et al., 2025), que define la taxonomía **MAST** (Multi-Agent System Failure Taxonomy) a partir de más de 1,600 trazas anotadas en 7 frameworks: **41.8% de las fallas son de diseño/especificación del sistema**, **36.9% son desalineación entre agentes**, y el resto (~21%) son fallas de verificación de tareas.

### 1.8 Demos

**Demo 1 (Andrés Hurtado) — generación estandarizada de propuestas comerciales.** Caso: la empresa ficticia ACME debe generar una propuesta para un cliente (Agencia Nacional de Defensa Jurídica del Estado) con un objetivo y presupuesto dados. Problema mostrado: pedirle lo mismo a distintos asistentes (ChatGPT, Claude) sin estandarización produce documentos inconsistentes (analogía: una hamburguesería que contrata personal sin darle la receta de la casa). Solución: construir una **skill** dentro del harness (demo con Claude Code) que fija estructura, capítulos y formato de salida, y una **memoria persistente en archivos** para que el contexto de trabajo no se pierda entre sesiones. Como referencias de organización del trabajo con agentes mencionó dos frameworks:
- **DOE (Directive – Orchestration – Execution)**: arquitectura de 3 capas — directrices en markdown (SOPs), una capa de orquestación que enruta de forma inteligente, y ejecución mediante scripts/herramientas determinísticas para lo que no necesita razonamiento (p. ej. no volver a buscar el logo de la empresa cada vez).
- **AI-DLC (AI-Driven Development Life Cycle, AWS)**: metodología para estructurar el ciclo de desarrollo de software cuando un agente participa activamente en las fases de análisis, diseño e implementación, no solo el humano.

**Demo 2 (Simón Calderón) — triage de tickets de soporte, patrón paralelo-supervisor.** Arquitectura:
```
UI → API → Supervisor (reglas, sin LLM)
              ├─► Especialista de Facturación ─┐
              └─► Especialista Técnico ────────┤
                                                ▼
                                    RAG (Postgres + pgvector)
                                                │
                                                ▼
                                    Agente Sintetizador → respuesta al cliente
```
- El **supervisor es puramente determinístico** (sin LLM) — enruta por reglas/palabras clave.
- Los dos especialistas leen **en paralelo, con contexto aislado** entre sí; ambos consumen Amazon Bedrock y consultan su propio RAG.
- El **agente sintetizador** es el único que redacta la respuesta final al cliente.
- Toda la traza se envía a **Langfuse Cloud** para observabilidad (se mostró latencia y costo por paso, y la capacidad de correlacionar la ejecución completa incluso cuando dos ramas corren en paralelo sin pisarse).

### Conceptos previos necesarios (de sesiones anteriores)
- **Arquitecturas multiagente** (jerárquica, mesh/paralelo, blackboard, workflow) — sesión 1 de julio. Esta charla aterriza el patrón **secuencial/paralelo/supervisor** con criterios prácticos de cuándo usar cada uno, y agrega el nivel de granularidad de "responsabilidad por agente" que sesión 1 no cubría.
- **RAG** — ya introducido; aquí se ve aplicado con Postgres + pgvector como vector store concreto.
- **Observabilidad/tracing (Langfuse)** — ya listado como parte del stack del proyecto; esta charla explica *cómo* y *por qué* instrumentarlo con un ID de correlación.

### Conceptos que se profundizan en próximas sesiones
- **LangGraph/LangChain** (miércoles, Uniandes) — el ejemplo de Simón usa LangGraph por debajo.
- **AgenticRAG** (jueves, Conecto) — construye directamente sobre el patrón RAG + especialista mostrado hoy.

---

## Parte 2 — Desarrollo, integración y evaluación de agentes con ADK (Google)

### 2.1 Jerarquía de abstracción (repaso desde otro ángulo)
ML clásico (supervisado/no supervisado) → redes neuronales → deep learning → **modelos de lenguaje** (entrenados con corpus gigantes) → **IA generativa** (capa adicional para generar contenido creativo, con control de aleatoriedad vía temperatura) → **agentes** (última capa: una entidad que se conecta a esos modelos y **ejecuta acciones**).

**Cómo "ejecuta acciones" un agente, en el fondo:** el modelo genera texto en forma de código, ese código se ejecuta en un sandbox (p. ej. Python), y esa ejecución puede ser una llamada a una API. Es decir: al final todo sigue siendo **texto generado** que un compilador/intérprete ejecuta — no hay magia adicional.

El agente añade un **bucle de ejecución (agent loop)**: guarda la tarea en contexto, ejecuta pasos, y periódicamente valida esos pasos contra la tarea original para decidir si ya se cumplió o si faltan pasos. Se apoya en **memoria de corto y largo plazo**.

### 2.2 Frameworks de código para agentes
Mencionados: CrewAI, LangChain/LangGraph, y el framework de esta charla, **ADK**. Todos proveen gestión de memoria/contexto, algún tipo de RAG, y conexión a múltiples proveedores de modelos. Son frameworks *de código*: requiere escribir Python (u otro lenguaje soportado).

### 2.3 ADK (Agent Development Kit) — Google
Framework open-source de Google, disponible en **Python, Go, Java y TypeScript**. Tres tipos de agente:
1. **LLM Agent**: comportamiento guiado por instrucciones en lenguaje natural.
2. **Workflow Agent**: comportamiento predefinido — **Sequential** (ejecuta uno tras otro), **Parallel** (dispara todos a la vez), **Loop** (repite hasta cumplir una condición o alcanzar un máximo de reintentos).
3. **Custom Agent**: se escribe directamente el código del bucle de razonamiento — máximo control, uso poco frecuente, reservado para necesidades muy puntuales.

**Tools**: built-in (búsqueda de Google, conexión a RAG de Google Cloud como Vertex AI Search), de terceros (p. ej. tools definidas en LangChain), o funciones Python propias — cada tool documenta con su docstring qué argumentos recibe y devuelve, información que el agente usa para decidir cómo invocarla.

**Callbacks**: puntos de intercepción antes/después de cada evento — antes/después de llamar al modelo, antes/después de llamar a una tool, antes/después de ejecutar el agente. Permiten loggear, transformar la entrada/salida, o implementar telemetría personalizada.

**Contexto de ejecución**: incluye un `ToolContext` (información disponible durante la ejecución de una tool específica, p. ej. el ID de sesión) y una **sesión** (un JSON con el historial/estado de la conversación actual, consultable por el agente en cualquier momento).

### 2.4 Protocolos complementarios
- **MCP**: expone tres tipos de recursos — *tools* (funciones/conexiones a datos ya construidas), *resources* (archivos, imágenes) y *prompts* (templates reutilizables con tareas predefinidas).
- **A2A**: comunicación entre agentes que **no** están en la misma máquina/contexto de ejecución — se identifican mediante un **Agent Card** (JSON de "tarjeta de presentación": qué hace el agente, quién es, qué skills tiene).
- Mencionado brevemente: existen protocolos adicionales para casos específicos (p. ej. de pago entre agentes).

### 2.5 Cuándo usar un agente (criterio de Google, coincide con Blend 360)
Escenarios que requieren **análisis, razonamiento o introducir pensamiento** → candidatos ideales para agente. Escenarios resolubles de forma **programática/determinista** → no conviene un agente (consume más cómputo y agrega comportamiento no determinístico donde no se necesita).

### 2.6 Skills en ADK
Una skill es una **receta reutilizable**: un playbook/lista de pasos para ejecutar una tarea de forma específica (análoga al concepto que usó Blend 360 en su demo 1, pero aquí formalizada dentro del framework). Puede incluir código Python asociado. Se usa cuando el procedimiento para cumplir una tarea ya se conoce de antemano (ejemplo: un manual de despliegue a producción, o de extracción de información con una estructura fija).

**Punto técnico relevante para optimizar contexto:** una skill **no se carga completa en la ventana de contexto del agente** — se carga progresivamente, solo cuando se necesita. Esto la hace preferible a incrustar tools directamente cuando un agente tiene muchas tareas procedimentales distintas: las tools pueden vivir dentro de las skills para aprovechar esa carga diferida.

### 2.7 Demo — agente sobre un dataset de misiones espaciales
Flujo mostrado (usando `agents-cli`, la CLI de Google para scaffolding de agentes ADK, instalada vía `uv`):

```bash
uvx google-agents-cli setup
agents-cli create codefest26 --prototype --yes
cd codefest26
agents-cli playground   # abre una UI web local para probar el agente
```

El proyecto generado ya trae una estructura ADK completa (agente base, tool de ejemplo `get_weather`, configuración de modelo Gemini). Sobre esa base se agregó:
- Un **modelo Pydantic** que mapea la estructura del CSV (dataset de misiones espaciales de Kaggle: `mission_id`, `target_type`, etc.).
- Una **tool custom** que lee ese CSV y responde preguntas específicas sobre él (p. ej. "¿cuántas misiones tuvieron como objetivo asteroides?", "¿qué misiones tuvieron como destino Marte?").

El agente elige la tool correcta según la pregunta y **responde solo con la información contenida en esa fuente**, no con lo aprendido en entrenamiento — el mismo principio de RAG/grounding aplicado con una tool custom en vez de un vector store. Se mencionó que ese mismo agente podría conectarse a un RAG real (Vertex AI Search) en vez de a un archivo plano, sin cambiar el resto del diseño.

### 2.8 Evaluación de agentes en ADK
La estructura generada por `agents-cli` incluye tres carpetas de pruebas:
- **Unit tests**: validan estructura de código (p. ej. que el modelo Pydantic esté bien definido) — no prueban el comportamiento del agente.
- **Integration tests**: pruebas clásicas de integración.
- **Evalsets**: prueban el comportamiento real del agente — trayectoria (¿llamó la tool correcta con los argumentos correctos?) y calidad de respuesta, vía **LLM-as-judge** configurado contra **rúbricas explícitas** (en la demo: *relevancia* — resuelve la necesidad del usuario — y *utilidad* — aporta información útil).

```bash
agents-cli eval run             # corre todos los evalsets del proyecto
agents-cli eval run --evalset tests/eval/evalsets/space_missions.evalset.json
```

Se puede seguir agregando casos al evalset a medida que aparecen preguntas nuevas o comportamientos no cubiertos, garantizando que las mejoras no rompan la calidad ya validada en casos anteriores (regresión).

### Conceptos previos necesarios
- **RAG / vector stores** (FAISS ya en el stack del proyecto) — la tool custom de la demo es un RAG simplificado sobre un CSV; el mismo patrón aplica al corpus real del equipo.
- **LLM-as-judge con rúbricas calibradas** — ya visto en [[etapa2-sesion1-resumen]] (DeepEval) y en la Parte 1 de esta sesión (Blend 360); ADK aplica el mismo patrón con su propio formato de configuración.

### Conceptos que se profundizan en próximas sesiones
- **LangGraph** (miércoles) dará el contraste directo frente a ADK y CrewAI para la decisión de framework aún pendiente en `CLAUDE.md`.
- **Estrategia de datos multiagente** (miércoles, Tito Neira) — relevante para decidir cómo exponer el corpus (RAG vectorial vs. grafo, ya construidos por el equipo) a un agente vía tool o vía RAG nativo del framework.

### Q&A relevante para el proyecto
Pregunta del moderador (FAC) sobre cómo evaluar un agente montado **sobre modelos vectoriales o de grafos ya construidos** (exactamente el caso del equipo). Recomendación de Andrés Pérez (Google):
1. Definir primero, con precisión, el **caso de uso** — determina el diseño del set de evaluación, no al revés.
2. Antes de la evaluación, tener control de **qué preguntas debería poder responder el agente** (y cuáles no).
3. Usar un **LLM "gatekeeper"** antes del agente principal: valida si la pregunta entrante es apropiada/resoluble por la arquitectura, y si no lo es, la redirige o la rechaza en vez de dejar que el agente principal improvise.
4. El evalset debe cubrir la mayor cantidad posible de casos de uso reales, con **rúbricas relevantes al dominio** (se mencionaron explícitamente precisión y recall como ejemplo de criterios a incluir, no solo relevancia/utilidad genéricas).

---

## Glosario rápido de esta sesión
- **Harness:** capa operativa completa alrededor del modelo (contexto, conectores, tools, validación, observabilidad) que le permite operar de forma segura y repetible.
- **MAST:** Multi-Agent System Failure Taxonomy — taxonomía empírica de 14 modos de falla en sistemas multiagente, agrupados en 3 categorías (Cemri et al., 2025).
- **Golden set:** conjunto de casos de referencia (derivados de trazas reales, no genéricos) usado para validar un sistema y detectar regresiones.
- **LLM-as-judge:** modelo (idealmente más avanzado que el evaluado) que puntúa respuestas contra rúbricas explícitas; debe calibrarse contra ejemplos etiquetados a mano para controlar sus propios sesgos.
- **Human-on-the-loop vs. human-in-the-loop:** supervisión asíncrona/posterior (acciones reversibles) vs. aprobación síncrona previa a la acción (acciones irreversibles/alto riesgo).
- **MCP vs. A2A:** MCP conecta un agente con herramientas/datos; A2A conecta un agente con otro agente (posiblemente remoto).
- **Skill (ADK):** procedimiento reutilizable, cargado en el contexto solo cuando se necesita (carga diferida), a diferencia de una tool que se declara de antemano.
- **DOE:** framework de 3 capas (Directive – Orchestration – Execution) para separar instrucciones en lenguaje natural, enrutamiento inteligente, y ejecución determinística.
- **AI-DLC:** metodología de AWS para integrar agentes como participantes activos del ciclo de vida de desarrollo de software (no solo el humano).

## Documentación y recursos citados

| Herramienta / referencia | Enlace | Para qué sirve |
|---|---|---|
| MAST — "Why Do Multi-Agent LLM Systems Fail?" | https://arxiv.org/abs/2503.13657 | Origen de las cifras 41.8% / 36.9% citadas en la charla |
| Langfuse — self-hosting | https://langfuse.com/self-hosting | Desplegar observabilidad de agentes vía Docker/Kubernetes |
| Langfuse (repo) | https://github.com/langfuse/langfuse | Código fuente, integración por decoradores |
| DOE Framework | https://github.com/jaseemts/doe | Arquitectura de 3 capas Directive-Orchestration-Execution |
| AWS AI-DLC | https://aws.amazon.com/blogs/devops/open-sourcing-adaptive-workflows-for-ai-driven-development-life-cycle-ai-dlc/ | Metodología de desarrollo con agentes como participantes activos |
| Google ADK — Quickstart Python | https://google.github.io/adk-docs/get-started/python | Instalación y primer agente con `adk create` |
| Google Agents CLI | https://google.github.io/agents-cli/ | CLI de scaffolding/evaluación usada en la demo (`agents-cli create`, `agents-cli eval run`) |
| ADK — Evaluation Guide | https://google.github.io/adk-docs/evaluate/criteria/ | Rúbricas, trayectoria y configuración de `eval_config.json` |
| Model Context Protocol (MCP) | https://modelcontextprotocol.io | Especificación del protocolo de conexión agente↔herramientas |
| Agent2Agent (A2A) | https://a2a-protocol.org | Especificación del protocolo de comunicación agente↔agente |

## Recomendaciones prácticas dadas en la sesión
- No asumir multiagente por defecto: aplicar el árbol de decisión (estructura estable → workflow; subtareas independientes → paralelo; decisión abierta → agente; acción irreversible → humano en el loop) antes de diseñar.
- Para cada agente, escribir explícitamente las 5 preguntas de diseño (propósito, entrada, salida, criterios de éxito, autoridad) más "qué NO debe saber".
- Empezar siempre por el patrón de organización más simple; añadir paralelismo o supervisión solo cuando se observe la necesidad, no por anticipación.
- Instrumentar un ID de correlación desde el día uno — la observabilidad es barata de agregar y cara de reconstruir después.
- Diseñar el set de evaluación a partir del caso de uso real, con un filtro (gatekeeper) de preguntas válidas antes del agente principal, y rúbricas específicas del dominio (no solo relevancia/utilidad genéricas).
- Definir el dominio permitido explícitamente para evitar que el usuario saque al agente de su tarea con una excusa social o emocional.
