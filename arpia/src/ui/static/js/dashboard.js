// Tablero del Reto 2 con el diseno del prototipo: asistente a la izquierda y
// cuatro graficos a la derecha.
//
// Al cargar, los graficos muestran datos PROVISIONALES (marcados como tales).
// Cada respuesta del agente que trae `view_spec` reemplaza el panel que
// corresponde con datos del backend (/api/aggregate):
//   timeline                       -> "Evolucion temporal" (linea por fenomeno)
//   bar/stacked_bar/donut/table/kpi -> "Distribucion de eventos"
// El mapa y las relaciones siguen provisionales: el corpus aun no tiene
// ubicaciones ni actores (ver ViewSpec en src/api/contracts.py).
//
// Chart.js y Leaflet estan vendorizados (static/vendor/) y llegan como
// globales `Chart` y `L`. Todo texto del backend entra con textContent.

import { enviarChat, obtenerSalud } from "./api.js";
import { FENOMENOS, cargar, normalizar, tituloPorDefecto, vistaDesdeHash } from "./viewspec.js";

const $ = (id) => document.getElementById(id);
const fmt = new Intl.NumberFormat("es-CO");
const CLAVE_SESION = "arpia.sesion_tablero";

const estado = { modoStub: false, ocupado: false, carga: 0 };

// -- colores: se leen de tokens.css, nunca se escriben aqui -------------------

const css = getComputedStyle(document.documentElement);
const tok = (nombre) => css.getPropertyValue(`--arpia-${nombre}`).trim();
const colorFenomeno = (f) => tok({ F1: "f1", F2: "f2", F3: "f3" }[f] || "space");

Chart.defaults.color = tok("text-secondary");
Chart.defaults.borderColor = tok("border");
Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
Chart.defaults.maintainAspectRatio = false;
Chart.defaults.plugins.legend.labels.boxWidth = 10;

function el(etiqueta, clase, texto) {
    const nodo = document.createElement(etiqueta);
    if (clase) nodo.className = clase;
    if (texto !== undefined && texto !== null) nodo.textContent = String(texto);
    return nodo;
}

function marcarPanel(idPanel, origen, nota) {
    const panel = $(idPanel);
    const insignia = panel.querySelector(".insignia-panel");
    const textos = { provisional: "Provisional", simulado: "Simulado", agente: "Del agente" };
    insignia.dataset.origen = origen;
    insignia.textContent = textos[origen];
    panel.querySelector(".grafico-nota").textContent = nota || "";
}

// -- datos provisionales (los del prototipo) ------------------------------------

const NOTA_PROVISIONAL = "Datos de ejemplo: se reemplazan con la respuesta del agente.";

const PROVISIONAL = {
    tiempo: { labels: ["2020", "2021", "2022", "2023", "2024", "2025"], valores: [35, 72, 91, 87, 120, 155] },
    eventos: { fenomenos: ["F1", "F2", "F3"], valores: [40, 35, 25] },
    puntos: [[4.711, -74.072, "Bogotá"], [3.451, -76.532, "Cali"], [6.244, -75.581, "Medellín"]],
};

// -- evolucion temporal -----------------------------------------------------------

let graficoTiempo = null;

function dibujarTiempo(labels, datasets, alSeleccionar) {
    graficoTiempo?.destroy();
    graficoTiempo = new Chart($("graficoTiempo"), {
        type: "line",
        data: { labels, datasets },
        options: {
            interaction: { mode: "nearest", intersect: true },
            plugins: { legend: { display: datasets.length > 1, position: "bottom" } },
            scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
            onClick: (_ev, elementos) => {
                const e = elementos[0];
                if (e && alSeleccionar) alSeleccionar(datasets[e.datasetIndex].meta[e.index]);
            },
        },
    });
}

function serie(label, data, color, meta = []) {
    return {
        label,
        data,
        meta,
        borderColor: color,
        backgroundColor: color,
        pointBackgroundColor: tok("text"),
        pointBorderColor: color,
        pointRadius: 3,
        pointHoverRadius: 5,
        borderWidth: 2,
        tension: 0.3,
        // monotona: la curva no pasa por valores que los datos no tienen
        cubicInterpolationMode: "monotone",
    };
}

function tiempoProvisional() {
    const { labels, valores } = PROVISIONAL.tiempo;
    dibujarTiempo(labels, [serie("Eventos (ejemplo)", valores, tok("space"))]);
    $("titulo-tiempo").textContent = "Evolución temporal";
    marcarPanel("panel-tiempo", "provisional", NOTA_PROVISIONAL);
}

function tiempoDesdeDatos(filas) {
    const anios = [...new Set(filas.map((f) => f.grupo).filter((g) => /^\d{4}$/.test(g)))].sort();
    const fens = [...new Set(filas.map((f) => f.fenomeno).filter(Boolean))].sort();
    const datasets = fens.map((fen) => {
        const porAnio = new Map(filas.filter((f) => f.fenomeno === fen).map((f) => [f.grupo, f]));
        return serie(
            `${fen} · ${FENOMENOS[fen]}`,
            anios.map((a) => porAnio.get(a)?.valor ?? 0),
            colorFenomeno(fen),
            anios.map((a) => ({ titulo: `${a} · ${fen}`, doc_ids: porAnio.get(a)?.doc_ids || [] })),
        );
    });
    dibujarTiempo(anios, datasets, mostrarDocs);
}

// -- distribucion de eventos ------------------------------------------------------

let graficoEventos = null;

function dibujarEventos(config) {
    graficoEventos?.destroy();
    graficoEventos = new Chart($("graficoEventos"), config);
}

function dona(labels, valores, colores, meta = []) {
    return {
        type: "doughnut",
        data: {
            labels,
            datasets: [{ data: valores, backgroundColor: colores, borderColor: tok("surface"), borderWidth: 2, hoverOffset: 5 }],
        },
        options: {
            plugins: { legend: { position: "bottom" } },
            onClick: (_ev, e) => e[0] && meta[e[0].index] && mostrarDocs(meta[e[0].index]),
        },
    };
}

function eventosProvisional() {
    const { fenomenos, valores } = PROVISIONAL.eventos;
    dibujarEventos(dona(fenomenos.map((f) => `${f} · ${FENOMENOS[f]}`), valores, fenomenos.map(colorFenomeno)));
    $("titulo-eventos").textContent = "Distribución de eventos";
    marcarPanel("panel-eventos", "provisional", NOTA_PROVISIONAL);
}

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

function eventosDesdeDatos(spec, filas) {
    // Por fenomeno (o indicador): dona con el color semantico de cada fenomeno.
    if (spec.group_by === "fenomeno" || spec.chart === "donut" || spec.chart === "kpi") {
        const grupos = agrupar(filas, (f) => f.fenomeno || f.grupo).sort((a, b) => a.k.localeCompare(b.k));
        dibujarEventos(dona(
            grupos.map((g) => (FENOMENOS[g.k] ? `${g.k} · ${FENOMENOS[g.k]}` : g.k)),
            grupos.map((g) => g.valor),
            grupos.map((g) => colorFenomeno(g.k)),
            grupos.map((g) => ({ titulo: g.k, doc_ids: g.doc_ids })),
        ));
        return;
    }

    // Por otra dimension: barras horizontales; apiladas por fenomeno si hay varios.
    const categorias = agrupar(filas, (f) => f.grupo).sort((a, b) => b.valor - a.valor).slice(0, 12).map((g) => g.k);
    const fens = [...new Set(filas.map((f) => f.fenomeno).filter(Boolean))].sort();
    const meta = [];
    const datasets = fens.map((fen, i) => {
        const porGrupo = new Map(filas.filter((f) => f.fenomeno === fen).map((f) => [f.grupo, f]));
        meta[i] = categorias.map((c) => ({ titulo: `${c} · ${fen}`, doc_ids: porGrupo.get(c)?.doc_ids || [] }));
        return {
            label: `${fen} · ${FENOMENOS[fen]}`,
            data: categorias.map((c) => porGrupo.get(c)?.valor ?? 0),
            backgroundColor: colorFenomeno(fen),
            borderRadius: 3,
        };
    });
    dibujarEventos({
        type: "bar",
        data: { labels: categorias.map((c) => c.replace(/_/g, " ")), datasets },
        options: {
            indexAxis: "y",
            plugins: { legend: { position: "bottom" } },
            scales: { x: { stacked: true, beginAtZero: true, ticks: { precision: 0 } }, y: { stacked: true } },
            onClick: (_ev, e) => e[0] && mostrarDocs(meta[e[0].datasetIndex][e[0].index]),
        },
    });
}

// -- mapa y relaciones (provisionales) ----------------------------------------------

function mapaProvisional() {
    const mapa = L.map("mapa", { attributionControl: true }).setView([4.6, -74.1], 5);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "© OpenStreetMap",
        maxZoom: 18,
    }).addTo(mapa);
    // circleMarker en vez de marker: no depende de imagenes externas de Leaflet.
    for (const [lat, lon, nombre] of PROVISIONAL.puntos) {
        L.circleMarker([lat, lon], {
            radius: 7,
            color: tok("text"),
            weight: 1.5,
            fillColor: tok("space"),
            fillOpacity: 0.9,
        }).addTo(mapa).bindPopup(nombre);
    }
    marcarPanel("panel-mapa", "provisional", "Ubicaciones de ejemplo: el corpus aún no trae lugar por documento.");
}

// -- vista del agente -----------------------------------------------------------------

async function aplicarVista(spec) {
    const turno = ++estado.carga;
    const esTiempo = spec.chart === "timeline";
    const idPanel = esTiempo ? "panel-tiempo" : "panel-eventos";
    const titulo = spec.titulo || tituloPorDefecto(spec);

    document.querySelectorAll(".grafico.activo").forEach((p) => p.classList.remove("activo"));
    $(idPanel).classList.add("activo");

    const { datos, error } = await cargar(spec, { modoStub: estado.modoStub });
    if (turno !== estado.carga) return;  // llego otra vista mientras cargaba

    if (error) {
        marcarPanel(idPanel, "provisional", `${error} Se mantienen los datos de ejemplo.`);
        return;
    }

    const notas = [spec.nota, datos.nota];
    if (datos.cobertura?.total) {
        const { con_dato, total } = datos.cobertura;
        notas.push(`Cobertura: ${fmt.format(con_dato)} de ${fmt.format(total)} documentos (${Math.round((con_dato / total) * 100)}%) tienen año.`);
    }
    const nota = [...new Set(notas.filter(Boolean))].join(" ");

    if (!datos.filas.length) {
        marcarPanel(idPanel, datos.simulado ? "simulado" : "agente", `${titulo}: no hay datos para estos filtros. ${nota}`);
        return;
    }

    if (esTiempo) {
        tiempoDesdeDatos(datos.filas);
        $("titulo-tiempo").textContent = titulo;
    } else {
        eventosDesdeDatos(spec, datos.filas);
        $("titulo-eventos").textContent = titulo;
    }
    marcarPanel(idPanel, datos.simulado ? "simulado" : "agente", nota);
    $(idPanel).scrollIntoView({ behavior: "smooth", block: "nearest" });
}

// -- fuente: trazabilidad -------------------------------------------------------------

function mostrarDocs({ titulo, doc_ids }) {
    const docs = [...new Set(doc_ids || [])];
    $("docId").textContent = docs.length ? `${docs.slice(0, 3).join(", ")}${docs.length > 3 ? ` (+${docs.length - 3})` : ""}` : "---";
    $("docId").title = docs.join("\n");
    $("chunkId").textContent = docs.length ? `agregado · ${titulo}` : "---";
}

function mostrarCitas(citas) {
    if (!Array.isArray(citas) || !citas.length) return;
    const [c] = citas;
    $("docId").textContent = citas.length > 1 ? `${c.doc_id} (+${citas.length - 1})` : c.doc_id;
    $("docId").title = citas.map((x) => x.doc_id).join("\n");
    $("chunkId").textContent = c.chunk_id;
    $("chunkId").title = citas.map((x) => x.chunk_id).join("\n");
}

// -- asistente --------------------------------------------------------------------------

const NOMBRES_AGENTE = {
    orquestador: "Orquestador",
    agente_documental: "Documental",
    agente_visualizador: "Visualizador",
    agente_analitico: "Analítico",
    guardian: "Guardián",
    memoria: "Memoria",
};

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
    for (const parrafo of String(datos.respuesta || "(respuesta vacía)").split(/\n\s*\n/)) {
        if (parrafo.trim()) caja.append(el("p", null, parrafo.trim()));
    }
    const md = datos.metadata || {};
    const meta = el("div", "respuesta-meta");
    for (const a of md.agentes_invocados || []) meta.append(el("span", "chip-agente", NOMBRES_AGENTE[a] || a));
    meta.append(el("span", "mono", `${fmt.format(md.tokens?.total || 0)} tokens · ${fmt.format(md.latencia_ms || 0)} ms`));
    caja.append(meta);
}

async function preguntar(texto) {
    const limpio = String(texto || "").trim();
    if (!limpio || estado.ocupado) return;
    estado.ocupado = true;
    $("enviar").disabled = true;
    $("pensando").classList.add("activo");
    $("respuesta").replaceChildren(el("p", null, "Procesando pregunta..."));

    try {
        const datos = await enviarChat(limpio, sesionId());
        mostrarRespuesta(datos);
        mostrarCitas(datos.citations);
        marcarModo(datos.mode);
        const spec = normalizar(datos.view_spec);
        if (spec) await aplicarVista(spec);
    } catch (err) {
        $("respuesta").replaceChildren(el("p", null, err.message || "No se pudo conectar con el servidor."));
    } finally {
        estado.ocupado = false;
        $("enviar").disabled = false;
        $("pensando").classList.remove("activo");
    }
}

// -- servicio ---------------------------------------------------------------------------

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
        const etiquetas = { ok: "Servicio operativo", degraded: "Servicio degradado", down: "Servicio caído" };
        nodo.dataset.estado = s.status || "down";
        texto.textContent = etiquetas[s.status] || `Estado: ${s.status}`;
        nodo.title = (s.warnings || []).join("\n") || "Sin advertencias";
        lineaIa.dataset.estado = s.status;
        lineaIa.textContent = s.status === "down" ? "● Sistema fuera de línea" : s.status === "degraded" ? "● Sistema en línea (degradado)" : "● Sistema en línea";
        marcarModo(s.mode);
    } catch (err) {
        nodo.dataset.estado = "down";
        texto.textContent = "Sin conexión";
        nodo.title = err.message;
        lineaIa.dataset.estado = "down";
        lineaIa.textContent = "● Sin conexión con el servidor";
    }
}

function urlChat() {
    const { protocol, hostname, port } = window.location;
    const p = port ? `:${port}` : "";
    if (hostname === "dashboard.localhost") return `${protocol}//localhost${p}/`;
    if (hostname.startsWith("dashboard.")) return `${protocol}//${hostname.replace(/^dashboard\./, "frontagent.")}${p}/`;
    return null;
}

// -- arranque ---------------------------------------------------------------------------

$("form-pregunta").addEventListener("submit", (ev) => {
    ev.preventDefault();
    const texto = $("question").value;
    $("question").value = "";
    preguntar(texto);
});

const chat = urlChat();
if (chat) {
    $("enlace-chat").href = chat;
    $("enlace-chat").hidden = false;
}

tiempoProvisional();
eventosProvisional();
mapaProvisional();
marcarPanel("panel-relaciones", "provisional", "Relaciones de ejemplo: el corpus aún no trae actores ni vínculos.");

// La salud decide si se permiten datos simulados (solo en modo stub).
await refrescarSalud();
setInterval(refrescarSalud, 60000);

// Vista enviada desde el chat ("Abrir en el tablero").
const inicial = vistaDesdeHash();
if (inicial) aplicarVista(inicial);
