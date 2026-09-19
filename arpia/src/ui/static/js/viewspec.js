// Traduce un ViewSpec (src/api/contracts.py) en la llamada de datos del tablero.
//
// El ViewSpec es un esquema cerrado: aqui solo se acepta el mismo vocabulario.
// Lo que no se reconozca se descarta, nunca se interpreta.

import { ApiError, obtenerVista } from "./api.js";
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
const CHARTS_CON_SERIES = ["bar", "stacked_bar", "timeline"];

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
    titulo: "",  // vacio: el titulo por defecto sale traducido (tituloPorDefecto)
    nota: "",
};

const anio = (v) => (v !== null && v !== undefined && /^\d{4}$/.test(String(v)) ? String(v) : null);

/** Valida y completa un ViewSpec. Devuelve null si no es utilizable. */
export function normalizar(vs) {
    if (!vs || typeof vs !== "object" || !CHARTS.includes(vs.chart)) return null;
    let groupBy = GROUP_BY.includes(vs.group_by) ? vs.group_by : null;
    // Cada componente necesita una dimension concreta para tener sentido.
    if (vs.chart === "timeline") groupBy = "anio";
    // Una dona reparte un todo entre categorias: vale por cualquier dimension menos el ano
    // (una dona de anios no dice nada; para eso esta la linea de tiempo).
    if (vs.chart === "donut" && (!groupBy || groupBy === "anio")) groupBy = "fenomeno";
    if (vs.chart === "stacked_bar" && (!groupBy || groupBy === "fenomeno")) groupBy = "organizacion";
    if ((vs.chart === "bar" || vs.chart === "table") && !groupBy) groupBy = "fenomeno";
    // Segunda dimension (una serie por cada valor). El servidor la valida igual; aqui solo se
    // descarta lo que no se puede pintar: distinta del eje y en un grafico que separe series.
    const eje = vs.chart === "timeline" ? "anio" : groupBy;
    const serie = GROUP_BY.includes(vs.serie_por) && vs.serie_por !== eje && CHARTS_CON_SERIES.includes(vs.chart) ? vs.serie_por : null;
    return {
        chart: vs.chart,
        metrica: METRICAS.includes(vs.metrica) ? vs.metrica : "conteo_documentos",
        fenomenos: Array.isArray(vs.fenomenos) ? vs.fenomenos.filter((f) => FENS.includes(f)) : [],
        desde: anio(vs.desde),
        hasta: anio(vs.hasta),
        group_by: vs.chart === "kpi" ? null : groupBy,
        serie_por: serie,
        limite: Number.isInteger(vs.limite) && vs.limite >= 1 && vs.limite <= 25 ? vs.limite : null,
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

/** Vista con la que abre el panel de evolucion temporal. */
export const VISTA_TIEMPO_INICIAL = {
    chart: "timeline",
    metrica: "conteo_documentos",
    fenomenos: [],
    desde: null,
    hasta: null,
    group_by: "anio",
    titulo: "",  // vacio: el titulo por defecto sale traducido (tituloPorDefecto)
    nota: "",
};

/** Traduce los motivos de `disponible: false` a un mensaje para el analista. */
export function mensajeIndice(motivo) {
    const m = String(motivo || "");
    if (m.startsWith("indice no disponible")) return t("error.indice");
    return m ? t("error.sinDatosMotivo", { motivo: m }) : t("error.datos");
}

/**
 * Carga los datos de una vista.
 * Devuelve { datos } o { error } con un mensaje legible; nunca lanza.
 *
 * Una sola llamada a `POST /api/view`: el servidor resuelve el `ViewSpec` (mismo esquema cerrado
 * que el visualizador), cruza las dimensiones y devuelve categorias x series con su cobertura.
 * Antes la GUI pedia `/api/aggregate` una vez por fenomeno y armaba las series por su cuenta:
 * una copia del criterio del servidor en otro lenguaje. Cada fila lleva su `serie`; `fenomeno`
 * solo cuando la categoria o la serie ES un fenomeno.
 */
export async function cargar(spec, { modoStub = false } = {}) {
    try {
        const r = await obtenerVista(spec);
        if (r.disponible === false) {
            if (modoStub) return { datos: datosSimulados({ ...spec, serie_por: null }) };
            return { error: mensajeIndice(r.motivo) };
        }
        const porFenomeno = r.group_by === "fenomeno";
        const filas = (r.series || []).flatMap((s) =>
            (r.categorias || []).map((c, i) => ({
                grupo: String(c),
                serie: String(s.clave),
                fenomeno: porFenomeno ? (FENS.includes(c) ? c : null) : r.serie_por === "fenomeno" && FENS.includes(s.clave) ? s.clave : null,
                valor: Number(s.valores?.[i]) || 0,
                doc_ids: Array.isArray(s.doc_ids?.[i]) ? s.doc_ids[i].map(String) : [],
            })),
        ).filter((f) => f.valor > 0);

        // `con_dato` son los documentos que SI declaran la dimension y `total` los que la podian
        // declarar. Solo tiene sentido para el ano: en las demas todos tienen dato y mostrar
        // "100 % tienen ano" seria falso. Ese caso ya lo dice la cobertura, no el aviso.
        const temporal = r.group_by === "anio";
        const enDimension = Number(r.cobertura?.documentos_en_dimension) || 0;
        const sinDato = Number(r.cobertura?.sin_dato_en_la_dimension) || 0;
        return {
            datos: {
                filas,
                total: Number(r.total) || 0,
                cobertura: temporal && enDimension ? { con_dato: enDimension - sinDato, total: enDimension } : null,
                // El aviso del servidor ya incluye la nota de la vista: no se dice dos veces.
                nota: temporal ? "" : (r.aviso || "").replace(spec.nota || "\0", "").trim(),
                simulado: false,
            },
        };
    } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
            if (modoStub) return { datos: datosSimulados({ ...spec, serie_por: null }) };
            return { error: t("error.sin_datos_tablero") };
        }
        return { error: err instanceof ApiError ? mensajeError(err) : t("error.datos") };
    }
}
