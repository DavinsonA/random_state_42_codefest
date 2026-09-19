// Tablero del Reto 2 con el diseno del prototipo: asistente a la izquierda y
// graficos a la derecha.
//
// La columna de graficos se arma aqui. Cada grafico es una
// "vista": { titulo, origen, nota, dibujar(contenedor) -> limpiar }. El mismo
// `dibujar` sirve para el panel y para la vista ampliada (boton "Ampliar"),
// asi el grafico se redibuja nitido al tamano grande en vez de estirarse.
//
// Al cargar se muestran cuatro vistas iniciales. Cada
// respuesta del agente reemplaza la columna con una vista por cada ViewSpec
// que traiga, del tipo que el agente indique, con datos de /api/aggregate.
//
// Chart.js esta vendorizado (static/vendor/) y llega como global `Chart`.
// Todo texto del backend entra con textContent.
//
// No hay mapa: el corpus no trae ubicacion (GET /api/geo lo declara), y un
// mapa geocodificado a ojo seria una afirmacion falsa con autoridad visual.

import { enviarChat, obtenerGeo, obtenerSalud } from "./api.js";
import {
    FENOMENOS,
    NOMBRE_CHART,
    NOMBRE_GROUP_BY,
    VISTA_INICIAL,
    VISTA_TIEMPO_INICIAL,
    cargar,
    tituloPorDefecto,
    vistasDeRespuesta,
    vistasDesdeHash,
} from "./viewspec.js";
import { conIdioma, mensajeError, montarSelector, t } from "./i18n.js";
import { abrirVisor, enlazarReferencias } from "./referencias.js";

const $ = (id) => document.getElementById(id);
const fmt = new Intl.NumberFormat("es-CO");
const CLAVE_SESION = "arpia.sesion_tablero";
const MAX_CATEGORIAS = 12;

const estado = { modoStub: false, ocupado: false, carga: 0, limpiezas: [] };

function el(etiqueta, clase, texto) {
    const nodo = document.createElement(etiqueta);
    if (clase) nodo.className = clase;
    if (texto !== undefined && texto !== null) nodo.textContent = String(texto);
    return nodo;
}

// -- colores: se leen de tokens.css, nunca se escriben aqui -------------------

const css = getComputedStyle(document.documentElement);
const tok = (nombre) => css.getPropertyValue(`--arpia-${nombre}`).trim();
const colorFenomeno = (f) => tok({ F1: "f1", F2: "f2", F3: "f3" }[f] || "space");
const etiquetaFenomeno = (f) => (FENOMENOS[f] ? `${f} · ${FENOMENOS[f]}` : f);

Chart.defaults.color = tok("text-secondary");
Chart.defaults.borderColor = tok("border");
Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
Chart.defaults.maintainAspectRatio = false;
Chart.defaults.plugins.legend.labels.boxWidth = 10;

// =============================================================================
// RENDERIZADORES: cada uno dibuja en `cont` y devuelve su funcion de limpieza
// =============================================================================

function lienzo(cont, etiqueta) {
    const caja = el("div", "lienzo");
    const canvas = el("canvas");
    canvas.setAttribute("role", "img");
    canvas.setAttribute("aria-label", etiqueta);
    caja.append(canvas);
    cont.append(caja);
    return canvas;
}

function grafico(cont, etiqueta, config) {
    const chart = new Chart(lienzo(cont, etiqueta), config);
    return () => chart.destroy();
}

/** Serie por ano, una linea por fenomeno. `series`: [{ label, color, valores, meta }] */
function dibujarLinea(cont, { etiqueta, labels, series }) {
    return grafico(cont, etiqueta, {
        type: "line",
        data: {
            labels,
            datasets: series.map((s) => ({
                label: s.label,
                data: s.valores,
                borderColor: s.color,
                backgroundColor: s.color,
                pointBackgroundColor: tok("text"),
                pointBorderColor: s.color,
                pointRadius: 3,
                pointHoverRadius: 5,
                borderWidth: 2,
                tension: 0.3,
                // monotona: la curva no pasa por valores que los datos no tienen
                cubicInterpolationMode: "monotone",
            })),
        },
        options: {
            interaction: { mode: "nearest", intersect: true },
            plugins: { legend: { display: series.length > 1, position: "bottom" } },
            scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
            onClick: (_ev, e) => e[0] && series[e[0].datasetIndex].meta?.[e[0].index] && mostrarDocs(series[e[0].datasetIndex].meta[e[0].index]),
        },
    });
}

/** Composicion. `partes`: [{ label, valor, color, meta }] */
function dibujarDona(cont, { etiqueta, partes }) {
    return grafico(cont, etiqueta, {
        type: "doughnut",
        data: {
            labels: partes.map((p) => p.label),
            datasets: [{
                data: partes.map((p) => p.valor),
                backgroundColor: partes.map((p) => p.color),
                borderColor: tok("surface"),
                borderWidth: 2,
                hoverOffset: 5,
            }],
        },
        options: {
            plugins: { legend: { position: "bottom" } },
            onClick: (_ev, e) => e[0] && partes[e[0].index].meta && mostrarDocs(partes[e[0].index].meta),
        },
    });
}

/** Barras. `series`: [{ label, color|colores, valores, meta }] */
function dibujarBarras(cont, { etiqueta, labels, series, apilado, horizontal }) {
    const ejeValor = { beginAtZero: true, stacked: apilado, ticks: { precision: 0 } };
    const ejeCategoria = { stacked: apilado };
    return grafico(cont, etiqueta, {
        type: "bar",
        data: {
            labels,
            datasets: series.map((s) => ({
                label: s.label,
                data: s.valores,
                backgroundColor: s.colores || s.color,
                borderRadius: 3,
            })),
        },
        options: {
            indexAxis: horizontal ? "y" : "x",
            plugins: { legend: { display: series.length > 1, position: "bottom" } },
            scales: horizontal ? { x: ejeValor, y: ejeCategoria } : { x: ejeCategoria, y: ejeValor },
            onClick: (_ev, e) => e[0] && series[e[0].datasetIndex].meta?.[e[0].index] && mostrarDocs(series[e[0].datasetIndex].meta[e[0].index]),
        },
    });
}

/** Tabla HTML. `filas`: [{ grupo, fenomeno, valor, doc_ids }] */
function dibujarTabla(cont, { columnaGrupo, filas }) {
    const caja = el("div", "tabla-caja");
    const tabla = el("table", "tabla-datos");
    const cabeza = el("tr");
    [columnaGrupo, t("tablero.tabla.fenomeno"), t("tablero.tabla.valor"), t("tablero.tabla.documentos")].forEach((texto, i) => {
        const th = el("th", i >= 2 ? "num" : null, texto);
        th.scope = "col";
        cabeza.append(th);
    });
    const thead = el("thead");
    thead.append(cabeza);
    const tbody = el("tbody");
    for (const f of [...filas].sort((a, b) => b.valor - a.valor)) {
        const tr = el("tr");
        const fen = el("td");
        if (f.fenomeno) {
            const chip = el("span", "chip-fenomeno mono", f.fenomeno);
            chip.dataset.fenomeno = f.fenomeno;
            fen.append(chip);
        } else {
            fen.textContent = "—";
        }
        tr.append(
            el("td", null, String(f.grupo).replace(/_/g, " ") || t("tablero.sinDato")),
            fen,
            el("td", "num mono", fmt.format(f.valor)),
            el("td", "num mono", fmt.format(f.doc_ids.length)),
        );
        tr.tabIndex = 0;
        tr.addEventListener("click", () => mostrarDocs({ titulo: String(f.grupo), doc_ids: f.doc_ids }));
        tbody.append(tr);
    }
    tabla.append(thead, tbody);
    caja.append(tabla);
    cont.append(caja);
    return () => {};
}

/** Indicador: total grande + desglose por fenomeno. */
function dibujarKpi(cont, { total, etiqueta, partes }) {
    const caja = el("div", "kpi");
    caja.append(el("p", "kpi-cifra mono", fmt.format(total)), el("p", "kpi-etiqueta", etiqueta));
    if (partes.length > 1) {
        const lista = el("ul", "kpi-desglose");
        for (const p of partes) {
            const li = el("li", "kpi-parte");
            li.dataset.fenomeno = p.k;
            li.append(el("span", "mono", p.k), el("strong", "mono", fmt.format(p.valor)));
            li.addEventListener("click", () => mostrarDocs({ titulo: p.k, doc_ids: p.doc_ids }));
            lista.append(li);
        }
        caja.append(lista);
    }
    cont.append(caja);
    return () => {};
}


function dibujarRelaciones(cont, { nodos }) {
    const caja = el("div", "relaciones");
    const posiciones = ["centro", "arriba", "abajo"];
    nodos.forEach((n, i) => caja.append(el("div", `nodo ${posiciones[i] || ""}`, n)));
    cont.append(caja);
    return () => {};
}

// =============================================================================
// VISTAS DE ARRANQUE
// =============================================================================
//
// **Ningun dato se inventa.** `RETO.md` §Restricciones duras: "Datos reales en
// la version desplegada. No se aceptan datos simulados o inventados en el
// tablero final". El prototipo abria con series, marcadores de mapa y nodos de
// ejemplo; se cambiaron por lo unico defendible: las dos vistas que el corpus
// si sostiene, cargadas de verdad, y una declaracion explicita en las dos que
// no.
//
// Un panel que dice "no hay este dato y por que" es informacion. Un panel con
// tres puntos sobre Colombia que nadie extrajo del corpus es una afirmacion
// falsa con autoridad visual, y es lo primero que se cae si el jurado pregunta
// de donde salio.

/** El mapa no existe, y el backend explica por que. */
async function vistaMapaSinDato() {
    let texto;
    try {
        const g = await obtenerGeo();
        // El backend manda dos frases sin puntuacion final ni mayuscula inicial.
        const frases = [g.motivo, g.alternativa]
            .filter(Boolean)
            .map((f) => f.trim().replace(/[.\s]+$/, ""))
            .map((f) => f[0].toUpperCase() + f.slice(1));
        texto = frases.length ? `${frases.join(". ")}.` : t("tablero.mapa.sinDatos");
    } catch {
        texto = t("tablero.mapa.sinDatos");
    }
    return {
        titulo: t("tablero.mapa"),
        origen: "sin_datos",
        nota: "",
        dibujar: mensaje(texto),
    };
}

/** Las relaciones necesitan el grafo de conocimiento, que era opcional en la
 *  Etapa 1 y no forma parte de esta base. */
function vistaRelacionesSinDato() {
    return {
        titulo: t("tablero.relaciones"),
        origen: "sin_datos",
        nota: "",
        dibujar: mensaje(t("tablero.relaciones.sinDatos")),
    };
}

/** Lo que se ve al abrir el tablero: dos vistas reales y dos declaraciones. */
async function vistasIniciales() {
    const conDatos = await Promise.all(
        [VISTA_TIEMPO_INICIAL, VISTA_INICIAL].map((spec) => vistaDelAgente(spec, { inicial: true })),
    );
    return [...conDatos, await vistaMapaSinDato(), vistaRelacionesSinDato()];
}

// =============================================================================
// VISTAS DEL AGENTE: ViewSpec + datos -> vista
// =============================================================================

/** Suma filas por una clave, conservando doc_ids. */
function agrupar(filas, clave) {
    const m = new Map();
    for (const f of filas) {
        const k = clave(f);
        const g = m.get(k) || { k, valor: 0, doc_ids: [] };
        g.valor += f.valor;
        g.doc_ids.push(...f.doc_ids);
        m.set(k, g);
    }
    return [...m.values()];
}

const legible = (g) => String(g ?? "").replace(/_/g, " ") || t("tablero.sinDato");

/** Elige y prepara el renderizador para el tipo de grafico que pidio el agente. */
function dibujanteDe(spec, filas, total) {
    const etiqueta = spec.titulo || tituloPorDefecto(spec);
    const fens = [...new Set(filas.map((f) => f.fenomeno).filter(Boolean))].sort();
    const porFenomeno = () => agrupar(filas, (f) => f.fenomeno || String(f.grupo)).sort((a, b) => a.k.localeCompare(b.k));

    switch (spec.chart) {
        case "timeline": {
            const anios = [...new Set(filas.map((f) => f.grupo).filter((g) => /^\d{4}$/.test(g)))].sort();
            const series = fens.map((fen) => {
                const m = new Map(filas.filter((f) => f.fenomeno === fen).map((f) => [f.grupo, f]));
                return {
                    label: etiquetaFenomeno(fen),
                    color: colorFenomeno(fen),
                    valores: anios.map((a) => m.get(a)?.valor ?? 0),
                    meta: anios.map((a) => ({ titulo: `${a} · ${fen}`, doc_ids: m.get(a)?.doc_ids || [] })),
                };
            });
            return (c) => dibujarLinea(c, { etiqueta, labels: anios, series });
        }

        case "donut":
            return (c) => dibujarDona(c, {
                etiqueta,
                partes: porFenomeno().map((g) => ({
                    label: etiquetaFenomeno(g.k),
                    valor: g.valor,
                    color: colorFenomeno(g.k),
                    meta: { titulo: g.k, doc_ids: g.doc_ids },
                })),
            });

        case "table":
            return (c) => dibujarTabla(c, { columnaGrupo: NOMBRE_GROUP_BY[spec.group_by] || t("tablero.tabla.grupo"), filas });

        case "kpi":
            return (c) => dibujarKpi(c, {
                total: total ?? filas.reduce((s, f) => s + f.valor, 0),
                etiqueta,
                partes: porFenomeno().filter((g) => FENOMENOS[g.k]),
            });

        default: {
            // bar / stacked_bar. Por fenomeno: una barra por fenomeno con su color.
            if (spec.group_by === "fenomeno") {
                const grupos = porFenomeno();
                return (c) => dibujarBarras(c, {
                    etiqueta,
                    labels: grupos.map((g) => g.k),
                    series: [{
                        label: t("tablero.total"),
                        colores: grupos.map((g) => colorFenomeno(g.k)),
                        valores: grupos.map((g) => g.valor),
                        meta: grupos.map((g) => ({ titulo: g.k, doc_ids: g.doc_ids })),
                    }],
                });
            }
            // Por otra dimension: una serie por fenomeno; apiladas si lo pidio el agente.
            const categorias = agrupar(filas, (f) => f.grupo)
                .sort((a, b) => b.valor - a.valor)
                .slice(0, MAX_CATEGORIAS)
                .map((g) => g.k);
            const series = fens.map((fen) => {
                const m = new Map(filas.filter((f) => f.fenomeno === fen).map((f) => [f.grupo, f]));
                return {
                    label: etiquetaFenomeno(fen),
                    color: colorFenomeno(fen),
                    valores: categorias.map((k) => m.get(k)?.valor ?? 0),
                    meta: categorias.map((k) => ({ titulo: `${legible(k)} · ${fen}`, doc_ids: m.get(k)?.doc_ids || [] })),
                };
            });
            return (c) => dibujarBarras(c, {
                etiqueta,
                labels: categorias.map(legible),
                series,
                apilado: spec.chart === "stacked_bar",
                // etiquetas largas (organizaciones, fuentes) se leen mejor en horizontal
                horizontal: spec.group_by !== "anio",
            });
        }
    }
}

/** Carga los datos de un ViewSpec y lo convierte en vista. Nunca lanza. */
async function vistaDelAgente(spec, { inicial = false } = {}) {
    const titulo = spec.titulo || tituloPorDefecto(spec);
    const { datos, error } = await cargar(spec, { modoStub: estado.modoStub });

    if (error) {
        return { titulo, origen: "sin_datos", nota: `${NOMBRE_CHART[spec.chart]}. ${error}`, dibujar: mensaje(t("tablero.sinDatosTodavia")) };
    }

    const notas = [spec.nota, datos.nota];
    if (datos.cobertura?.total) {
        const { con_dato, total } = datos.cobertura;
        notas.push(t("nota.cobertura", { con: fmt.format(con_dato), total: fmt.format(total), pct: Math.round((con_dato / total) * 100) }));
    }
    const nota = [...new Set(notas.filter(Boolean))].join(" ");
    const origen = datos.simulado ? "simulado" : inicial ? "corpus" : "agente";

    if (!datos.filas.length) {
        return { titulo, origen: datos.simulado ? "simulado" : "sin_datos", nota, dibujar: mensaje(t("tablero.sinDatosFiltros")) };
    }
    return { titulo, origen, nota, dibujar: dibujanteDe(spec, datos.filas, datos.total) };
}

function mensaje(texto) {
    return (c) => {
        c.append(el("p", "grafico-vacio", texto));
        return () => {};
    };
}

// =============================================================================
// PANELES: columna derecha + vista ampliada
// =============================================================================


function iconoAmpliar() {
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 16 16");
    svg.setAttribute("aria-hidden", "true");
    const trazo = document.createElementNS(ns, "path");
    trazo.setAttribute("d", "M2 6V2h4M10 2h4v4M14 10v4h-4M6 14H2v-4");
    svg.append(trazo);
    return svg;
}

function crearPanel(vista, { ancho = false, alto = false } = {}) {
    const panel = el("article", "grafico");
    panel.classList.toggle("ancho", ancho);
    panel.classList.toggle("alto", alto);

    const cabeza = el("div", "grafico-cabeza");
    const ampliar = el("button", "boton-icono boton-ampliar");
    ampliar.type = "button";
    ampliar.title = t("tablero.ampliar");
    ampliar.setAttribute("aria-label", t("tablero.ampliarDe", { titulo: vista.titulo }));
    ampliar.append(iconoAmpliar());
    ampliar.addEventListener("click", () => abrirAmpliado(vista));
    const acciones = el("div", "grafico-acciones");
    // Todo panel dice de donde vienen sus datos: del corpus, del agente, simulado
    // (solo en modo stub) o sin datos.
    const insignia = el("span", "insignia-panel", t(`tablero.origen.${vista.origen}`));
    insignia.dataset.origen = vista.origen;
    acciones.append(insignia);
    acciones.append(ampliar);
    cabeza.append(el("h3", null, vista.titulo), acciones);

    const cuerpo = el("div", "grafico-cuerpo");
    panel.append(cabeza, el("p", "grafico-nota", vista.nota || ""), cuerpo);
    return { panel, cuerpo };
}

/**
 * Reemplaza la columna de graficos con estas vistas y las reparte segun cuantas
 * sean: 1 -> ancho completo y alta; 3 -> la primera a lo ancho y dos debajo;
 * 2 y 4 -> dos columnas; mas -> dos columnas, la primera a lo ancho si es impar.
 */
function mostrarVistas(vistas) {
    for (const limpiar of estado.limpiezas) limpiar();
    estado.limpiezas = [];

    const contenedor = $("graficos");
    contenedor.replaceChildren();
    contenedor.dataset.cantidad = String(vistas.length);

    vistas.forEach((vista, i) => {
        const unico = vistas.length === 1;
        const { panel, cuerpo } = crearPanel(vista, {
            ancho: unico || (vistas.length % 2 === 1 && i === 0),
            alto: unico,
        });
        contenedor.append(panel);
        // se dibuja despues de insertar: Chart.js necesita medir el contenedor
        estado.limpiezas.push(vista.dibujar(cuerpo));
    });
}

// -- vista ampliada ------------------------------------------------------------

let limpiarAmpliado = null;

function abrirAmpliado(vista) {
    const dialogo = $("ampliado");
    limpiarContenidoAmpliado();
    $("ampliado-titulo").textContent = vista.titulo;
    $("ampliado-nota").textContent = vista.nota || "";
    dialogo.showModal();
    // se dibuja con el dialogo ya abierto, para que el grafico mida su tamano grande
    limpiarAmpliado = vista.dibujar($("ampliado-cuerpo"));
}

/** Destruye el grafico ampliado. Idempotente: puede llamarse mas de una vez. */
function limpiarContenidoAmpliado() {
    limpiarAmpliado?.();
    limpiarAmpliado = null;
    $("ampliado-cuerpo").replaceChildren();
}

// La limpieza se hace en cada via de cierre y no depende del evento `close`
// (no todos los navegadores embebidos lo disparan de forma fiable).
function cerrarAmpliado() {
    const dialogo = $("ampliado");
    if (dialogo.open) dialogo.close();
    limpiarContenidoAmpliado();
}

$("ampliado-cerrar").addEventListener("click", cerrarAmpliado);
// Esc: se toma el control para limpiar en el mismo paso
$("ampliado").addEventListener("cancel", (ev) => {
    ev.preventDefault();
    cerrarAmpliado();
});
// clic en el fondo (fuera del cuadro) cierra
$("ampliado").addEventListener("click", (ev) => {
    if (ev.target === ev.currentTarget) cerrarAmpliado();
});
$("ampliado").addEventListener("close", limpiarContenidoAmpliado);

// =============================================================================
// FUENTE: trazabilidad
// =============================================================================

/** El boton de la seccion Fuente abre el visor del documento (js/referencias.js).
 *  `cita` puede no traer `chunk_id` —una cifra agregada solo sabe el documento—:
 *  entonces el visor abre el documento desde el principio. */
function ofrecerDocumento(cita) {
    const boton = $("abrir-fuente");
    if (!boton) return;
    boton.hidden = !cita;
    boton.onclick = cita ? () => abrirVisor(cita, boton) : null;
}

function mostrarDocs({ titulo, doc_ids }) {
    const docs = [...new Set(doc_ids || [])];
    $("docId").textContent = docs.length ? `${docs.slice(0, 3).join(", ")}${docs.length > 3 ? ` (+${docs.length - 3})` : ""}` : "---";
    $("docId").title = docs.join("\n");
    $("chunkId").textContent = docs.length ? t("tablero.agregado", { titulo }) : "---";
    ofrecerDocumento(docs.length ? { doc_id: docs[0] } : null);
}

function mostrarCitas(citas) {
    if (!Array.isArray(citas) || !citas.length) return;
    const [c] = citas;
    $("docId").textContent = citas.length > 1 ? `${c.doc_id} (+${citas.length - 1})` : c.doc_id;
    $("docId").title = citas.map((x) => x.doc_id).join("\n");
    $("chunkId").textContent = c.chunk_id;
    $("chunkId").title = citas.map((x) => x.chunk_id).join("\n");
    ofrecerDocumento(c);
}

// =============================================================================
// ASISTENTE
// =============================================================================

function sesionId() {
    try {
        let id = sessionStorage.getItem(CLAVE_SESION);
        if (!id) {
            id = crypto.randomUUID?.() || `t-${Date.now().toString(36)}`;
            sessionStorage.setItem(CLAVE_SESION, id);
        }
        return id;
    } catch {
        window.__arpiaSesionTablero ||= crypto.randomUUID?.() || `t-${Date.now().toString(36)}`;
        return window.__arpiaSesionTablero;
    }
}

function mostrarRespuesta(datos) {
    const caja = $("respuesta");
    caja.replaceChildren();
    for (const parrafo of String(datos.respuesta || t("chat.vacia")).split(/\n\s*\n/)) {
        if (parrafo.trim()) caja.append(el("p", null, parrafo.trim()));
    }
    const md = datos.metadata || {};
    const meta = el("div", "respuesta-meta");
    for (const a of md.agentes_invocados || []) meta.append(el("span", "chip-agente", t(`agente.${a}`)));
    meta.append(el("span", "mono", `${fmt.format(md.tokens?.total || 0)} tokens · ${fmt.format(md.latencia_ms || 0)} ms`));
    caja.append(meta);

    // Las citas del texto se vuelven interactivas: al pulsarlas abren el
    // fragmento exacto que las sostiene. Es la trazabilidad que exige RETO.md
    // —todo dato mostrado se rastrea hasta su doc_id y chunk_id— puesta al
    // alcance de un clic, en vez de un identificador que hay que copiar.
    enlazarReferencias(caja, datos.citations);
}

/** Pinta las vistas que pidio el agente. Si no pidio ninguna, el tablero se mantiene. */
async function aplicarVistas(specs) {
    if (!specs.length) return;
    const turno = ++estado.carga;
    const vistas = await Promise.all(specs.map((s) => vistaDelAgente(s)));
    if (turno !== estado.carga) return;  // llego otra respuesta mientras cargaba

    // Dos vistas con el mismo titulo (p. ej. dona y barras "por fenomeno") se
    // distinguen por su tipo de grafico.
    const repetidos = vistas.map((v) => v.titulo).filter((t, i, a) => a.indexOf(t) !== i);
    vistas.forEach((v, i) => {
        if (repetidos.includes(v.titulo)) v.titulo = `${v.titulo} · ${NOMBRE_CHART[specs[i].chart]}`;
    });
    estado.specs = specs;  // para rehacer los graficos si cambia el idioma
    mostrarVistas(vistas);
    $("graficos").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function preguntar(texto) {
    const limpio = String(texto || "").trim();
    if (!limpio || estado.ocupado) return;
    estado.ocupado = true;
    $("enviar").disabled = true;
    $("pensando").classList.add("activo");
    $("respuesta").replaceChildren(el("p", null, t("tablero.ia.procesando")));

    try {
        const datos = await enviarChat(limpio, sesionId());
        mostrarRespuesta(datos);
        mostrarCitas(datos.citations);
        marcarModo(datos.mode);
        await aplicarVistas(vistasDeRespuesta(datos));
    } catch (err) {
        console.error(err);
        $("respuesta").replaceChildren(el("p", null, mensajeError(err)));
    } finally {
        estado.ocupado = false;
        $("enviar").disabled = false;
        $("pensando").classList.remove("activo");
    }
}

// =============================================================================
// SERVICIO
// =============================================================================

function marcarModo(mode) {
    estado.modoStub = mode === "stub";
    $("aviso-stub").hidden = !estado.modoStub;
}

async function refrescarSalud() {
    const nodo = $("salud");
    const texto = nodo.querySelector(".salud-texto");
    const lineaIa = $("estado-ia");
    try {
        const s = await obtenerSalud();
                nodo.dataset.estado = s.status || "down";
        texto.textContent = ["ok", "degraded", "down"].includes(s.status) ? t(`salud.${s.status}`) : t("salud.estado", { estado: s.status });
        nodo.title = (s.warnings || []).join("\n") || t("salud.sinAdvertencias");
        lineaIa.dataset.estado = s.status;
        lineaIa.textContent = t(s.status === "down" ? "tablero.ia.fuera" : s.status === "degraded" ? "tablero.ia.degradado" : "tablero.ia.enLinea");
        marcarModo(s.mode);
    } catch (err) {
        nodo.dataset.estado = "down";
        texto.textContent = t("salud.sinConexion");
        nodo.title = mensajeError(err);
        lineaIa.dataset.estado = "down";
        lineaIa.textContent = t("tablero.ia.sinConexion");
    }
}

function urlChat() {
    const { protocol, hostname, port, pathname } = window.location;
    const p = port ? `:${port}` : "";
    // Abierta como archivo (Live Server, file://): el chat es el archivo vecino.
    if (pathname.endsWith(".html")) return new URL("chat.html", window.location.href).href;
    if (hostname === "dashboard.localhost") return `${protocol}//localhost${p}/`;
    if (hostname.startsWith("dashboard.")) return `${protocol}//${hostname.replace(/^dashboard\./, "frontagent.")}${p}/`;
    return null;
}

// =============================================================================
// ARRANQUE
// =============================================================================

$("form-pregunta").addEventListener("submit", (ev) => {
    ev.preventDefault();
    const texto = $("question").value;
    $("question").value = "";
    preguntar(texto);
});

function actualizarEnlaceChat() {
    const chat = urlChat();
    if (chat) {
        $("enlace-chat").href = conIdioma(chat);
        $("enlace-chat").hidden = false;
    }
}

// Cambio de idioma: los textos fijos los traduce i18n.js; aqui se rehace lo
// generado (graficos, estado del servicio, enlace al chat).
montarSelector($("barra-acciones"), () => {
    actualizarEnlaceChat();
    refrescarSalud();
    if (estado.specs) aplicarVistas(estado.specs);
    else vistasIniciales().then(mostrarVistas);
});
actualizarEnlaceChat();

mostrarVistas(await vistasIniciales());

// La salud decide si se permiten datos simulados (solo en modo stub).
await refrescarSalud();
setInterval(refrescarSalud, 60000);

// Vistas enviadas por URL: "Abrir en el tablero" desde el chat (#vista=) o
// varias a la vez (#vistas=[...]). Tambien si cambian con el tablero abierto.
aplicarVistas(vistasDesdeHash());
window.addEventListener("hashchange", () => aplicarVistas(vistasDesdeHash()));
