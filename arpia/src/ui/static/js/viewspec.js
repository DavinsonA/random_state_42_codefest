// Traduce un ViewSpec (src/api/contracts.py) en la llamada de datos del tablero.
//
// El ViewSpec es un esquema cerrado: aqui solo se acepta el mismo vocabulario.
// Lo que no se reconozca se descarta, nunca se interpreta.

import { ApiError, obtenerAgregado } from "./api.js";

export const FENOMENOS = {
    F1: "IA y Capacidades Estratégicas",
    F2: "Seguridad del Entorno Espacial",
    F3: "Dinámicas Territoriales",
};

export const CHARTS = ["timeline", "bar", "stacked_bar", "donut", "table", "kpi"];
export const GROUP_BY = ["fenomeno", "organizacion", "fuente", "formato", "anio"];
export const METRICAS = ["conteo_documentos", "conteo_fragmentos"];
const FENS = ["F1", "F2", "F3"];

export const NOMBRE_CHART = {
    timeline: "Serie anual",
    bar: "Barras",
    stacked_bar: "Barras apiladas por fenómeno",
    donut: "Composición por fenómeno",
    table: "Tabla",
    kpi: "Indicador",
};

export const NOMBRE_GROUP_BY = {
    fenomeno: "fenómeno",
    organizacion: "organización",
    fuente: "fuente",
    formato: "formato",
    anio: "año",
};

const NOMBRE_METRICA = { conteo_documentos: "documentos", conteo_fragmentos: "fragmentos" };

/** Vista con la que abre el tablero si no llega ninguna. */
export const VISTA_INICIAL = {
    chart: "bar",
    metrica: "conteo_documentos",
    fenomenos: [],
    desde: null,
    hasta: null,
    group_by: "fenomeno",
    titulo: "Documentos por fenómeno",
    nota: "",
};

const anio = (v) => (v !== null && v !== undefined && /^\d{4}$/.test(String(v)) ? String(v) : null);

/** Valida y completa un ViewSpec. Devuelve null si no es utilizable. */
export function normalizar(vs) {
    if (!vs || typeof vs !== "object" || !CHARTS.includes(vs.chart)) return null;
    let groupBy = GROUP_BY.includes(vs.group_by) ? vs.group_by : null;
    // Cada componente necesita una dimension concreta para tener sentido.
    if (vs.chart === "timeline") groupBy = "anio";
    if (vs.chart === "donut") groupBy = "fenomeno";
    if (vs.chart === "stacked_bar" && (!groupBy || groupBy === "fenomeno")) groupBy = "organizacion";
    if ((vs.chart === "bar" || vs.chart === "table") && !groupBy) groupBy = "fenomeno";
    return {
        chart: vs.chart,
        metrica: METRICAS.includes(vs.metrica) ? vs.metrica : "conteo_documentos",
        fenomenos: Array.isArray(vs.fenomenos) ? vs.fenomenos.filter((f) => FENS.includes(f)) : [],
        desde: anio(vs.desde),
        hasta: anio(vs.hasta),
        group_by: vs.chart === "kpi" ? null : groupBy,
        titulo: typeof vs.titulo === "string" ? vs.titulo : "",
        nota: typeof vs.nota === "string" ? vs.nota : "",
    };
}

/** Lee `#vista=<json>` de la URL (lo envia el chat con "Abrir en el tablero"). */
export function vistaDesdeHash() {
    const m = window.location.hash.match(/vista=([^&]+)/);
    if (!m) return null;
    try {
        return normalizar(JSON.parse(decodeURIComponent(m[1])));
    } catch {
        return null;
    }
}

export function tituloPorDefecto(spec) {
    const met = NOMBRE_METRICA[spec.metrica] || spec.metrica;
    if (spec.chart === "kpi") return `Total de ${met}`;
    return `${met[0].toUpperCase()}${met.slice(1)} por ${NOMBRE_GROUP_BY[spec.group_by] || "grupo"}`;
}

// -- datos -------------------------------------------------------------------

/** Datos de demostracion, SOLO en modo stub. Marcados y deterministas. */
function datosSimulados(spec) {
    const fens = spec.fenomenos.length ? spec.fenomenos : FENS;
    const grupos = {
        fenomeno: null,
        anio: ["2019", "2020", "2021", "2022", "2023", "2024", "2025"],
        organizacion: ["[stub] Organización A", "[stub] Organización B", "[stub] Organización C", "[stub] Organización D"],
        fuente: ["[stub] fuente 1", "[stub] fuente 2", "[stub] fuente 3"],
        formato: ["pdf", "html", "txt"],
    }[spec.group_by || "fenomeno"];
    const filas = [];
    let n = 0;
    for (const f of fens) {
        for (const g of grupos || [f]) {
            if (spec.group_by === "anio" && ((spec.desde && g < spec.desde) || (spec.hasta && g > spec.hasta))) continue;
            n += 1;
            const valor = 5 + ((n * 37 + f.charCodeAt(1) * 11) % 40);
            filas.push({
                grupo: grupos ? g : f,
                fenomeno: f,
                valor,
                doc_ids: Array.from({ length: Math.min(valor, 6) }, (_, i) => `stub-doc-${n}-${i + 1}`),
            });
        }
    }
    return {
        filas,
        total: filas.reduce((s, f) => s + f.valor, 0),
        cobertura: spec.group_by === "anio" ? { con_dato: 622, total: 1826 } : null,
        nota: "Datos simulados (modo stub): no provienen del corpus.",
        simulado: true,
    };
}

/**
 * Carga los datos de una vista.
 * Devuelve { datos } o { error } con un mensaje legible; nunca lanza.
 */
export async function cargar(spec, { modoStub = false } = {}) {
    try {
        const r = await obtenerAgregado(spec);
        const filas = (r.filas || []).map((f) => ({
            grupo: f.grupo === null || f.grupo === undefined ? "" : String(f.grupo),
            fenomeno: FENS.includes(f.fenomeno) ? f.fenomeno : null,
            valor: Number(f.valor) || 0,
            doc_ids: Array.isArray(f.doc_ids) ? f.doc_ids.map(String) : [],
        }));
        return { datos: { filas, total: r.total, cobertura: r.cobertura || null, nota: r.nota || "", simulado: r.mode === "stub" } };
    } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
            if (modoStub) return { datos: datosSimulados(spec) };
            return { error: "El servicio aún no expone los datos del tablero (/api/aggregate). La vista se mostrará en cuanto esté disponible." };
        }
        return { error: err.message || "No se pudieron cargar los datos de la vista." };
    }
}

