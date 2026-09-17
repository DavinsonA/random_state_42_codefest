# CODEFEST Ad Astra 2026 — Etapa 2, Sesión 1 (7 de septiembre)

Resumen de conceptos. Cubre solo lo explicado en esta sesión: apertura institucional de la fase pre-presencial, la charla **"De la información al conocimiento: análisis y anticipación en la era de la IA"** (Tcnel. Alexandra Zavala López, FAC) y **"Arquitectura detallada de la infraestructura del reto"** (Aval Digital Labs — Steven Jerena y Diego Alejandro Buitrago). Es la primera sesión de una segunda etapa de conferencias, distinta de las sesiones 1–5 de julio (fase virtual/clasificatoria): esta etapa ya está orientada a la resolución del **reto presencial** (18–19 de septiembre, Uniandes).

---

## Parte 0 — Contexto y agenda de la etapa

- Semana de conferencias: **7 al 11 de septiembre, 17:00–19:00**.
- **20 equipos clasificados** (+3 backup) de **11 instituciones** en **7 ciudades** (Bogotá con mayor participación; también Cartagena, Bucaramanga, Villavicencio, Tunja, Medellín, Cali). Universidad Icesi está entre las clasificadas.
- Delegaciones observadoras: EE. UU., Perú, Argentina, Chile (Chile presentó propuesta con desempeño destacado).
- El **handbook técnico detallado del reto** solo se entrega el 18 de septiembre; las conferencias de esta semana son preparación conceptual y de herramientas, no la especificación del reto.

**Agenda completa de la semana** (útil como mapa de "qué viene"):

| Día | Charla 1 | Charla 2 |
|---|---|---|
| Lun 7 | De la información al conocimiento (FAC) | Arquitectura de infraestructura del reto (Aval Digital Labs) — *esta sesión* |
| Mar 8 | Agentes que colaboran, sistemas que resuelven (Blend 360) | Desarrollo, integración y evaluación de agentes con ADK (Google) |
| Mié 9 | Arquitecturas agénticas con LangChain y LangGraph (Uniandes) | Estrategia de datos para arquitectura multiagente (Nodo de Innovación Uniandes) |
| Jue 10 | AgenticRAG: dentro de la mente de un agente (Conecto) | Visualizaciones con datos georreferenciados (Uniandes) |
| Vie 11 | Plataforma de inteligencia geoespacial (Telespacio) | Arquitectura de un AI harness robusto con Bantor Hub (Bantor) |

---

## Parte 1 — De la información al conocimiento (Tcnel. Alexandra Zavala, FAC)

### 1.1 Superioridad de la información vs. sobrecarga de información
Tener más datos no equivale a tener más conocimiento. Cita a **Herbert Simon (1971)**: la riqueza de información consume la atención de quien la procesa, y el desempeño analítico deja de ser lineal respecto al volumen de datos disponible. Esto se conoce como **information overload**. La superioridad de la información no está en adquirir datos, sino en la capacidad de **transformarlos en conocimiento que anticipe riesgos**.

### 1.2 Evaluación del ambiente de información
La charla usa un marco (atribuido genéricamente a la OTAN) para evaluar el **ambiente de información** antes de fusionar fuentes:
- **Calidad de la fuente**: propia, de terceros de calidad desconocida (p. ej. redes sociales, con riesgo de desinformación), diplomática, o pública (con sesgo de perspectiva).
- **Cuatro dimensiones del dato**: velocidad de crecimiento, variedad de tipos, veracidad/confiabilidad, volumen.

> **Aproximación (no confirmada en la charla):** estas cuatro dimensiones coinciden con el marco clásico de **Big Data — las "4 V" (Volume, Velocity, Variety, Veracity)**, ampliamente documentado en literatura de gestión de datos. La ponente no usó ese nombre explícitamente; es un mapeo mío para ubicar el concepto en un marco más conocido.
> El "marco de la OTAN" al que se refiere corresponde probablemente al concepto de **Information Environment Assessment (IEA)**, descrito en la doctrina **AJP-10.1 — Allied Joint Doctrine for Information Operations**. Es una inferencia de contexto, no una cita literal de la charla.

### 1.3 De la información a la decisión (doctrina militar)
Cadena: **dato → información → relación/patrón → conocimiento → decisión**. Se aplica en tres líneas:
1. **Comando y control (C2)** de operaciones y activos en tiempo real.
2. **Evaluación del entorno operacional** antes de desplegar medios (identificar actores, relaciones, tensiones).
3. **Planeamiento de respuesta a crisis** (no solo conflicto armado: incluye desastres naturales, como el terremoto reciente mencionado en la charla).

### 1.4 Vigilancia tecnológica: metodología de revisión sistemática
La FAC hizo una revisión de literatura con el **método de Barbara Kitchenham** (revisión sistemática de literatura / SLR) para catalogar tecnologías usadas en el mundo para apoyo a la decisión militar. Resultado: **32 métodos y técnicas** — 22 orientadas a análisis de información, 10 a planeamiento operacional (más otras centradas en datos). De proyectos prácticos (no solo teoría) identificaron **6 usos de IA en entornos militares**: identificación de blancos, plataformas de armas, simulación/entrenamiento, procesamiento de datos, ciberseguridad, y asistencia médica remota. El foco de mayor avance práctico: **procesamiento de datos y ciberseguridad**.

Esto es directamente relevante para el proyecto: el sistema que el equipo construye (extracción de entidades/relaciones/eventos desde NLP + visión + fusión de datos heterogéneos) es exactamente el tipo de tecnología que esta vigilancia identificó como aplicable a análisis de información militar — no es un enfoque inventado, es un patrón con literatura y proyectos previos.

### 1.5 Ciberseguridad en la industria aeronáutica — cronología de incidentes

| Año | Incidente (resumen) | Categoría |
|---|---|---|
| 2015 | Denegación de servicio sobre sistema de planificación de vuelos (LOT) | Interrupción de operación |
| 2016 | Defacement de check-in en aeropuertos de Vietnam | Interrupción de operación |
| 2018 | Robo masivo de datos financieros/tarjetas de una aerolínea | Robo de datos |
| 2021 | Exposición de datos de ~4.5M pasajeros | Robo de datos |
| 2022 | Ransomware sobre SpiceJet | Secuestro de datos |
| 2023 | Ransomware + exfiltración de cadena logística de repuestos | Secuestro de datos + cadena de suministro |
| 2024 | Incidente global CrowdStrike (no dirigido al sector, pero propagado a aeropuertos) | Efecto colateral de terceros |
| 2025 | Ingeniería social con exfiltración vía plataforma en la nube | Ingeniería social |

Patrón: el riesgo se mueve de "ralentizar la operación" (2015–2016) a "robo masivo de datos" (2018–2021) a "secuestro con fines financieros" (2022+). La causa estructural: la industria aeronáutica depende de **terceros y cadena de suministro**, no solo de sus propios sistemas, lo que amplía la superficie de ataque.

**Dato citado en la charla:** tiempo medio de permanencia no detectada de un atacante ≈ 14 días (atribuido a informe de Google/Mandiant).
> **Verificación:** el reporte oficial es el **Mandiant M-Trends**. Las cifras publicadas de *dwell time* global mediano varían por año: 10 días (2023), 11 días (2024, reportado en M-Trends 2025), 14 días (2025, reportado en M-Trends 2026). El valor "14 días" citado en la charla coincide con la cifra más reciente publicada (M-Trends 2026), aunque la charla no especificó el año del informe.

### 1.6 De dato heterogéneo a conocimiento estructurado
Idea central: **la misma lógica de fusión de señales/imágenes de sensores** (usada en ediciones previas del CODEFEST) **aplica a datos heterogéneos de texto/observatorios**. El reto de este año entregó datos de **21 fuentes de observatorios de defensa** en distintos idiomas y países, cubriendo tres fenómenos: uso de IA en entornos militares, amenazas espaciales, y dinámicas de fronteras en LATAM/Caribe. La tecnología para esto (fusión de datos, extracción de eventos, NLP + visión artificial + visualización) **ya existe**; el objetivo del reto no es inventarla sino generar **capacidad propia y soberanía tecnológica**, no dependencia externa.

**Ejemplo mostrado (video, Japón):** un sistema tipo Palantir de apoyo a decisión para respuesta a desastres (terremoto/inundación, sept. 2024), consolidando datos personales dispersos entre gobiernos locales bajo controles de acceso basados en roles y protección de datos personales (con participación de una comisión de protección de datos y abogados). Se usó como ejemplo de **uso dual** (defensa ↔ gestión de crisis civil) de plataformas de fusión de información.

### Conceptos previos necesarios (de sesiones anteriores)
- **RAG, arquitecturas multiagente (jerárquica, mesh, blackboard, workflow)** — sesión 1 de julio. La charla de hoy da el *por qué* institucional de esas arquitecturas: fusionar fuentes heterogéneas para producir conocimiento accionable.
- **Fusión de fuentes heterogéneas y extracción de eventos** ya estaba anticipada en sesión 1 ("el detalle técnico se profundiza en sesiones posteriores") — esta sesión aterriza el *para qué* de dominio; el detalle técnico llega el jueves con Conecto (AgenticRAG).

### Conceptos que se profundizan en próximas sesiones
- **AgenticRAG** (Conecto, jueves) — el mecanismo técnico de RAG dentro de un agente.
- **Estrategia de datos para multiagente** (Nodo de Innovación Uniandes, miércoles) — cómo diseñar el pipeline de ingesta para las 21 fuentes.
- **Visualización georreferenciada** (Uniandes, jueves) e **inteligencia geoespacial** (Telespacio, viernes) — relevante directamente para el workstream de Juan José (Data & Geo Engineer).

---

## Parte 2 — Arquitectura de infraestructura del reto (Aval Digital Labs)

### 2.1 Flujo general
Cambio respecto a ediciones anteriores: **no hay ambiente cloud provisto para desarrollo**. El flujo es:

```
Máquina local del equipo (código, pruebas de agentes)
        │  llamadas a LLM
        ▼
   LiteLLM Gateway  ──────────────►  Amazon Bedrock (solo modelos open-source)
        │
        │  una vez el equipo tiene una solución funcional localmente
        ▼
   Coolify (deploy Docker desde GitHub, URL pública)
        │
        ▼
   Entorno de evaluación de jurados (pipeline DeepEval + pipeline de consumo)
```

**Restricción clave:** los modelos disponibles en el gateway son **exclusivamente open-source** (no comerciales), por condiciones de entornos militares — aunque se sirven a través de una nube (Bedrock) por practicidad de acceso, no por ser modelos propietarios de AWS.

### 2.2 LiteLLM — AI Gateway
Un **gateway unificado**: expone un único formato de API (estilo OpenAI) sobre múltiples modelos fundacionales que, por debajo, tienen formatos de invocación distintos. Provisto por equipo:
- Un **endpoint** único.
- Una **API key por equipo**.
- Un **model ID** por modelo (se cambia el modelo solo cambiando ese parámetro).
- **Presupuesto de tokens/costo por equipo** (no ilimitado; agotarlo trae penalidad). El presupuesto se asigna a nivel de costo del modelo fundacional, no de cantidad fija de tokens — modelos más grandes consumen presupuesto más rápido.
- **Dashboard de consumo** casi en tiempo real (tokens, costo, presupuesto restante).

Ejemplo de invocación (formato OpenAI-compatible, típico de un proxy LiteLLM):

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://<litellm-gateway-endpoint>",
    api_key="<team-api-key>",
)

response = client.chat.completions.create(
    model="<model-id-from-handbook>",
    messages=[{"role": "user", "content": "..."}],
)
print(response.choices[0].message.content)
```

Documentación oficial: [docs.litellm.ai — Proxy Quick Start](https://docs.litellm.ai/docs/proxy/quick_start) · [Virtual Keys](https://docs.litellm.ai/docs/proxy/virtual_keys) (gestión de API keys por equipo/desarrollador).

### 2.3 Coolify — PaaS de despliegue
PaaS **self-hosted, open-source**, alternativa a Heroku/Vercel/Netlify basada en contenedores Docker. Flujo:
1. Generar una **llave SSH desde Coolify** y cargarla en el repositorio de GitHub del equipo.
2. Hacer push del código (con `Dockerfile` en la raíz) a una rama.
3. En Coolify, apuntar a esa rama y elegir el tipo de build (Dockerfile custom o genérico).
4. Coolify aprovisiona infraestructura, construye el contenedor y genera una **URL pública**.

Además de aplicaciones, permite desplegar **bases de datos** (estructuradas o vectoriales) desde un catálogo de un clic (Postgres, Redis, MariaDB, etc.) o vía Dockerfile custom. Puntos evaluables mencionados explícitamente:
- **Variables de entorno**: no hardcodear credenciales/información sensible en el código; configurarlas en Coolify. Esto es calidad de código y **se califica**.
- **Logs**: cada deploy genera logs de build y de runtime, útiles para debug (incluyendo con agentes de IA vía MCP de Coolify).
- **Reinicio vs. borrado**: preferir reiniciar contenedores fallidos antes que recrearlos desde cero.

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv --break-system-packages && uv sync --frozen
COPY . .
CMD ["uv", "run", "uvicorn", "src.ui.app:app", "--host", "0.0.0.0", "--port", "8000"]
```
```bash
# .env (nunca commitear; configurar como variables de entorno en Coolify)
LITELLM_API_KEY=sk-...
LITELLM_BASE_URL=https://...
DATABASE_URL=postgresql://...
```

Documentación oficial: [coolify.io/docs](https://coolify.io/docs) · [Instalación / self-hosted](https://coolify.io/docs/get-started/installation) · repo: [github.com/coollabsio/coolify](https://github.com/coollabsio/coolify).

### 2.4 DeepEval — framework de evaluación de agentes
Automatiza la evaluación de la solución de cara al jurado, sobre dos ejes:
- **Trayectoria (trace)**: evalúa la ruta completa del agente frente a una "ruta ideal" para llegar al objetivo — penaliza iteraciones innecesarias.
- **Componentes (spans)**: cada paso individual del agente (llamada a LLM, tool call, retrieval) se evalúa por separado — toxicidad, comprensibilidad, adherencia al tono definido en la guía.

Se combina con **evaluación humana** y un criterio de **costo-efectividad**: no basta con usar el modelo más potente si el costo no se justifica frente al presupuesto de tokens del gateway.

> **Correspondencia técnica confirmada en la documentación de DeepEval:** lo que la charla describe como "evaluar la traza completa" corresponde a las **trajectory metrics** (`TaskCompletionMetric`, `StepEfficiencyMetric`, `PlanAdherenceMetric`, `PlanQualityMetric`), y lo que describe como evaluar "cada paso" corresponde a **component-level metrics sobre spans** individuales dentro del trace.

```python
from deepeval import evaluate
from deepeval.test_case import LLMTestCase
from deepeval.metrics import TaskCompletionMetric

test_case = LLMTestCase(
    input="Analiza actividad de deforestación reportada en la región X",
    actual_output=agent_response,
    retrieval_context=retrieved_docs,
)
evaluate(test_cases=[test_case], metrics=[TaskCompletionMetric(threshold=0.7)])
```

Documentación oficial: [deepeval.com/docs/getting-started-agents](https://deepeval.com/docs/getting-started-agents) · [Evaluación por componentes (spans)](https://deepeval.com/docs/evaluation-component-level-llm-evals) · [Métricas de trayectoria](https://deepeval.com/docs/metrics-introduction).

### Conceptos previos necesarios
- **Docker / docker-compose**, ya en el stack del proyecto (`CLAUDE.md`).
- **REST APIs y variables de entorno / gestión de secretos** — base para entender por qué Coolify penaliza credenciales hardcodeadas.
- **Flujo Git de rama + push** para disparar deploys.
- **Licenciamiento open-source vs. propietario de modelos LLM** — el mismo criterio que ya aplica el equipo a dependencias de software (Apache 2.0 / sin copyleft fuerte) ahora aplica también a los modelos: solo open-weight en el gateway del reto.
- **Tracing/observabilidad de agentes** (LangSmith/Langfuse, ya listado como stack en el proyecto) — es el mismo concepto de *spans* que usa DeepEval, aplicado ahora a evaluación en vez de solo debug.

### Conceptos que se profundizan en próximas sesiones
- **Google ADK** (martes) y **LangGraph** (miércoles, Uniandes) — información directamente relevante para la decisión de framework de agentes que el proyecto tiene pendiente ("A DEFINIR" en `CLAUDE.md`, entre LangGraph, CrewAI y Claude Agent SDK).
- **Estrategia de datos para multiagente** (miércoles) — probablemente aterrizará cómo alimentar el pipeline de ingesta que corre sobre Coolify/bases de datos desplegadas ahí.

---

## Glosario rápido de esta sesión
- **Information overload:** más datos no implica más conocimiento; la atención y capacidad de procesamiento no escalan linealmente con el volumen (Simon, 1971).
- **Information Environment Assessment (aproximado):** evaluación de fuentes de información por calidad, velocidad, variedad, veracidad y volumen antes de fusionarlas.
- **Dwell time:** tiempo que un atacante permanece sin ser detectado en un sistema comprometido.
- **SLR (Systematic Literature Review):** metodología de revisión de literatura reproducible y auditable (Kitchenham & Charters, 2007).
- **AI Gateway:** capa intermedia que expone un único formato de API sobre múltiples proveedores/modelos de LLM (LiteLLM).
- **PaaS basado en contenedores:** plataforma que automatiza el aprovisionamiento y despliegue de contenedores Docker desde un repositorio Git (Coolify).
- **Span / trace:** unidad mínima de ejecución de un agente (una llamada a LLM, un tool call) y la secuencia ordenada de todas ellas, respectivamente — unidad de evaluación en DeepEval.
- **Cost-effectiveness (agentes):** criterio de evaluación que balancea calidad de resultado contra consumo de tokens/presupuesto.

## Documentación y recursos citados

| Herramienta / referencia | Enlace | Para qué sirve |
|---|---|---|
| LiteLLM Proxy | https://docs.litellm.ai/docs/proxy/quick_start | Levantar/consumir el gateway unificado de LLMs |
| LiteLLM Virtual Keys | https://docs.litellm.ai/docs/proxy/virtual_keys | Gestión de API keys y control de gasto por equipo |
| Coolify Docs | https://coolify.io/docs | Deploy de apps/DBs Dockerizadas desde GitHub |
| Coolify (repo) | https://github.com/coollabsio/coolify | Código fuente, self-hosting |
| DeepEval — Agentes | https://deepeval.com/docs/getting-started-agents | Evaluación de trayectoria y componentes de agentes |
| DeepEval — Spans | https://deepeval.com/docs/evaluation-component-level-llm-evals | Evaluación por componente individual |
| DeepEval — Métricas | https://deepeval.com/docs/metrics-introduction | Catálogo de métricas de trayectoria y componente |
| Kitchenham & Charters (2007) | Technical Report EBSE-2007-01, Keele University | Metodología de revisión sistemática de literatura |
| Mandiant M-Trends | https://cloud.google.com/blog/topics/threat-intelligence/m-trends-2025/ | Cifras de dwell time citadas en la charla |
| NATO AJP-10.1 (aproximación) | Allied Joint Doctrine for Information Operations | Marco de referencia probable para "evaluación del ambiente de información" |

## Recomendaciones prácticas dadas en la sesión
- Monitorear activamente el consumo de tokens del gateway y planificarlo por iteración; agotarlo trae penalidad.
- No hardcodear credenciales — usar variables de entorno en Coolify; es un criterio de calificación explícito.
- Preferir reiniciar contenedores antes que recrearlos ante fallos.
- Diseñar pensando en costo-efectividad, no solo en usar el modelo más potente disponible: DeepEval evalúa ambos ejes.
- Revisar la guía de usuario del reto antes de fijar el formato del endpoint de evaluación — desviarse de las reglas documentadas genera fricción en la evaluación automática.
