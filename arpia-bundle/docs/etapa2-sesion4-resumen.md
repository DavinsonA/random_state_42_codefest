# CODEFEST Ad Astra 2026 — Etapa 2, Sesión 4 (10 de septiembre)

Resumen de conceptos. Cubre solo lo explicado en esta sesión: **"Visualizaciones con datos georreferenciados"** (Camilo Escobar Velázquez, Uniandes). La charla de Conecto (Tomás Acosta Bernal, *AgenticRAG*) prevista para hoy se aplazó por un inconveniente personal del ponente; los organizadores mencionaron que buscarían reprogramarla o compartirla grabada. Es la cuarta sesión de la etapa pre-presencial, y es una extensión directa de una charla de visualización que Camilo ya había dado en la fase virtual de julio (tareas analíticas clásicas) — hoy se enfoca en las dos tareas que quedaron pendientes entonces: **tendencia** (líneas de tiempo) y **tarea espacial** (mapas), y en cómo integrarlas.

---

## Parte 1 — Visualizaciones con datos georreferenciados y longitudinales (Camilo Escobar)

### 1.1 Por qué esto importa para los tres fenómenos del reto
El corpus del reto virtual cubre tres fenómenos (IA en entornos militares, seguridad espacial/órbita baja, dinámicas territoriales en LATAM y el Caribe). El fenómeno 3 es el más explícitamente geoespacial, pero los tres comparten dos características que hacen relevante esta charla:
- **Componente de lugar**: nombres de lugares, entidades culturales, observatorios ubicados en países/regiones específicas, ya presentes como texto explícito en los documentos.
- **Componente de tiempo**: los reportes de los observatorios vienen fechados desde 2023–2024, lo que permite ver tendencias a lo largo del tiempo, no solo hechos puntuales.

### 1.2 Preparación de datos espaciales
Antes de visualizar, hay que **identificar y normalizar entidades georreferenciables** en el texto: nombres de lugares (ciudades, hitos culturales — ej. el Parque Simón Bolívar en Bogotá), divisiones político-administrativas (países, regiones, departamentos/cantones), y los recursos OSM PBF que ya hacen parte del corpus. Punto de diseño clave: **la granularidad de la coordenada debe corresponder a la escala del análisis** — si el interés es a nivel de país, basta una coordenada representativa del país; si es a nivel de departamento o municipio, se necesitan coordenadas más específicas por región.

### 1.3 Preparación de datos temporales
Cada observatorio fuente puede venir de un país distinto, y **el formato de fecha varía por país/gobierno**: DD/MM/AAAA (Colombia, con `/`), DD.MM.AAAA (Suiza, con `.` — decisión gubernamental oficial), MM/DD/AAAA (Estados Unidos). Si no se estandariza esto antes de procesar, cualquier análisis temporal o visualización pierde sentido. Según el objetivo de la tarea, además puede convenir **agregar** las fechas por mes, trimestre o año.

### 1.4 Trazabilidad hacia el dato original
Recomendación explícita: mantener siempre la relación entre lo que se visualiza y los **IDs de documento y de chunk** del dataset original. Esto permite que cualquier hallazgo visual sea rastreable hasta su fuente — necesario tanto para la calidad del análisis como, previsiblemente, para la evaluación del reto.

### 1.5 Recordatorio: seis tareas analíticas clásicas (de la charla previa de Camilo en la fase virtual)
| Tarea | Visualizaciones típicas |
|---|---|
| Comparación | Barras, radar, tablas |
| Relación | Dispersión, redes/nodos, matrices |
| Distribución | Histogramas, cajas y bigotes |
| Composición | Ej. un mapa completo construido por partes (departamentos) |
| **Tendencia** | Líneas de tiempo, áreas bajo la curva, diagramas de Gantt |
| **Espacial** | Mapas |

Las dos últimas son el foco de esta sesión.

### 1.6 Tres tipos de mapas — los "canales" de codificación geoespacial

**a) Mapa de puntos.** El canal principal es la **ubicación** (el centro del punto); la cantidad, si se necesita, se codifica con el **diámetro** (diagrama de burbujas). Se usa cuando el número de ubicaciones es moderado y lo que importa es identificar *dónde existe* un fenómeno, no tanto diferenciar magnitudes finas entre puntos. Ejemplo mostrado en vivo: una iniciativa civil de mapeo que ubica centros de apoyo a adultos mayores en la zona de impacto del sismo reciente en Colombia — al seleccionar un departamento, el mapa refina la vista a ubicaciones más puntuales.

**b) Mapa coroplético.** Regiones bien delimitadas (administrativas o de interés) coloreadas según una métrica — para **comparar magnitudes entre territorios**. Ejemplo mostrado (de un paper): mapa de Colombia dividido por municipios, con escala de color de amarillo pálido a rojo oscuro, mostrando mayor magnitud de impacto hacia el sureste del país.

**c) Mapa de calor (heatmap).** Sin regiones marcadas — muestra la **densidad/intensidad continua** de un fenómeno sobre el territorio. Útil cuando hay demasiados eventos puntuales para representarlos individualmente, o cuando el fenómeno no respeta límites administrativos. Ejemplo mostrado: el impacto de un sismo reciente en Colombia representado como una mancha de calor alrededor del epicentro, codificando la intensidad percibida.

### 1.7 Niveles de detalle (zoom) en mapas
Como en Google Maps, el nivel de zoom determina cuánta información/capas se revelan (relieve/altitud, tráfico en tiempo real, capas temáticas específicas). Recomendación de diseño: pensar explícitamente qué información se revela en cada nivel de zoom, en vez de mostrar todo siempre al mismo nivel de detalle.

### 1.8 Fuentes de datos geoespaciales públicas mencionadas
| Categoría | Fuentes | Usos típicos |
|---|---|---|
| Ópticas | Sentinel-2, MODIS, VIIRS, Landsat | Vegetación, agricultura, cobertura del suelo; **VIIRS en particular es la fuente estándar para luces nocturnas** |
| Radar (SAR) | Sentinel-1 | Zonas urbanas, inundaciones, detección de cambios, verificación de instalaciones (funciona de noche y con nubosidad) |
| Especializadas | Aqua (perfiles atmosféricos: temperatura, vapor de agua, gases), **ECOSTRESS** (temperatura superficial de alta resolución desde la ISS, evapotranspiración) | Picos de calor urbano, estrés hídrico de vegetación |

**Portales de acceso**: **NASA Earthdata Search** y **Copernicus Data Space Ecosystem** — descritos como "un Google Maps con muchas más capacidades de filtrado" sobre estas fuentes.

**Mapeo sugerido fuente↔fenómeno del reto** (propuesto por el ponente):
- Fenómeno 1 (IA en entornos militares) → Sentinel-2/MODIS/VIIRS, para cambios e infraestructura física.
- Fenómeno 2 (seguridad espacial/órbita baja) → Sentinel-1/Aqua/ECOSTRESS, para cambios en infraestructura terrestre asociada.
- Fenómeno 3 (dinámicas territoriales LATAM) → ECOSTRESS/VIIRS, para deforestación, cambios de vegetación y agricultura.

### 1.9 Plataformas y librerías
Plataformas GIS profesionales como **ArcGIS (Esri)** tienen más capacidades pero una curva de aprendizaje alta — no recomendadas para el ritmo de una hackatón. Para el reto, más viables: **Leaflet** y **Mapbox GL JS** — ambas soportan **brushing and linking** (filtrado y renderizado cruzado e interactivo entre visualizaciones vinculadas).

### 1.10 Codificación visual y accesibilidad (recomendaciones explícitas)
- **Teoría del color**: el rojo connota "alerta/problema" perceptualmente — cuidado al usarlo para representar, por ejemplo, un avance positivo de vegetación.
- **Paletas consistentes** para el mismo fenómeno en todas las vistas, con **escalas bien establecidas** (no reinventar la escala de color en cada gráfico).
- **Revisar el contraste** entre colores adyacentes de una escala antes de usarla — un contraste bajo puede representar información de forma engañosa (además de ser una barrera de accesibilidad).
- **No superponer leyendas/métricas sobre el mapa** de forma que oculten información relevante.

### 1.11 Datos longitudinales / líneas de tiempo

**Riesgo de falsa representación**: unir con líneas rectas observaciones espaciadas en el tiempo puede sugerir una tendencia lineal continua que los datos reales no sustentan. Ejemplo mostrado con datos inventados: una línea recta entre dos puntos de 2022–2023 sugiere crecimiento constante, cuando en realidad los datos podían haber estado estables la mayor parte del período y subir solo al final — **usar curvas o solo puntos** cuando la interpolación lineal no está justificada. Las líneas de tiempo también sirven para mostrar **reapariciones o relaciones entre eventos**, no solo la evolución de una magnitud.

**Buenas prácticas explícitas:**
1. **Agregación consistente y declarada**: si el título dice "por año", toda la gráfica debe estar agregada por año — no mezclar granularidades.
2. **Contexto explícito**: leyendas, títulos y textos de acompañamiento correctos y completos.
3. **Colores consistentes** para el mismo fenómeno a través de las distintas vistas.
4. **Filtros de rango temporal**, dado que los datos suelen cubrir una franja de tiempo amplia.

### 1.12 Integración de visualizaciones geoespaciales + temporales
Tres patrones de composición mencionados:
- **Cuadrícula (grid)**: dashboard clásico, varios cuadrantes con vistas complementarias.
- **Maestro-detalle**: un mapa grande + un panel de detalle (patrón familiar de sitios de reserva de hoteles/Airbnb). **Recomendado explícitamente como el más viable para el alcance del reto.**
- **Narrativa guiada** (tipo "scrollytelling" de museo, mostrando cómo se construye una historia a lo largo del tiempo): mencionado como posibilidad más ambiciosa, no como recomendación principal.

**Interactividad transversal, independiente del patrón elegido:**
- **Filtros globales**: seleccionar un fenómeno debe afectar todas las visualizaciones del dashboard.
- **Brushing and linking**: seleccionar algo en una visualización debe resaltar/filtrar la selección correspondiente en las demás.
- Mantener siempre visible la **trazabilidad hacia la fuente original** de cada dato mostrado.

### 1.13 Q&A y cierre — pistas para el reto (sin revelar el reto)
- **Tip principal del ponente**: entender primero **cuál es la tarea analítica real** antes de elegir el tipo de visualización — el error común es caer en el sesgo de usar el gráfico que uno ya sabe hacer, en vez del que la tarea realmente pide.
- Recomendación operativa: revisar con anticipación las fuentes de datos geoespaciales compartidas por correo (Sentinel, MODIS, VIIRS, Landsat, Aqua, ECOSTRESS, portales NASA/Copernicus) y pensar qué se podría extraer de ahí para **enriquecer** el corpus vectorial/de grafos ya construido en la fase 1 — sugerido explícitamente por el moderador como algo "provechoso" de hacer antes del reto presencial.
- El moderador confirmó (sin dar detalles del reto) que es "muy posible" que el reto involucre trabajar con datos georreferenciados sobre las fuentes ya entregadas.

### Conceptos previos necesarios
- **Tareas analíticas clásicas** (comparación, relación, distribución, composición) — charla previa de Camilo en la fase virtual de julio, resumidas en la sección 1.5 de este documento.
- **Corpus con `doc_id`/chunk y los tres fenómenos** — contexto del proyecto; la georreferenciación es exactamente el tipo de entidad extraíble que puede alimentar el pipeline de retrieval/multiagente ya existente.
- **Extracción de entidades vía agentes/RAG** ([[etapa2-sesion3-resumen]], charla de Rubén Manrique) — la normalización de lugares y fechas descrita hoy es el insumo que un agente analista necesitaría antes de poder citar evidencia georreferenciada de forma confiable.

### Conceptos que se profundizan en próximas sesiones
- **Plataforma de inteligencia geoespacial** (viernes, Telespacio) — profundiza el uso profesional de este tipo de fuentes satelitales.
- La charla de Conecto sobre **AgenticRAG**, aplazada de esta sesión, es la que profundizaría cómo un agente decide y ejecuta múltiples búsquedas — sigue pendiente de reprogramación.

---

## Glosario rápido de esta sesión
- **Mapa de puntos:** el canal principal es la ubicación; la magnitud (si aplica) se codifica con el tamaño del punto.
- **Mapa coroplético:** regiones delimitadas coloreadas según una métrica, para comparar magnitudes entre territorios.
- **Mapa de calor (heatmap) geoespacial:** densidad/intensidad continua de un fenómeno, sin respetar límites administrativos.
- **Brushing and linking:** interacción en la que seleccionar/filtrar en una visualización actualiza automáticamente las demás visualizaciones vinculadas.
- **SAR (Synthetic Aperture Radar):** radar de apertura sintética (Sentinel-1); permite observación día/noche y con nubosidad.
- **Evapotranspiración:** combinación de evaporación del suelo y transpiración de las plantas; producto derivado de sensores térmicos como ECOSTRESS.
- **Falsa representación por interpolación lineal:** sesgo visual al conectar con líneas rectas observaciones temporales espaciadas, sugiriendo una tendencia continua inexistente.

## Documentación y recursos citados

| Herramienta / referencia | Enlace | Para qué sirve |
|---|---|---|
| NASA Earthdata Search | https://search.earthdata.nasa.gov | Portal de búsqueda de datos satelitales de NASA y agencias asociadas (ESA, JAXA, ISRO) |
| Copernicus Data Space Ecosystem | https://dataspace.copernicus.eu | Portal oficial de acceso a datos Sentinel (1, 2, 3, 5P) de la ESA |
| ECOSTRESS (NASA JPL) | https://ecostress.jpl.nasa.gov | Temperatura superficial de alta resolución y evapotranspiración desde la ISS |
| Leaflet | https://leafletjs.com | Librería JS ligera para mapas interactivos en frontend |
| Mapbox GL JS | https://docs.mapbox.com/mapbox-gl-js/ | Librería JS para mapas vectoriales interactivos, con soporte de brushing and linking |
| Esri ArcGIS | https://www.esri.com/en-us/arcgis/about-arcgis/overview | Plataforma GIS profesional (mencionada como referencia, curva de aprendizaje alta para el ritmo del reto) |

## Recomendaciones prácticas dadas en la sesión
- Definir la tarea analítica (comparación, tendencia, espacial, etc.) antes de elegir el tipo de gráfico o mapa — no al revés.
- Normalizar formato de fecha y granularidad de coordenada geográfica según el país de origen de cada fuente/observatorio, antes de cualquier análisis temporal o espacial.
- Mantener siempre la trazabilidad hacia `doc_id`/chunk de origen en cualquier visualización.
- Para el alcance del reto, empezar por un patrón maestro-detalle (mapa + panel) con filtros globales y brushing and linking, antes que narrativas guiadas más ambiciosas.
- Revisar con anticipación las fuentes satelitales públicas (Sentinel, MODIS, VIIRS, Landsat, Aqua, ECOSTRESS) para identificar qué podrían aportar como enriquecimiento del corpus ya construido en la fase 1.
- Usar curvas o puntos discretos en vez de líneas rectas cuando los datos temporales no sustenten una interpolación lineal.
