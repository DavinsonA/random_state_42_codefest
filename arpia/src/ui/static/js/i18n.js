// Idioma de la interfaz (es / en), sin librerias.
//
// - Textos fijos del HTML: atributos `data-i18n` (texto), `data-i18n-placeholder`,
//   `data-i18n-aria` (aria-label) y `data-i18n-title` (title).
// - Textos generados por JS: `t("clave", { variables })`.
// - El idioma se recuerda en localStorage y viaja en los enlaces entre chat y
//   tablero como `?lang=`: en el despliegue son dominios distintos
//   (frontagent.* / dashboard.*) y no comparten almacenamiento.
//
// Lo que escribe el agente (respuesta, citas, titulos de vistas) llega del
// backend tal cual: no se traduce aqui.

export const IDIOMAS = ["es", "en"];
const CLAVE = "arpia.idioma";

const DICC = {
    es: {
        "idioma.es": "Español",
        "idioma.en": "English",
        "idioma.cambiar": "Idioma de la página",
        "cargador.texto": "Cargando",

        "salud.verificando": "Verificando servicio…",
        "salud.ok": "Servicio operativo",
        "salud.degraded": "Servicio degradado",
        "salud.down": "Servicio caído",
        "salud.sinConexion": "Sin conexión",
        "salud.sinAdvertencias": "Sin advertencias",
        "salud.estado": "Estado: {estado}",

        "aviso.stub.titulo": "Modo simulado.",
        "aviso.stub.chat": "Este servicio responde con datos de prueba ({codigo}): nada de lo que ves proviene del corpus.",
        "aviso.stub.tablero": "Los datos son de prueba ({codigo}): nada de lo que ves proviene del corpus.",

        "agente.orquestador": "Orquestador",
        "agente.agente_documental": "Documental",
        "agente.agente_visualizador": "Visualizador",
        "agente.agente_analitico": "Analítico",
        "agente.guardian": "Guardián",
        "agente.memoria": "Memoria",

        "fenomeno.F1": "IA y Capacidades Estratégicas",
        "fenomeno.F2": "Seguridad del Entorno Espacial",
        "fenomeno.F3": "Dinámicas Territoriales",

        "chart.timeline": "Serie anual",
        "chart.bar": "Barras",
        "chart.stacked_bar": "Barras apiladas por fenómeno",
        "chart.donut": "Composición",
        "chart.table": "Tabla",
        "chart.kpi": "Indicador",

        "grupo.fenomeno": "fenómeno",
        "grupo.organizacion": "organización",
        "grupo.fuente": "fuente",
        "grupo.formato": "formato",
        "grupo.anio": "año",
        "grupo.generico": "grupo",

        "metrica.conteo_documentos": "documentos",
        "metrica.conteo_fragmentos": "fragmentos",

        "titulo.total": "Total de {metrica}",
        "titulo.por": "{Metrica} por {grupo}",

        "error.sin_backend": "Esta página no está conectada al backend de A.R.P.I.A. (se abrió desde otro servidor, p. ej. Live Server). Con el backend encendido, ábrela en http://localhost:8765/ (chat) o http://dashboard.localhost:8765/ (tablero).",
        "error.timeout": "El servicio tardó demasiado en responder. Intenta de nuevo.",
        "error.red": "No se pudo conectar con el servicio.",
        "error.ilegible": "Respuesta ilegible del servicio (HTTP {status}).",
        "error.http": "El servicio respondió con error (HTTP {status}).",
        "error.sin_datos_tablero": "El servicio aún no expone los datos del tablero (/api/aggregate). La vista se mostrará en cuanto esté disponible.",
        "error.datos": "No se pudieron cargar los datos de la vista.",
        "error.indice": "El índice del corpus todavía no está disponible. La vista se mostrará en cuanto lo esté.",
        "error.sinDatosMotivo": "No hay datos disponibles: {motivo}.",
        "error.inesperado": "Ocurrió un error inesperado.",

        "nota.simulado": "Datos simulados (modo stub): no provienen del corpus.",
        "nota.cobertura": "Cobertura: {con} de {total} documentos ({pct}%) tienen año.",

        // -- chat --
        "chat.titulo": "A.R.P.I.A. · Asistente de análisis",
        "chat.sub": "Aplicativo de Recuperación, Predicción e Inteligencia Agéntica",
        "chat.nueva": "Nueva conversación",
        "chat.tablero": "Tablero",
        "chat.bienvenida.titulo": "¿Qué quieres analizar?",
        "chat.bienvenida.texto": "Respondo sobre el corpus de fuentes abiertas de los tres fenómenos del reto. Cada respuesta cita el documento y el fragmento de donde sale.",
        "chat.fenomenos": "Fenómenos del corpus",
        "chat.ejemplos": "Preguntas de ejemplo",
        "chat.ejemplo1": "¿Qué reporta el corpus sobre capacidades antisatélite en 2024?",
        "chat.ejemplo2": "¿Cómo difiere el enfoque de dos países frente a la órbita baja terrestre?",
        "chat.ejemplo3": "¿Qué actores aparecen asociados a dinámicas territoriales en la frontera?",
        "chat.ejemplo4": "¿Cuántos documentos hay por fenómeno?",
        "chat.entrada.label": "Escribe tu consulta",
        "chat.entrada.placeholder": "Escribe tu consulta sobre el corpus…",
        "chat.enviar": "Enviar",
        "chat.ayuda": "Enter envía · Shift+Enter nueva línea",
        "chat.conversacion": "Conversación",
        "chat.tu": "Tú",
        "chat.pendiente": "Consultando agentes y evidencia del corpus…",
        "chat.vacia": "(respuesta vacía)",
        "chat.agentes": "Agentes invocados",
        "chat.interacciones": "interacciones",
        "chat.tokens": "tokens",
        "chat.latencia": "latencia",
        "chat.evidencia": "Evidencia · {n} {unidad}",
        "chat.fragmento": "fragmento",
        "chat.fragmentos": "fragmentos",
        "chat.vista.propuesta": "Vista propuesta",
        "chat.vista.aria": "Vista propuesta para el tablero",
        "chat.vista.conteo": "conteo de {metrica}",
        "chat.vista.por": "por {grupo}",
        "chat.vista.nota": "Nota: ",
        "chat.vista.abrir": "Abrir en el tablero",
        "chat.visualizar": "Visualizar esto",
        "chat.sinRespuesta": "Sin respuesta",
        "chat.reintentar": "Reintentar",
        "chat.estado.simulado": "Simulado",
        "chat.estado.sinConsulta": "Sin consulta",
        "chat.estado.fueraAlcance": "Fuera de alcance",
        "chat.estado.errorInterno": "Error interno",
        "chat.estado.liveNo": "Modo real no habilitado",

        // -- tablero --
        "tablero.titulo": "A.R.P.I.A. · Tablero de análisis",
        "tablero.marca": "Tablero Analítico",
        "tablero.chat": "Chat",
        "tablero.ia.titulo": "Asistente Inteligente",
        "tablero.ia.enLinea": "● Sistema en línea",
        "tablero.ia.degradado": "● Sistema en línea (degradado)",
        "tablero.ia.fuera": "● Sistema fuera de línea",
        "tablero.ia.sinConexion": "● Sin conexión con el servidor",
        "tablero.ia.inicio": "Ingrese su consulta para comenzar. El agente analizará la información solicitada y actualizará el tablero con las visualizaciones y resultados relevantes.",
        "tablero.ia.pensando": "La IA está analizando los datos...",
        "tablero.ia.procesando": "Procesando pregunta...",
        "tablero.pregunta.label": "Escribe tu pregunta",
        "tablero.pregunta.placeholder": "Escribe tu pregunta...",
        "tablero.enviar": "Enviar",
        "tablero.fuente": "Fuente",
        "tablero.visualizaciones": "Visualizaciones",
        "tablero.agregado": "agregado · {titulo}",
        "tablero.ampliar": "Ampliar gráfico",
        "tablero.ampliarDe": "Ampliar: {titulo}",
        "tablero.cerrar": "Cerrar vista ampliada",
        "tablero.origen.simulado": "Simulado",
        "tablero.origen.agente": "Del agente",
        "tablero.origen.corpus": "Del corpus",
        "tablero.origen.sin_datos": "Sin datos",
        "tablero.mapa": "Distribución geográfica",
        "tablero.mapa.sinDatos": "El corpus no trae lugar por documento, así que no hay mapa que dibujar.",
        "tablero.relaciones": "Relaciones",
        "tablero.relaciones.sinDatos": "El corpus no trae actores ni vínculos entre ellos, así que no hay relaciones que dibujar. No se inventan.",
        "tablero.abrirDocumento": "Abrir documento",
        "tablero.sinDatosTodavia": "Sin datos disponibles todavía.",
        "tablero.sinDatosFiltros": "No hay datos para estos filtros.",
        "tablero.tabla.grupo": "Grupo",
        "tablero.tabla.fenomeno": "Fenómeno",
        "tablero.tabla.valor": "Valor",
        "tablero.tabla.documentos": "Documentos",
        "tablero.total": "Total",
        "tablero.sinDato": "(sin dato)",
        "tablero.otros": "Otros",
        "tablero.hallazgos": "Lo que dicen las cifras",
        "informe.titulo": "Informe de análisis · A.R.P.I.A.",
        "informe.pregunta": "Consulta",
        "informe.fecha": "Generado",
        "informe.respuesta": "Análisis",
        "informe.hallazgos": "Lo que dicen las cifras",
        "informe.vistas": "Visualizaciones",
        "informe.fuentes": "Fuentes",
        "informe.pie": "Generado por A.R.P.I.A. · {tokens} tokens · agentes: {agentes}",
        "informe.descargar": "Descargar informe",
        "informe.pagina": "Página {n} de {total}",
        "serie.tipo": "Tipo de gráfico",
        "serie.linea": "Línea",
        "serie.columnas": "Columnas",
        "serie.barras": "Barras",
    },

    en: {
        "idioma.es": "Español",
        "idioma.en": "English",
        "idioma.cambiar": "Page language",
        "cargador.texto": "Loading",

        "salud.verificando": "Checking service…",
        "salud.ok": "Service operational",
        "salud.degraded": "Service degraded",
        "salud.down": "Service down",
        "salud.sinConexion": "No connection",
        "salud.sinAdvertencias": "No warnings",
        "salud.estado": "Status: {estado}",

        "aviso.stub.titulo": "Simulated mode.",
        "aviso.stub.chat": "This service answers with test data ({codigo}): nothing you see comes from the corpus.",
        "aviso.stub.tablero": "Data is for testing ({codigo}): nothing you see comes from the corpus.",

        "agente.orquestador": "Orchestrator",
        "agente.agente_documental": "Document agent",
        "agente.agente_visualizador": "Visualization agent",
        "agente.agente_analitico": "Analytics agent",
        "agente.guardian": "Guardian",
        "agente.memoria": "Memory",

        "fenomeno.F1": "AI and Strategic Capabilities",
        "fenomeno.F2": "Space Environment Security",
        "fenomeno.F3": "Territorial Dynamics",

        "chart.timeline": "Yearly series",
        "chart.bar": "Bars",
        "chart.stacked_bar": "Bars stacked by phenomenon",
        "chart.donut": "Composition",
        "chart.table": "Table",
        "chart.kpi": "Indicator",

        "grupo.fenomeno": "phenomenon",
        "grupo.organizacion": "organization",
        "grupo.fuente": "source",
        "grupo.formato": "format",
        "grupo.anio": "year",
        "grupo.generico": "group",

        "metrica.conteo_documentos": "documents",
        "metrica.conteo_fragmentos": "fragments",

        "titulo.total": "Total {metrica}",
        "titulo.por": "{Metrica} by {grupo}",

        "error.sin_backend": "This page is not connected to the A.R.P.I.A. backend (it was opened from another server, e.g. Live Server). With the backend running, open it at http://localhost:8765/ (chat) or http://dashboard.localhost:8765/ (dashboard).",
        "error.timeout": "The service took too long to respond. Please try again.",
        "error.red": "Could not connect to the service.",
        "error.ilegible": "Unreadable response from the service (HTTP {status}).",
        "error.http": "The service returned an error (HTTP {status}).",
        "error.sin_datos_tablero": "The service does not expose dashboard data yet (/api/aggregate). The view will appear as soon as it is available.",
        "error.datos": "Could not load the data for this view.",
        "error.indice": "The corpus index is not available yet. The view will appear as soon as it is.",
        "error.sinDatosMotivo": "No data available: {motivo}.",
        "error.inesperado": "An unexpected error occurred.",

        "nota.simulado": "Simulated data (stub mode): it does not come from the corpus.",
        "nota.cobertura": "Coverage: {con} of {total} documents ({pct}%) have an identifiable year.",

        // -- chat --
        "chat.titulo": "A.R.P.I.A. · Analysis assistant",
        "chat.sub": "Agentic Retrieval, Prediction and Intelligence Application",
        "chat.nueva": "New conversation",
        "chat.tablero": "Dashboard",
        "chat.bienvenida.titulo": "What do you want to analyze?",
        "chat.bienvenida.texto": "I answer questions about the open-source corpus covering the challenge's three phenomena. Every answer cites the document and the fragment it comes from.",
        "chat.fenomenos": "Corpus phenomena",
        "chat.ejemplos": "Example questions",
        "chat.ejemplo1": "What does the corpus report about anti-satellite capabilities in 2024?",
        "chat.ejemplo2": "How do two countries differ in their approach to low Earth orbit?",
        "chat.ejemplo3": "Which actors are associated with territorial dynamics at the border?",
        "chat.ejemplo4": "How many documents are there per phenomenon?",
        "chat.entrada.label": "Type your question",
        "chat.entrada.placeholder": "Ask about the corpus…",
        "chat.enviar": "Send",
        "chat.ayuda": "Enter sends · Shift+Enter new line",
        "chat.conversacion": "Conversation",
        "chat.tu": "You",
        "chat.pendiente": "Consulting agents and corpus evidence…",
        "chat.vacia": "(empty answer)",
        "chat.agentes": "Agents invoked",
        "chat.interacciones": "interactions",
        "chat.tokens": "tokens",
        "chat.latencia": "latency",
        "chat.evidencia": "Evidence · {n} {unidad}",
        "chat.fragmento": "fragment",
        "chat.fragmentos": "fragments",
        "chat.vista.propuesta": "Proposed view",
        "chat.vista.aria": "View proposed for the dashboard",
        "chat.vista.conteo": "count of {metrica}",
        "chat.vista.por": "by {grupo}",
        "chat.vista.nota": "Note: ",
        "chat.vista.abrir": "Open in dashboard",
        "chat.visualizar": "Visualize this",
        "chat.sinRespuesta": "No answer",
        "chat.reintentar": "Retry",
        "chat.estado.simulado": "Simulated",
        "chat.estado.sinConsulta": "No question",
        "chat.estado.fueraAlcance": "Out of scope",
        "chat.estado.errorInterno": "Internal error",
        "chat.estado.liveNo": "Live mode not enabled",

        // -- tablero --
        "tablero.titulo": "A.R.P.I.A. · Analysis dashboard",
        "tablero.marca": "Analytics Dashboard",
        "tablero.chat": "Chat",
        "tablero.ia.titulo": "Intelligent Assistant",
        "tablero.ia.enLinea": "● System online",
        "tablero.ia.degradado": "● System online (degraded)",
        "tablero.ia.fuera": "● System offline",
        "tablero.ia.sinConexion": "● No connection to the server",
        "tablero.ia.inicio": "Enter your question to begin. The agent will analyze the requested information and update the dashboard with the relevant visualizations and results.",
        "tablero.ia.pensando": "The AI is analyzing the data...",
        "tablero.ia.procesando": "Processing question...",
        "tablero.pregunta.label": "Type your question",
        "tablero.pregunta.placeholder": "Type your question...",
        "tablero.enviar": "Send",
        "tablero.fuente": "Source",
        "tablero.visualizaciones": "Visualizations",
        "tablero.agregado": "aggregate · {titulo}",
        "tablero.ampliar": "Expand chart",
        "tablero.ampliarDe": "Expand: {titulo}",
        "tablero.cerrar": "Close expanded view",
        "tablero.origen.simulado": "Simulated",
        "tablero.origen.agente": "From the agent",
        "tablero.origen.corpus": "From the corpus",
        "tablero.origen.sin_datos": "No data",
        "tablero.mapa": "Geographic distribution",
        "tablero.mapa.sinDatos": "The corpus has no place per document, so there is no map to draw.",
        "tablero.relaciones": "Relationships",
        "tablero.relaciones.sinDatos": "The corpus has no actors or links between them, so there are no relationships to draw. None are invented.",
        "tablero.abrirDocumento": "Open document",
        "tablero.sinDatosTodavia": "No data available yet.",
        "tablero.sinDatosFiltros": "No data for these filters.",
        "tablero.tabla.grupo": "Group",
        "tablero.tabla.fenomeno": "Phenomenon",
        "tablero.tabla.valor": "Value",
        "tablero.tabla.documentos": "Documents",
        "tablero.total": "Total",
        "tablero.sinDato": "(no data)",
        "tablero.otros": "Other",
        "tablero.hallazgos": "What the figures show",
        "informe.titulo": "Analysis report · A.R.P.I.A.",
        "informe.pregunta": "Query",
        "informe.fecha": "Generated",
        "informe.respuesta": "Analysis",
        "informe.hallazgos": "What the figures show",
        "informe.vistas": "Visualizations",
        "informe.fuentes": "Sources",
        "informe.pie": "Generated by A.R.P.I.A. · {tokens} tokens · agents: {agentes}",
        "informe.descargar": "Download report",
        "informe.pagina": "Page {n} of {total}",
        "serie.tipo": "Chart type",
        "serie.linea": "Line",
        "serie.columnas": "Columns",
        "serie.barras": "Bars",
    },
};

// -- idioma activo -------------------------------------------------------------

function leerInicial() {
    // Sin DOM esto no es un error: el modulo se importa tal cual desde el
    // ejecutor de pruebas de Node, donde no hay `window` ni `localStorage`.
    // Reventar al importarse haria intestables todos los modulos que dependen
    // de este —`viewspec.js` y `referencias.js` entre ellos— por un idioma que
    // ahi no se usa para nada.
    if (typeof window === "undefined") return "es";

    const deUrl = new URLSearchParams(window.location.search).get("lang");
    if (IDIOMAS.includes(deUrl)) return deUrl;
    try {
        const guardado = localStorage.getItem(CLAVE);
        if (IDIOMAS.includes(guardado)) return guardado;
    } catch { /* almacenamiento bloqueado: se usa el predeterminado */ }
    return "es";
}

let actual = leerInicial();

export function idioma() {
    return actual;
}

/** Traduce una clave; `{var}` se sustituye y `{Var}` la pone con mayuscula inicial. */
export function t(clave, vars = {}) {
    const texto = DICC[actual][clave] ?? DICC.es[clave] ?? clave;
    return texto.replace(/\{(\w+)\}/g, (_, nombre) => {
        const v = vars[nombre] ?? vars[nombre.toLowerCase()];
        if (v === undefined) return `{${nombre}}`;
        const s = String(v);
        return nombre[0] === nombre[0].toUpperCase() ? s.charAt(0).toUpperCase() + s.slice(1) : s;
    });
}

/** Mensaje de un error de api.js en el idioma activo (usa `err.codigo`). */
export function mensajeError(err) {
    if (err?.codigo && DICC.es[`error.${err.codigo}`]) return t(`error.${err.codigo}`, { status: err.status });
    return err?.message || t("error.inesperado");
}

/** Aplica el idioma a los textos marcados del documento. */
export function traducirDocumento(raiz = document) {
    document.documentElement.lang = actual;
    raiz.querySelectorAll("[data-i18n]").forEach((n) => { n.textContent = t(n.dataset.i18n, n.dataset); });
    raiz.querySelectorAll("[data-i18n-placeholder]").forEach((n) => { n.placeholder = t(n.dataset.i18nPlaceholder); });
    raiz.querySelectorAll("[data-i18n-aria]").forEach((n) => { n.setAttribute("aria-label", t(n.dataset.i18nAria)); });
    raiz.querySelectorAll("[data-i18n-title]").forEach((n) => { n.title = t(n.dataset.i18nTitle); });
}

/** Anade `?lang=` a un enlace hacia la otra pagina, conservando el hash. */
export function conIdioma(url) {
    if (!url) return url;
    const u = new URL(url, window.location.href);
    u.searchParams.set("lang", actual);
    return u.href;
}

/**
 * Monta el selector de banderas al final de `contenedor`. `alCambiar(idioma)` se llama
 * despues de traducir el documento, para que la pagina rehaga lo dinamico.
 */
export function montarSelector(contenedor, alCambiar) {
    const grupo = document.createElement("div");
    grupo.className = "selector-idioma";
    grupo.setAttribute("role", "group");

    const banderas = { es: "img/bandera-co.svg", en: "img/bandera-us.svg" };
    const botones = IDIOMAS.map((codigo) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "bandera";
        b.dataset.idioma = codigo;
        const img = document.createElement("img");
        img.src = banderas[codigo];
        img.alt = "";
        img.width = 24;
        img.height = 16;
        const sigla = document.createElement("span");
        sigla.textContent = codigo.toUpperCase();
        b.append(img, sigla);
        b.addEventListener("click", () => {
            if (codigo === actual) return;
            actual = codigo;
            try { localStorage.setItem(CLAVE, codigo); } catch { /* sin almacenamiento */ }
            refrescar();
            traducirDocumento();
            alCambiar?.(codigo);
        });
        return b;
    });

    function refrescar() {
        grupo.setAttribute("aria-label", t("idioma.cambiar"));
        for (const b of botones) {
            const activo = b.dataset.idioma === actual;
            b.setAttribute("aria-pressed", String(activo));
            b.title = t(`idioma.${b.dataset.idioma}`);
            b.setAttribute("aria-label", t(`idioma.${b.dataset.idioma}`));
        }
    }

    grupo.append(...botones);
    refrescar();
    // al final de la barra (esquina derecha): posicion fija del selector de idioma
    contenedor.append(grupo);
    traducirDocumento();
}
