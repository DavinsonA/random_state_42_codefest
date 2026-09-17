# CODEFEST Ad Astra 2026 — Etapa 2, Sesión 5 (11 de septiembre) — cierre del ciclo

Resumen de conceptos. Cubre solo lo explicado en esta sesión: **"Plataformas de inteligencia geoespacial"** (Raúl Silva Gómez, Telespazio), **"¿Y si la IA pudiera ver la Tierra más allá del prompt? Arquitectura de un AI harness robusto usando Vantor Hub"** (Jofre Manchola, Vantor/antes Maxar), y **"AgenticRAG: dentro de la mente de un agente — LLMs, Tools y MCP"** (Tomás Acosta y Luis Fernando Ruiz, Conecto — reprogramada desde la sesión 4). Es la última sesión del ciclo pre-presencial; cierra con logística oficial del reto del 18–19 de septiembre.

---

## Parte 0 — Logística y reglas oficiales del reto presencial

- De **100 equipos inscritos**, **20 clasificaron** a la fase presencial (18–19 de septiembre, Ed. Mario Laserna, Uniandes).
- Formato: **jornada continua de 24 horas**; el reto específico se publica al inicio, no antes. Al final, cada equipo tiene **5 minutos de pitch + 3 minutos de preguntas del jurado (8 min total)**. Premiación el 19 de septiembre.
- **Entregables obligatorios**: presentación/demo en vivo, **repositorio público de GitHub con licencia open source permisiva** (no restrictiva — la licencia restrictiva es motivo de **descalificación**), documentación técnica en el repositorio. El código debe ser abierto **a perpetuidad**, modificable, con atribución del autor original preservada, y toda librería/recurso de terceros debe tener licencia compatible.
- **Asistencia**: los 4 integrantes deben asistir presencialmente y haber asistido al ciclo de conferencias virtuales; la inasistencia injustificada puede descalificar al equipo, a criterio del comité.
- **Requisito de cómputo**: mínimo **dos computadores portátiles operativos** por equipo.
- **Conducta prohibida (todas causal de descalificación)**: interferir con otros equipos, suplantar identidad, incluir código malicioso, información falsa o que viole propiedad intelectual de terceros, contenido que incite violencia/discriminación/atente contra el buen nombre de personas o instituciones, licencias incompatibles con open source, o contenido publicitario/político/ideológico ajeno a los organizadores.
- Recomendación logística: llegar al campus **desde las 4:00 p.m. del viernes 18** para el registro y entrega del kit (toma ~10–15 min por equipo, son 20 equipos).

---

## Parte 1 — Plataformas de inteligencia geoespacial (Raúl Silva Gómez, Telespazio)

### 1.1 Telespazio, en contexto
Empresa italiana fundada en **1961** (+60 años de trayectoria), joint venture entre **Leonardo (67%)** y **Thales (33%)**. Opera en explotación de geoinformación satelital, telecomunicaciones satelitales y operación de segmento terrestre/espacial. El punto de la charla no es la tecnología en abstracto — es que estos servicios de geointeligencia **existen desde antes** del boom actual de IA; lo que cambió con IA + big data + nube es la **velocidad de respuesta** y el **volumen** que se puede explotar.

### 1.2 Catálogo de plataformas mostradas (cada una responde una pregunta vertical distinta)
| Plataforma | Enfoque |
|---|---|
| **SEonSE** (Smart Eyes on SEas) | Vigilancia del dominio marítimo |
| **braINT** | Explotación masiva de imágenes para inteligencia de actividad en superficie (defensa) |
| Plataformas agrícolas | Proyección de variables agronómicas sobre grandes volúmenes de datos |
| Plataforma de detección de cambios por radar | Monitoreo ambiental y de infraestructura |
| **MapCy** (con el subsistema **FLOOD**) | Cartografía de emergencia de altísima demanda/baja latencia (ej. inundaciones) |

> Los nombres "SEonSE" y "braINT" en el audio sonaban como "SEONC" y "Braint" — corresponden a productos reales y públicamente documentados de Telespazio/e-GEOS. "IMapsy"/"Mapsy" corresponde a **MapCy**, su plataforma de cartografía rápida de emergencia.

### 1.3 MapCy + FLOOD: el ejemplo del terremoto/inundación
El subsistema FLOOD es un **modelo hidrológico** alimentado con datos meteorológicos de lluvia, que simula la inundación de una ciudad (la calidad depende del modelo de elevación del terreno disponible). Lo distintivo: el sistema de IA asociado **busca en redes sociales, en tiempo real, contenido georreferenciado** (fotos, videos, publicaciones) relacionado con el evento, y usa esa evidencia para **actualizar la condición espacial de la simulación** — no es solo un modelo hidráulico corriendo aislado, se retroalimenta con evidencia ciudadana en vivo. (Corresponde al concepto documentado públicamente como "Enhanced Flood Footprint": combinar mediciones meteorológicas, imágenes satelitales, modelos hidrológicos y marcadores de redes sociales.)

### 1.4 braINT en detalle
Pipeline: sobre un enorme conjunto de imágenes de un área, la plataforma **decide automáticamente** qué tipo de dato de observación de la Tierra usar (de archivo o encargar captura nueva) y qué preprocesamiento aplicar según la pregunta planteada; luego hace **análisis multitemporal**. Tres ejemplos de producto mostrados:
1. **Patrón de vida en una base**: detección automática de vehículos (aéreos/terrestres) a lo largo de una secuencia histórica de imágenes, clasificados por dinámica temporal — permite saber qué aeronaves estuvieron en qué lugar y cuándo.
2. **Inteligencia de inventario petrolero**: la variación del nivel del techo flotante de los tanques de una refinería, vista en secuencia de imágenes, permite estimar el stock de crudo y detectar disrupciones logísticas.
3. **Inteligencia logística clásica**: ocupación de parqueaderos o patios de contenedores a lo largo del tiempo.

El output final en todos los casos es un **reporte de inteligencia (IMINT) generado de forma asistida**, mucho más rápido que el proceso manual tradicional.

### 1.5 SEonSE en detalle — vigilancia marítima multisensor
Outputs: detección de embarcaciones (radar u óptico), detección de manchas de petróleo, extracción cuantitativa de campos de viento/oleaje, y **detección de anomalías** (el núcleo de IA de la plataforma).

**Fuentes de posicionamiento de embarcaciones** (cada una cubre el punto ciego de la anterior):
- **AIS satelital**: transpondedor activo a bordo que reporta posición e identificación (matrícula única global) vía constelación dedicada. Problema: **se puede apagar**.
- **VMS**: similar al AIS pero para zonas costeras, no alta mar.
- **Imágenes nocturnas**: detectan la emisión de luz de una embarcación que no transmite AIS.
- **Geolocalización por radiofrecuencia**: se capta desde el espacio la emisión del radar marítimo propio de la embarcación (constelación dedicada a esto); permite identificarla aun con el AIS apagado, porque cada emisor de radio tiene una "firma" de onda característica.

**Constelaciones satelitales usadas**: COSMO-SkyMed (radar banda X, italiana — descrita como estado del arte comercial en radar), SAOCOM (radar banda L, argentina), Sentinel-1 (radar banda C, europea), y ópticas como Satellogic y BlackSky (revisita multidiaria).

**Tipos de imagen radar**: **ScanSAR** (resolución media/baja, 20–100 m, cobertura de cientos de km — para detección amplia en el dominio marítimo) vs. **Spotlight** (altísima resolución, foco puntual — para detalle de infraestructura, ej. un puerto completo).

### 1.6 Detección de anomalías — qué cuenta como "anómalo"
Aprendido estadísticamente sobre el histórico de rutas: entrada/salida de una **zona de exclusión** (ej. zona económica exclusiva), embarcación de **bandera extranjera** operando dentro de aguas de otro país (pesca ilegal), **cambio repentino de ruta**, **encuentro en altamar** entre dos embarcaciones, y **adulteración del AIS** (ej. una misma matrícula reportando tres posiciones lejanas casi simultáneamente — descartado como falla técnica cuando el patrón se repite solo en momentos específicos, lo que sugiere manipulación deliberada).

### 1.7 Caso real: monitoreo de una semana en la costa brasileña
Más de **800,000 mensajes AIS** y ~20 imágenes de radar analizadas. Hallazgos:
- Numerosas embarcaciones **detectadas por radar sin señal AIS correspondiente** — evidencia de que la fuente "colaborativa" (AIS) subestima significativamente la actividad real en el mar.
- Alertas por embarcaciones de bandera extranjera (norcoreana, otra bandera, palestina) dentro de la costa brasileña, y rutas cíclicas atípicas de embarcaciones no locales.
- Un caso de **correlación espacio-temporal** entre una mancha de petróleo detectada y los mensajes AIS de embarcaciones cercanas en tiempo y espacio a la toma de la imagen → generación automática de un **ranking de responsables potenciales del derrame** (relevante porque el derrame de petróleo puede ser un delito ambiental).

**Conclusión de la charla**: el valor de la IA aquí no es "ver" una imagen de radar (que es ruidosa y difícil de interpretar a simple vista) — es **correlacionar múltiples fuentes heterogéneas** (imagen + AIS + VMS + RF + luces nocturnas) en tiempo y espacio para producir inteligencia procesable.

### Conceptos previos necesarios
- Fuentes ópticas/radar (Sentinel-1/2, VIIRS, ECOSTRESS) — [[etapa2-sesion4-resumen]]. Esta charla es la aplicación operativa y a escala de esas mismas fuentes.

---

## Parte 2 — Arquitectura de un AI harness robusto con Vantor Hub (Jofre Manchola)

### 2.1 Aclaración de marca (importante para no confundirse en la documentación)
**Maxar se renombró Vantor en octubre de 2025.** El producto se llama **Vantor Hub**, pero el API sigue expuesto bajo el dominio `maxar.com` y buena parte de la documentación técnica todavía dice "Maxar" — en la práctica es lo mismo. (En el audio se transcribió como "Bantor"; el nombre correcto y verificado es **Vantor**.)

### 2.2 Capacidades del API de Vantor
Discovery, Streaming Maps, Raster Analytics, Vector Analytics, Ordering, Tasking. Imágenes de hasta 15–30 cm de resolución, más de 20 años de archivo, y un **mosaico base** de muy alto detalle usado como capa de fondo.

### 2.3 Idea central: "el LLM no ve nada"
Un modelo de lenguaje recibe/genera **texto**, no imágenes interpretadas semánticamente por sí mismo. El flujo real es: universo de millones de imágenes → **Discovery** filtra candidatas por metadata (nubosidad, fecha, área) según parámetros que el LLM tradujo de una pregunta en lenguaje natural → selección de un subconjunto reducido → **procesamiento bajo demanda** delegado al motor de análisis del propio API (no en el navegador, no por el LLM) → interpretación final por un experto humano. Cada caja de ese flujo es una herramienta específica, no una tarea que el LLM resuelva "pensando".

### 2.4 Estructura del harness — mismas piezas que Claude Code
Jofre construyó su harness desde cero con cuatro componentes, todos en **texto plano (Markdown)** — deliberado, porque los LLM trabajan muy bien con texto estructurado (títulos, negritas, bloques de código, links):
- **Agentes** (roles): arquitecto GIS, implementador/desarrollador, agente de especificaciones, agente de experiencia de usuario, experto en la plataforma Vantor, y **dos verificadores** que usan modelos distintos entre sí (uno con GPT, otro con un modelo gratuito) y distintos del que generó el código.
- **Skills**: contexto del CODEFEST (qué es, audiencia, tono a usar), despliegue automático (push → deploy en Vercel), y la habilidad de ajustar especificaciones.
- **Tools**: cualquier herramienta que el agente puede invocar (GitHub, Vercel, el API de Vantor, el LLM).
- **Hooks**: scripts deterministas, **no dependen del LLM**, que corren en momentos fijos del flujo.

### 2.5 Principio central: *spec-driven development*
No se escribe código directamente — se escriben **especificaciones** (objetivo, entradas/salidas, criterios de aceptación, cómo se verifica) y el LLM implementa a partir de ellas. **La calidad de la especificación determina la calidad del código resultante**, y es en escribir bien esa especificación donde realmente se invierte el tiempo (más que en "escribir prompts").

### 2.6 El ciclo cerrado generar → verificar → corregir
El agente que construye el código **nunca debe ser el mismo que lo evalúa** — la verificación cruzada entre modelos distintos da resultados más confiables. Este ciclo necesita una **condición de parada** (tope de iteraciones) para no agotar el presupuesto de tokens si el código nunca termina de cumplir la especificación.

### 2.7 Hooks explícitos usados en la demo
- **Validación de secretos**: corre en cada commit para evitar que una API key quede expuesta en un repositorio público por error de la IA.
- **Puntos de confirmación humana obligatoria**: para acciones destructivas (borrar archivos) o con costo monetario (subir un plan de facturación) — el agente **no** decide autónomamente ahí.
- **Telemetría**: registra llamadas y respuestas para análisis posterior — el objetivo no es "quemar menos tokens para parecer eficiente" ni "usar más tokens para parecer riguroso", sino **capturar información real** que después permita mejorar skills, agentes y elección de modelo.

### 2.8 Selección de modelo por rol, no por defecto
Usar el modelo más caro/capaz para las decisiones que requieren más "pensar" — definir arquitectura, mecanismos de despliegue, librerías, estrategia — y un modelo más barato para implementar una vez el plan ya está detallado. El verificador, además, debe usar un modelo distinto al que generó el código.

### 2.9 Resiliencia de demo (plan B), pensado desde el diseño
El harness guarda **consultas y resultados pregrabados** como caché local, para poder mostrar la aplicación funcionando aunque falle el API, el LLM o la conexión a internet durante una presentación en vivo — diseñado desde el principio, no improvisado.

### 2.10 Herramientas de desarrollo mencionadas
Jofre usó **Devin** para construir toda la aplicación (cero líneas de código escritas a mano). Mencionó su historia de marca: la herramienta que usó fue antes **Codeium**, luego **Windsurf**, y en 2025 Windsurf fue adquirida por **Cognition** (la empresa detrás de Devin) — hoy integrada al ecosistema Devin. Alternativas de pago mencionadas: Cursor, Codex. Alternativa **gratuita/económica recomendada** para quien no tenga licencia: **OpenCode**, una herramienta de código abierto para desarrollo agéntico (CLI + interfaz), punto de entrada equivalente a un archivo tipo `AGENTS.md` que orquesta agentes, skills y hooks.

### 2.11 Demo en vivo (resumen)
A partir de un ítem de su propio roadmap ("agregar herramientas de medida/dibujo al visor GIS"), con un prompt deliberadamente breve, el harness: piensa la especificación → define tareas y plan de verificación → escribe código → corre type-check, lint y build local → hace commit → push a GitHub → Vercel despliega automáticamente por el hook ya configurado → se prueba en vivo (medir distancia, dibujar un polígono, cambiar opacidad de capas) → detecta un bug menor en la herramienta de dibujo por su cuenta → itera, corrige, y vuelve a desplegar — sin intervención humana en el código en ningún punto.

### 2.12 Mensaje central de la charla
**"El arnés pone en cintura al LLM"** — un buen harness importa más que usar el modelo más potente disponible; muchas veces se recurre a un modelo más caro para compensar un harness deficiente. Recomendación explícita para el reto: empezar a construir la arquitectura agéntica (agentes, skills, hooks) **antes** de conocer el reto el 18 de septiembre, para ganar velocidad ese día.

### Conceptos previos necesarios
- **Harness, human-in-the-loop, verificación cruzada de modelos** — [[etapa2-sesion2-resumen]] (Blend 360) y [[etapa2-sesion3-resumen]] (interrupt/Command de LangGraph). Los hooks de confirmación humana de Jofre son el mismo patrón aplicado a un flujo de desarrollo de software en vez de a un agente de dominio.

---

## Parte 3 — AgenticRAG: dentro de la mente de un agente — LLMs, Tools y MCP (Tomás Acosta y Luis Fernando Ruiz, Conecto)

### 3.1 Caso guía: Vortex (empresa ficticia de electrodomésticos)
Línea de soporte 24/7 en inglés/español/francés, para dos tipos de usuario: dueño de electrodoméstico y técnico autorizado. Especificación explícita de límites (mismo principio de "qué SÍ / qué NO" ya visto en la sesión 2 de Blend 360):
- **Sí**: diferenciar tipo de usuario, guiar procedimientos, responder preguntas, escalar a visita técnica.
- **No**: dar recomendaciones de circuitos eléctricos a quien no tiene el conocimiento, cancelar o agendar sin confirmación explícita.

Fuentes: manuales de usuario y boletines técnicos (PDFs largos, con jerarquía de capítulos/secciones, tablas de códigos de error, figuras, referencias cruzadas) + historial de servicio y garantías (parcialmente **manuscrito**).

### 3.2 Fundamentos técnicos
- **Token**: unidad mínima de procesamiento de un LLM — no es la palabra. Ejemplos: "desaguar" se parte en dos tokens; un código como "E21" también se tokeniza en partes, dependiendo del tokenizador usado.
- **Embedding**: vector que captura el significado **en contexto**. Ejemplo clásico de ambigüedad: "banco" cerca de "parque" pesa hacia el mueble; cerca de otras palabras, hacia la institución financiera — son vectores distintos según el contexto, aunque sea la misma palabra.
- **Similitud coseno**: mide el ángulo entre dos vectores, no su longitud — rango de -1 (opuestos) a 1 (misma dirección). Algunas librerías reportan **distancia coseno** = 1 − similitud (en ese caso, 0 es lo más similar).

### 3.3 RAG clásico: Recuperar + Aumentar + Generar

**Ingesta**, según el tipo de documento:
| Técnica | Cuándo usarla |
|---|---|
| Extracción de texto nativo (pymupdf, pdfplumber) | PDF con texto real, sin tablas complejas |
| OCR clásico (**Tesseract**, mantenido históricamente por Google) | PDFs escaneados o imágenes |
| Modelos de layout/tablas | Documentos con tablas estructuradas (recomendación: modelos gratuitos de Nvidia) |
| Modelos de visión-lenguaje | Leer la página completa como imagen (APIs gratuitas de Nvidia o Google AI Studio mencionadas como opción durante la competencia) |

**Chunking (segmentación)** — seis estrategias, recomendadas para **combinar entre sí** en vez de depender de los valores por defecto de un framework:
1. **Por tokens**: corte fijo de cantidad; simple pero puede partir ideas a la mitad.
2. **Por página**: simple, pero puede mezclar ideas distintas o partir una idea entre dos páginas.
3. **Por estructura/jerarquía**: respeta capítulos/secciones del documento — ideal cuando el documento ya viene bien organizado.
4. **Por tabla**: extrae fila por fila, repitiendo el encabezado en cada fragmento — clave para tablas de códigos de error como las de Vortex.
5. **Semántico**: el corte se hace donde cambia el significado (guiarse por signos de puntuación: puntos, punto y coma).
6. **Contextual**: corte semántico + un resumen de en qué parte del documento vive ese fragmento — coincide con lo que Anthropic documenta públicamente como *Contextual Retrieval*.

**Indexación y búsqueda**:
- **Fuerza bruta**: similitud coseno contra todos los registros — viable con pocos documentos.
- **HNSW** (índice aproximado, basado en grafos de vecinos): escalable a volúmenes grandes.
- **BM25** (búsqueda léxica) + **RRF** (Reciprocal Rank Fusion): combina el ranking léxico y el vectorial, dando más peso a las posiciones altas de cada uno.
- **Filtros por metadata** (página, modelo, sección) antes o junto con la búsqueda semántica, para más velocidad y precisión.

**Optimización post-recuperación**:
- **Reranking** con un modelo *cross-encoder* entrenado específicamente — más preciso, requiere entrenamiento propio.
- **Reprompting / expansión de consulta**: generar variantes de la pregunta original, recuperar por cada una, fusionar con RRF — mejora el recall a costa de más latencia (trade-off explícito).

**Generación condicionada**: un LLM predice el siguiente token según una distribución de probabilidad aprendida en entrenamiento. Si el dominio (ej. los códigos de error específicos de Vortex) no estuvo en esos datos —por ser información privada—, la distribución no discrimina bien la palabra correcta. RAG inyecta los chunks relevantes en el contexto para **sesgar correctamente** esa distribución, mitigando (no eliminando) alucinaciones.

### 3.4 De RAG a AgenticRAG
Un RAG plano sigue siempre el mismo camino fijo: recuperar → generar. Un **agente** decide dinámicamente qué herramienta llamar, cuántas veces, y cuándo tiene evidencia suficiente para responder — puede consultar varias fuentes distintas (no solo el índice vectorial), o pedir confirmación humana antes de ejecutar una acción. En el caso Vortex: cuatro tools — buscar manual, consultar historial, verificar garantía, agendar visita — cada una expuesta como un contrato JSON (nombre, descripción, parámetros). **La calidad de la descripción determina si el agente la usa bien** — el mismo punto que Rubén Manrique ya insistió sobre el docstring en LangChain ([[etapa2-sesion3-resumen]]).

### 3.5 MCP (Model Context Protocol)
Capa de orquestación entre agente(s) y un conjunto de tools. Sin MCP, conectar las mismas 15 tools a un segundo agente obliga a reimplementar toda la integración; con MCP, el agente solo se conecta al servidor y **descubre** qué tools/recursos existen. Ventajas: reutilización entre agentes, esquema de tools verificado en un solo lugar, gobierno de permisos centralizado (el mismo servidor MCP puede exponer distintos subconjuntos de tools según el cliente). Costo: latencia adicional y una dependencia más — **no siempre vale la pena** si son pocas tools o un solo agente aislado (mismo principio de "adopción no implica necesidad" ya visto en [[etapa2-sesion2-resumen]]).

### 3.6 Gestión de contexto en conversaciones largas
La ventana de contexto de un LLM es limitada y el desempeño empeora conforme la conversación se alarga. Técnica más usada actualmente: resumir la conversación en un archivo tipo `context.md` que el agente vuelve a leer, en vez de arrastrar todo el historial turno a turno.

### 3.7 Observabilidad
Mencionan **LangSmith** (advertencia explícita: si se trabaja con datos privados, sus trazas incluyen el contexto y las respuestas completas del agente — riesgo de privacidad a evaluar) y **Langfuse** (ya visto en sesiones anteriores de esta etapa). Una traza útil debe registrar latencia y pasos por respuesta, qué tools se llamaron, costo por llamada, y permitir **localizar** el componente específico que falla en vez de adivinar.

### 3.8 Evaluación de RAG en cuatro capas
1. **Recuperación**: context recall (de lo relevante, cuánto se recuperó), context precision (de lo recuperado, cuánto era relevante), hit rate (si al menos un documento relevante aparece en el top-K).
2. **Generación**: fidelidad y relevancia de la respuesta — evaluables con un LLM-as-judge.
3. **Decisiones del agente**: si llamó la tool correcta, con argumentos válidos, si hubo alucinación — revisando la traza completa.
4. **Golden Dataset**: conjunto de referencia (pregunta, documentos esperados, respuesta esperada) que se **mantiene y crece** a medida que producción revela casos no contemplados.

> **Nota de correspondencia con el stack ya definido del proyecto**: context recall, context precision y fidelidad/relevancia son exactamente las métricas centrales del framework **RAGAS**, ya listado como parte del stack de herramientas del equipo. Esta charla da la base conceptual de esas métricas, no un framework nuevo.

### Conceptos previos necesarios
- **Docstring como prompt de una tool** — [[etapa2-sesion3-resumen]] (Rubén Manrique).
- **Harness, MCP/A2A a nivel conceptual** — [[etapa2-sesion2-resumen]] (Blend 360, Google).
- **RAG y chunking**, introducidos por Rubén en la fase virtual de julio (fuera de esta etapa) — esta charla es la profundización técnica prometida explícitamente el jueves en [[etapa2-sesion3-resumen]] ("el detalle técnico de AgenticRAG llega con Conecto"), cumplida hoy tras el aplazamiento.

---

## Glosario rápido de esta sesión
- **ScanSAR vs. Spotlight:** modos de imagen radar — cobertura amplia y baja resolución vs. foco puntual de alta resolución.
- **AIS / VMS:** sistemas activos de posicionamiento de embarcaciones (alta mar / zona costera); ambos pueden desactivarse, de ahí la necesidad de fuentes complementarias (luces nocturnas, radiofrecuencia).
- **Spec-driven development:** escribir especificaciones detalladas en vez de código; el LLM implementa a partir de ellas.
- **HNSW:** índice aproximado de vecinos más cercanos basado en grafos, para búsqueda vectorial escalable.
- **BM25 + RRF:** búsqueda léxica combinada con fusión de rankings (léxico + vectorial).
- **Cross-encoder (reranking):** modelo entrenado específicamente para reordenar candidatos recuperados por relevancia real.
- **Contextual chunking:** fragmento semántico + resumen de su ubicación en el documento original.
- **Golden Dataset:** conjunto de referencia (pregunta–documentos–respuesta esperada) usado para evaluar y detectar regresiones en un sistema RAG/agéntico.

## Documentación y recursos citados

| Herramienta / referencia | Enlace | Para qué sirve |
|---|---|---|
| Telespazio — SEonSE (Smart Eyes on SEas) | https://www.telespazio.com/en/press-release-detail/-/detail/seonse-1 | Plataforma de vigilancia marítima multisensor |
| Telespazio UK — braINT / SEonSE | https://telespazio.co.uk/en/geoinformation/applications/defence-intelligence | Explotación masiva de imágenes para inteligencia de defensa |
| Telespazio UK — MapCy | https://telespazio.co.uk/en/geoinformation/platforms/mapcy | Cartografía rápida de emergencia (incl. modelo de inundación + redes sociales) |
| Vantor (antes Maxar) | https://www.vantor.com | API de imágenes satelitales de alta resolución (Discovery, Raster/Vector Analytics) |
| Cognition — adquisición de Windsurf | https://cognition.com/blog/windsurf | Historia de la herramienta de desarrollo agéntico usada en la demo de Vantor |
| OpenCode | https://opencode.ai | Alternativa de código abierto para desarrollo agéntico sin licencia comercial |
| Tesseract OCR | https://github.com/tesseract-ocr/tesseract | Motor OCR de código abierto para PDFs escaneados |
| Anthropic — Contextual Retrieval | https://www.anthropic.com/news/contextual-retrieval | Técnica de chunking contextual mencionada por Conecto |
| RAGAS | https://docs.ragas.io | Framework de métricas de evaluación RAG (context recall/precision, fidelidad) |
| Model Context Protocol | https://modelcontextprotocol.io | Especificación del protocolo agente↔herramientas |

## Recomendaciones prácticas dadas en la sesión
- Verificar la licencia de cada dependencia y del repositorio final antes de la entrega — una licencia restrictiva descalifica al equipo.
- Empezar a construir el harness (agentes, skills, hooks, especificaciones base) antes del 18 de septiembre, sin esperar a conocer el reto.
- Nunca dejar que el mismo modelo que generó código sea el único que lo verifica — usar verificación cruzada con un modelo distinto.
- Definir hooks de validación de secretos y puntos de confirmación humana obligatoria para acciones destructivas o con costo, antes de dar autonomía amplia al harness.
- Combinar varias estrategias de chunking (estructura + tabla + semántico, por ejemplo) en vez de usar solo la opción por defecto de un framework.
- Revisar la traza completa del agente (no solo la respuesta final) para diagnosticar fallos de recuperación, de tool-calling o de generación por separado.
- Mantener y ampliar un Golden Dataset de evaluación a medida que aparezcan casos no contemplados durante las pruebas.
- Tener un plan B con datos/resultados pregrabados para que la demo funcione incluso si falla una API externa o la conexión el día del reto.
