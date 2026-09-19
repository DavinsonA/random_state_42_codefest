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

import { enviarChat, obtenerSalud } from "./api.js";
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
import { capturarGraficas, descargarInforme } from "./informe.js";
import { abrirVisor, enlazarReferencias } from "./referencias.js";
import { conTransicion, paginaLista, suavizarEnlace } from "./transiciones.js";

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

/** Tono (0-360) de un color de token `#RRGGBB`. */
function tonoDe(hex) {
    const [r, g, b] = [0, 1, 2].map((i) => parseInt(hex.slice(1 + 2 * i, 3 + 2 * i), 16) / 255);
    const max = Math.max(r, g, b);
    const d = max - Math.min(r, g, b);
    if (!d) return 0;
    const h = max === r ? ((g - b) / d) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
    return (h * 60 + 360) % 360;
}

/** `n` colores distinguibles para categorias que no son fenomenos (organizaciones, formatos...).
 *  Parten del tono de marca (`--arpia-primary`) y giran por el circulo cromatico: con tonos de una
 *  sola familia, cinco lineas de una serie temporal no se distinguen. Hasta 8 categorias giran 47
 *  grados; con mas, el circulo se reparte y se alterna la luminosidad. */
function paletaCategorica(n) {
    const base = tonoDe(tok("primary"));
    const paso = n <= 8 ? 47 : 360 / n;
    return Array.from({ length: n }, (_, i) => `hsl(${Math.round((base + paso * i) % 360)} 62% ${n > 8 && i % 2 ? 46 : 60}%)`);
}

Chart.defaults.color = tok("text-secondary");
Chart.defaults.borderColor = tok("border");
Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
Chart.defaults.maintainAspectRatio = false;
Chart.defaults.plugins.legend.labels.boxWidth = 10;

// Animacion de los graficos: corta y con salida suave. Si el sistema pide
// reducir movimiento, no se anima.
const REDUCIR_MOVIMIENTO = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
// Se MUTA `defaults.animation`, no se reemplaza: al sustituirlo entero se perdia la
// configuracion por defecto de las animaciones de color, y cada grafico lanzaba
// `this._fn is not a function` al animar `backgroundColor` y `borderColor`.
if (REDUCIR_MOVIMIENTO) {
    Chart.defaults.animation = false;
} else {
    Chart.defaults.animation.duration = 650;
    Chart.defaults.animation.easing = "easeOutQuart";
}

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

/** Tipos de la serie temporal que el usuario puede alternar debajo del grafico. */
const TIPOS_SERIE = ["linea", "columnas", "barras"];

function configSerie(tipo, { labels, series }) {
    const esLinea = tipo === "linea";
    const horizontal = tipo === "barras";
    const ejeValor = { beginAtZero: true, ticks: { precision: 0 } };
    return {
        type: esLinea ? "line" : "bar",
        data: {
            labels,
            datasets: series.map((s) => (esLinea
                ? {
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
                }
                : { label: s.label, data: s.valores, backgroundColor: s.color, borderRadius: 3 })),
        },
        options: {
            indexAxis: horizontal ? "y" : "x",
            // Al pasar el mouse: el tooltip muestra el ano y el valor de cada serie.
            interaction: esLinea ? { mode: "nearest", intersect: true } : { mode: "index", intersect: false },
            plugins: { legend: { display: series.length > 1, position: "bottom" } },
            scales: horizontal ? { x: ejeValor } : { y: ejeValor },
            onClick: (_ev, e) => e[0] && series[e[0].datasetIndex].meta?.[e[0].index] && mostrarDocs(series[e[0].datasetIndex].meta[e[0].index]),
        },
    };
}

/**
 * Serie por ano, una serie por fenomeno, con botones debajo para verla como
 * linea, columnas o barras. `memoria.tipo` guarda la eleccion del panel para
 * que la vista ampliada abra con el mismo tipo.
 * `series`: [{ label, color, valores, meta }]
 */
function dibujarSerie(cont, { etiqueta, labels, series, memoria = { tipo: "linea" } }) {
    const canvas = lienzo(cont, etiqueta);
    let chart = null;

    // Los botones se insertan ANTES de crear el grafico: asi Chart.js mide el
    // espacio que de verdad le queda. Si se crea primero (vista ampliada), el
    // canvas toma todo el alto y queda encima de los botones, tapando el clic.
    const grupo = el("div", "selector-grafico");
    grupo.setAttribute("role", "group");
    grupo.setAttribute("aria-label", t("serie.tipo"));
    const botones = TIPOS_SERIE.map((tipo) => {
        const b = el("button", "tipo-grafico", t(`serie.${tipo}`));
        b.type = "button";
        b.dataset.tipo = tipo;
        b.setAttribute("aria-pressed", String(tipo === memoria.tipo));
        b.addEventListener("click", () => {
            if (tipo === memoria.tipo) return;
            memoria.tipo = tipo;
            chart?.destroy();
            chart = new Chart(canvas, configSerie(tipo, { labels, series }));
            botones.forEach((x) => x.setAttribute("aria-pressed", String(x.dataset.tipo === tipo)));
        });
        return b;
    });
    grupo.append(...botones);
    cont.append(grupo);

    chart = new Chart(canvas, configSerie(memoria.tipo, { labels, series }));
    return () => chart?.destroy();
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
// si sostiene, cargadas de verdad. Igual que en `main`, el tablero abre solo
// con esas dos: sin paneles de mapa ni de relaciones, que el corpus no tiene.

/** Lo que se ve al abrir el tablero: las dos vistas reales del corpus. */
async function vistasIniciales() {
    return Promise.all(
        [VISTA_TIEMPO_INICIAL, VISTA_INICIAL].map((spec) => vistaDelAgente(spec, { inicial: true })),
    );
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

/** Parte una etiqueta larga en lineas de hasta `ancho` letras (Chart.js dibuja cada elemento en su linea). */
const envolver = (texto, ancho = 18) =>
    String(texto).split(" ").reduce((lineas, palabra) => {
        const ultima = lineas[lineas.length - 1];
        if (ultima !== undefined && `${ultima} ${palabra}`.length <= ancho) lineas[lineas.length - 1] = `${ultima} ${palabra}`;
        else lineas.push(palabra);
        return lineas;
    }, []);

const legible = (g) => String(g ?? "").replace(/_/g, " ") || t("tablero.sinDato");

/** Elige y prepara el renderizador para el tipo de grafico que pidio el agente. */
function dibujanteDe(spec, filas, total) {
    const etiqueta = spec.titulo || tituloPorDefecto(spec);
    // Series: una por fenomeno, salvo que la vista pida cruzar por otra dimension (`serie_por`).
    const claveSerie = (f) => f.serie ?? f.fenomeno;
    const cruzada = Boolean(spec.serie_por) && spec.serie_por !== "fenomeno";
    const claves = [...new Set(filas.map(claveSerie).filter(Boolean))];
    const fens = cruzada ? claves : claves.sort();
    const colores = cruzada ? paletaCategorica(fens.length) : [];
    const etiquetaSerie = (k) => (cruzada ? legible(k) : etiquetaFenomeno(k));
    const colorSerie = (k) => (cruzada ? colores[fens.indexOf(k)] : colorFenomeno(k));
    const porFenomeno = () => agrupar(filas, (f) => f.fenomeno || String(f.grupo)).sort((a, b) => a.k.localeCompare(b.k));

    switch (spec.chart) {
        case "timeline": {
            const anios = [...new Set(filas.map((f) => f.grupo).filter((g) => /^\d{4}$/.test(g)))].sort();
            const series = fens.map((fen) => {
                const m = new Map(filas.filter((f) => claveSerie(f) === fen).map((f) => [f.grupo, f]));
                return {
                    label: etiquetaSerie(fen),
                    color: colorSerie(fen),
                    valores: anios.map((a) => m.get(a)?.valor ?? 0),
                    meta: anios.map((a) => ({ titulo: `${a} · ${legible(fen)}`, doc_ids: m.get(a)?.doc_ids || [] })),
                };
            });
            const memoria = { tipo: "linea" };
            return (c) => dibujarSerie(c, { etiqueta, labels: anios, series, memoria });
        }

        case "donut": {
            if (spec.group_by === "fenomeno" || !spec.group_by) {
                return (c) => dibujarDona(c, {
                    etiqueta,
                    partes: porFenomeno().map((g) => ({
                        label: etiquetaFenomeno(g.k),
                        valor: g.valor,
                        color: colorFenomeno(g.k),
                        meta: { titulo: g.k, doc_ids: g.doc_ids },
                    })),
                });
            }
            // Por otra dimension: una porcion por categoria, sumando los fenomenos.
            const grupos = agrupar(filas, (f) => f.grupo).sort((a, b) => b.valor - a.valor);
            const resto = grupos.slice(MAX_CATEGORIAS);
            const partes = grupos.slice(0, MAX_CATEGORIAS).map((g) => ({ label: legible(g.k), valor: g.valor, meta: { titulo: legible(g.k), doc_ids: g.doc_ids } }));
            if (resto.length) {
                const otros = t("tablero.otros");
                partes.push({ label: otros, valor: resto.reduce((s, g) => s + g.valor, 0), meta: { titulo: otros, doc_ids: resto.flatMap((g) => g.doc_ids) } });
            }
            const colores = paletaCategorica(partes.length);
            partes.forEach((p, i) => { p.color = colores[i]; });
            return (c) => dibujarDona(c, { etiqueta, partes });
        }

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
            if (spec.group_by === "fenomeno" && !spec.serie_por) {
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
            // Por fenomeno van en su orden (F1, F2, F3); en las demas, de mayor a menor.
            const porFen = spec.group_by === "fenomeno";
            const categorias = agrupar(filas, (f) => f.grupo)
                .sort((a, b) => (porFen ? a.k.localeCompare(b.k) : b.valor - a.valor))
                .slice(0, MAX_CATEGORIAS)
                .map((g) => g.k);
            const series = fens.map((fen) => {
                const m = new Map(filas.filter((f) => claveSerie(f) === fen).map((f) => [f.grupo, f]));
                return {
                    label: etiquetaSerie(fen),
                    color: colorSerie(fen),
                    valores: categorias.map((k) => m.get(k)?.valor ?? 0),
                    meta: categorias.map((k) => ({ titulo: `${legible(k)} · ${legible(fen)}`, doc_ids: m.get(k)?.doc_ids || [] })),
                };
            });
            return (c) => dibujarBarras(c, {
                etiqueta,
                labels: categorias.map((k) => (porFen ? envolver(etiquetaFenomeno(k)) : legible(k))),
                series,
                apilado: spec.chart === "stacked_bar",
                // etiquetas largas (organizaciones, fuentes) se leen mejor en horizontal; las de los
                // tres fenomenos, en columnas con el nombre partido en lineas
                horizontal: spec.group_by !== "anio" && !porFen,
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

    // El aviso generico ("solo el 34 % declara ano") lo reemplaza la cobertura MEDIDA de esta vista:
    // decir las dos cosas seguidas confunde (34 % del corpus y 10 % de F1 a la vez).
    const generico = datos.cobertura?.total && /^Cobertura temporal/i.test(spec.nota || "");
    const notas = [generico ? "" : spec.nota, datos.nota];
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
 * Entrada de los paneles: fundido + leve subida, escalonada, y el grafico de
 * cada uno se vuelve a dibujar desde cero (barras que crecen, linea que sube).
 * Se usa al terminar la carga de la pagina y cada vez que cambian las vistas.
 */
function animarPaneles() {
    if (REDUCIR_MOVIMIENTO) return;
    $("graficos").querySelectorAll(".grafico").forEach((panel, i) => {
        panel.style.setProperty("--orden", String(i));
        panel.classList.remove("entrando");
        void panel.offsetWidth;  // reinicia la animacion CSS si ya estaba
        panel.classList.add("entrando");
        // al terminar se quita: la animacion no debe fijar `transform` y
        // anular el efecto hover del panel. El temporizador cubre el caso en
        // que `animationend` no llega (pestana en segundo plano).
        const quitar = () => panel.classList.remove("entrando");
        panel.addEventListener("animationend", quitar, { once: true });
        setTimeout(quitar, 420 + i * 70 + 150);
        panel.querySelectorAll("canvas").forEach((canvas) => {
            const chart = Chart.getChart(canvas);
            if (chart) {
                chart.reset();
                chart.update();
            }
        });
    });
}

/**
 * Reemplaza la columna de graficos con estas vistas y las reparte segun cuantas
 * sean: 1 -> ancho completo y alta; 3 -> la primera a lo ancho y dos debajo;
 * 2 y 4 -> dos columnas; mas -> dos columnas, la primera a lo ancho si es impar.
 */
function mostrarVistas(vistas, { animar = true } = {}) {
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
    if (animar) animarPaneles();
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

    // Hallazgos del compositor: lo que las cifras de la vista dicen, calculado
    // sin modelo. Van debajo de la respuesta y antes de la procedencia porque
    // son lectura de los datos, no una afirmacion del corpus: el analista debe
    // poder distinguir de un vistazo lo que dice un documento de lo que dice la
    // aritmetica sobre la agregacion.
    if (Array.isArray(datos.hallazgos) && datos.hallazgos.length) {
        const lista = el("ul", "hallazgos");
        lista.setAttribute("aria-label", t("tablero.hallazgos"));
        for (const h of datos.hallazgos) lista.append(el("li", null, h));
        caja.append(el("p", "hallazgos-titulo", t("tablero.hallazgos")));
        caja.append(lista);
    }

    // El informe se arma con lo que ya esta en pantalla, asi que el boton solo
    // aparece cuando hay una respuesta que descargar.
    const boton = $("descargar-informe");
    if (boton) {
        boton.hidden = false;
        boton.onclick = () =>
            descargarInforme(estado.ultimaPregunta || "", datos, { graficas: capturarGraficas(document, tok("surface")) });
    }

    // Las citas del texto se vuelven interactivas: al pulsarlas abren el
    // fragmento exacto que las sostiene. Es la trazabilidad que exige RETO.md
    // —todo dato mostrado se rastrea hasta su doc_id y chunk_id— puesta al
    // alcance de un clic, en vez de un identificador que hay que copiar.
    enlazarReferencias(caja, datos.citations);
}

/** Pinta las vistas que pidio el agente. Si no pidio ninguna, el tablero se mantiene. */
async function aplicarVistas(specs, { animar = true } = {}) {
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
    mostrarVistas(vistas, { animar });
    $("graficos").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function preguntar(texto) {
    const limpio = String(texto || "").trim();
    if (!limpio || estado.ocupado) return;
    estado.ocupado = true;
    // La guarda el informe: sin la pregunta, el archivo descargado no dice a
    // que responde.
    estado.ultimaPregunta = limpio;
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
        suavizarEnlace($("enlace-chat"));
    }
}

// Cambio de idioma: los textos fijos los traduce i18n.js; aqui se rehace lo
// generado (graficos, estado del servicio, enlace al chat).
montarSelector($("barra-acciones"), () => conTransicion(async () => {
    actualizarEnlaceChat();
    refrescarSalud();
    // bajo el cargador no se anima: se anima al retirarse (abajo)
    if (estado.specs) await aplicarVistas(estado.specs, { animar: false });
    else mostrarVistas(await vistasIniciales(), { animar: false });
}).then(animarPaneles));
actualizarEnlaceChat();

// Primera carga: las vistas iniciales (datos reales) se arman bajo la pantalla
// de carga y se animan cuando esta se retira, para que la animacion se vea.
mostrarVistas(await vistasIniciales(), { animar: false });
paginaLista().then(animarPaneles);

// La salud decide si se permiten datos simulados (solo en modo stub).
await refrescarSalud();
setInterval(refrescarSalud, 60000);

// Vistas enviadas por URL: "Abrir en el tablero" desde el chat (#vista=) o
// varias a la vez (#vistas=[...]). Tambien si cambian con el tablero abierto.
aplicarVistas(vistasDesdeHash());
window.addEventListener("hashchange", () => aplicarVistas(vistasDesdeHash()));
