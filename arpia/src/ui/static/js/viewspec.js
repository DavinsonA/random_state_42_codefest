// Traduce un ViewSpec (src/api/contracts.py) en la llamada de datos del tablero.
//
// El ViewSpec es un esquema cerrado: aqui solo se acepta el mismo vocabulario.
// Lo que no se reconozca se descarta, nunca se interpreta.

import { ApiError, obtenerAgregado } from "./api.js";
import { mensajeError, t } from "./i18n.js";

/** Objeto cuyos valores se leen del idioma activo en cada acceso (getters). */
function traducible(prefijo, claves) {
    const obj = {};
    for (const k of claves) Object.defineProperty(obj, k, { get: () => t(`${prefijo}.${k}`), enumerable: true });
    return Object.freeze(obj);
}

export const FENOMENOS = traducible("fenomeno", ["F1", "F2", "F3"]);

export const CHARTS = ["timeline", "bar", "stacked_bar", "donut", "table", "kpi"];
export const GROUP_BY = ["fenomeno", "organizacion", "fuente", "formato", "anio"];
export const METRICAS = ["conteo_documentos", "conteo_fragmentos"];
const FENS = ["F1", "F2", "F3"];

export const NOMBRE_CHART = traducible("chart", ["timeline", "bar", "stacked_bar", "donut", "table", "kpi"]);

export const NOMBRE_GROUP_BY = traducible("grupo", ["fenomeno", "organizacion", "fuente", "formato", "anio"]);

const NOMBRE_METRICA = traducible("metrica", ["conteo_documentos", "conteo_fragmentos"]);

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

/** Tope de graficos por respuesta: mas de esto deja de ser legible. */
export const MAX_VISTAS = 6;

/**
 * Vistas que trae una respuesta de /chat, ya normalizadas.
 *
 * El contrato actual (src/api/contracts.py) solo tiene `view_spec` (una).
 * Se acepta tambien `view_specs` (lista) para cuando el backend lo exponga:
 * el tablero ya sabe repartir N graficos. Lo invalido se descarta.
 */
export function vistasDeRespuesta(datos) {
    const crudas = Array.isArray(datos?.view_specs) && datos.view_specs.length
        ? datos.view_specs
        : [datos?.view_spec];
    return crudas.map(normalizar).filter(Boolean).slice(0, MAX_VISTAS);
}

/** `#vistas=[...]` o `#vista={...}` en la URL (enlace desde el chat, pruebas). */
export function vistasDesdeHash() {
    const m = window.location.hash.match(/vistas?=([^&]+)/);
    if (!m) return [];
    try {
        const valor = JSON.parse(decodeURIComponent(m[1]));
        return (Array.isArray(valor) ? valor : [valor]).map(normalizar).filter(Boolean).slice(0, MAX_VISTAS);
    } catch {
        return [];
    }
}

export function tituloPorDefecto(spec) {
    const metrica = NOMBRE_METRICA[spec.metrica] || spec.metrica;
    if (spec.chart === "kpi") return t("titulo.total", { metrica });
    return t("titulo.por", { metrica, grupo: NOMBRE_GROUP_BY[spec.group_by] || t("grupo.generico") });
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
        nota: t("nota.simulado"),
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
            return { error: t("error.sin_datos_tablero") };
        }
        return { error: err instanceof ApiError ? mensajeError(err) : t("error.datos") };
    }
}

