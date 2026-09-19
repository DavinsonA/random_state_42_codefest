// Referencias de una respuesta: de donde sale cada afirmacion.
//
// Pasar el raton por un identificador de documento (F2-SWF-117) muestra un
// tooltip con su procedencia y el fragmento citado; hacer clic abre un visor con
// el documento reconstruido a partir de sus fragmentos vecinos. El corpus guarda
// texto ya extraido (no el archivo original), asi que el visor es el mismo para
// un PDF, un CSV o una pagina web. Contrato del backend: API.md, "Referencias".
//
// Todo texto del backend entra con textContent, nunca con innerHTML: el corpus
// viene de fuentes externas y puede traer marcado o instrucciones hostiles
// (RETO.md §Defensa contra prompt injection).
//
// Este modulo no toca el DOM al importarse: las funciones puras se prueban con
// `node --test` (tests/js/referencias.test.mjs).

import { obtenerDocumento, obtenerEvidencia } from "./api.js";

const VENTANA = 2;                  // fragmentos a cada lado del citado
const RETRASO_MOSTRAR_MS = 150;     // evita el parpadeo al cruzar el cursor
const RETRASO_OCULTAR_MS = 100;
const LARGO_FRAGMENTO = 240;        // igual a corpus.FRAGMENTO_CHARS: si llega justo, venia recortado

// -- logica pura ------------------------------------------------------------

export function escaparRegex(texto) {
    return texto.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Parte un texto en segmentos `{texto}` y `{id}` segun los doc_id conocidos.
 *
 * Solo reconoce identificadores completos: `F2-SWF-11` no coincide dentro de
 * `F2-SWF-117`. Los ids mas largos van primero por si uno contiene al otro.
 */
export function partirPorReferencias(texto, ids) {
    const cadena = String(texto ?? "");
    if (!cadena) return [];
    const validos = [...new Set(ids)].filter(Boolean).sort((a, b) => b.length - a.length);
    if (!validos.length) return [{ texto: cadena }];

    const re = new RegExp(
        `(?<![A-Za-z0-9_-])(${validos.map(escaparRegex).join("|")})(?![A-Za-z0-9_-])`,
        "g",
    );
    const partes = [];
    let ultimo = 0;
    for (const m of cadena.matchAll(re)) {
        if (m.index > ultimo) partes.push({ texto: cadena.slice(ultimo, m.index) });
        partes.push({ id: m[1] });
        ultimo = m.index + m[1].length;
    }
    if (ultimo < cadena.length) partes.push({ texto: cadena.slice(ultimo) });
    return partes;
}

/** Las dos lineas descriptivas de una cita: de quien es y que lugar ocupa. */
export function describirCita(cita) {
    const origen = [cita.fuente, cita.anio, cita.formato ? String(cita.formato).toUpperCase() : null]
        .filter((x) => x !== null && x !== undefined && x !== "")
        .join(" · ");
    const conPosicion = Number.isInteger(cita.posicion) && Number.isInteger(cita.total_fragmentos);
    const posicion = conPosicion
        ? `Fragmento ${cita.posicion + 1} de ${cita.total_fragmentos.toLocaleString("es-CO")}`
        : "";
    return { origen, posicion };
}

/** Centro de la pagina anterior (`direccion < 0`) o siguiente del visor.
 *
 * La nueva ventana queda pegada a la actual, sin solaparse. El backend recorta
 * el centro a los limites del documento.
 */
export function centroPagina(documento, direccion, ventana = VENTANA) {
    return direccion < 0 ? documento.desde - 1 - ventana : documento.hasta + 1 + ventana;
}

/** El fragmento citado venia recortado si su largo llega al maximo del backend. */
export function citaRecortada(cita) {
    return typeof cita.fragmento === "string" && cita.fragmento.length >= LARGO_FRAGMENTO;
}

const MOTIVOS = {
    "documento no encontrado":
        "Este documento no está en el índice. En modo simulado las referencias son de ejemplo.",
    "el fragmento no pertenece a ese documento": "El fragmento citado no pertenece a este documento.",
    "documento sin fragmentos": "Este documento no tiene fragmentos disponibles.",
};

export function mensajeNoDisponible(motivo) {
    if (MOTIVOS[motivo]) return MOTIVOS[motivo];
    if (String(motivo || "").startsWith("indice no disponible")) {
        return "El índice del corpus todavía no está disponible. Intenta de nuevo en un momento.";
    }
    return "No se pudo abrir el documento.";
}

// -- DOM ----------------------------------------------------------------------

function el(etiqueta, clase, texto) {
    const nodo = document.createElement(etiqueta);
    if (clase) nodo.className = clase;
    if (texto !== undefined && texto !== null) nodo.textContent = String(texto);
    return nodo;
}

// -- tooltip ------------------------------------------------------------------

let tooltip = null;
let anclaActual = null;
let temporizador = null;

function obtenerTooltip() {
    if (tooltip) return tooltip;
    tooltip = el("div", "ref-tooltip");
    tooltip.id = "ref-tooltip";
    tooltip.setAttribute("role", "tooltip");
    tooltip.hidden = true;
    document.body.append(tooltip);
    // Un tooltip que sigue flotando mientras se desplaza el chat queda sobre otra cosa.
    window.addEventListener("scroll", () => ocultarTooltip(true), true);
    return tooltip;
}

function llenarTooltip(t, cita) {
    const { origen, posicion } = describirCita(cita);
    t.replaceChildren();
    if (origen) t.append(el("div", "ref-tooltip-origen", origen));
    t.append(el("div", "ref-tooltip-id mono", cita.doc_id));
    if (posicion) t.append(el("div", "ref-tooltip-pos", posicion));
    if (cita.fragmento) {
        t.append(el("blockquote", "ref-tooltip-texto", citaRecortada(cita) ? `${cita.fragmento}…` : cita.fragmento));
    }
    t.append(el("div", "ref-tooltip-pie", "Clic para abrir el documento"));
}

function posicionarTooltip(t, ancla) {
    const margen = 8;
    const r = ancla.getBoundingClientRect();
    t.style.left = "0px";
    t.style.top = "0px";
    t.hidden = false;
    const ancho = t.offsetWidth;
    const alto = t.offsetHeight;
    const x = Math.max(margen, Math.min(r.left + r.width / 2 - ancho / 2, window.innerWidth - ancho - margen));
    let y = r.bottom + 6;
    if (y + alto + margen > window.innerHeight && r.top - alto - 6 > margen) y = r.top - alto - 6;
    t.style.left = `${Math.round(x)}px`;
    t.style.top = `${Math.round(y)}px`;
}

function mostrarTooltip(ancla, cita) {
    clearTimeout(temporizador);
    temporizador = setTimeout(() => {
        if (visor && !visor.panel.hidden) return;
        const t = obtenerTooltip();
        llenarTooltip(t, cita);
        posicionarTooltip(t, ancla);
        ancla.setAttribute("aria-describedby", "ref-tooltip");
        anclaActual = ancla;
    }, RETRASO_MOSTRAR_MS);
}

function ocultarTooltip(ya = false) {
    clearTimeout(temporizador);
    const ocultar = () => {
        if (tooltip) tooltip.hidden = true;
        if (anclaActual) anclaActual.removeAttribute("aria-describedby");
        anclaActual = null;
    };
    if (ya) ocultar();
    else temporizador = setTimeout(ocultar, RETRASO_OCULTAR_MS);
}

// -- visor del documento ------------------------------------------------------

let visor = null;
let disparador = null;
let tokenCarga = 0;
const estado = { docId: "", citado: "", cita: null, documento: null };

function obtenerVisor() {
    if (visor) return visor;

    const fondo = el("div", "visor-fondo");
    fondo.hidden = true;
    fondo.addEventListener("click", cerrarVisor);

    const panel = el("aside", "visor");
    panel.id = "visor-ref";
    panel.hidden = true;
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-modal", "true");
    panel.setAttribute("aria-labelledby", "visor-titulo");

    const cabeza = el("header", "visor-cabeza");
    const titulos = el("div", "visor-titulos");
    const titulo = el("h2", "visor-titulo mono");
    titulo.id = "visor-titulo";
    const meta = el("p", "visor-meta");
    const fuente = el("p", "visor-fuente mono");
    titulos.append(titulo, meta, fuente);
    const cerrar = el("button", "boton boton-secundario visor-cerrar", "Cerrar");
    cerrar.type = "button";
    cerrar.addEventListener("click", cerrarVisor);
    cabeza.append(titulos, cerrar);

    const cuerpo = el("div", "visor-cuerpo");
    cuerpo.setAttribute("aria-live", "polite");

    const pie = el("footer", "visor-pie");
    const anterior = el("button", "boton boton-texto", "← Anteriores");
    anterior.type = "button";
    const rango = el("span", "visor-rango");
    const siguiente = el("button", "boton boton-texto", "Siguientes →");
    siguiente.type = "button";
    anterior.addEventListener("click", () => pagina(-1));
    siguiente.addEventListener("click", () => pagina(1));
    pie.append(anterior, rango, siguiente);

    panel.append(cabeza, cuerpo, pie);
    document.body.append(fondo, panel);

    panel.addEventListener("keydown", atraparTabulador);
    visor = { fondo, panel, titulo, meta, fuente, cuerpo, pie, anterior, siguiente, rango, cerrar };
    return visor;
}

function atraparTabulador(ev) {
    if (ev.key !== "Tab") return;
    const foco = [...visor.panel.querySelectorAll("button:not([disabled])")];
    if (!foco.length) return;
    const primero = foco[0];
    const ultimo = foco[foco.length - 1];
    if (ev.shiftKey && document.activeElement === primero) {
        ev.preventDefault();
        ultimo.focus();
    } else if (!ev.shiftKey && document.activeElement === ultimo) {
        ev.preventDefault();
        primero.focus();
    }
}

function alTeclear(ev) {
    if (ev.key === "Escape") cerrarVisor();
}

function mostrarAviso(texto, esError = false) {
    const v = obtenerVisor();
    v.cuerpo.replaceChildren(el("p", esError ? "visor-aviso visor-error" : "visor-aviso", texto));
    v.pie.hidden = true;
}

function pintarCabecera(datos) {
    const v = obtenerVisor();
    const meta = [datos.organizacion, datos.anio, datos.formato ? String(datos.formato).toUpperCase() : null, datos.fenomeno_nombre]
        .filter((x) => x !== null && x !== undefined && x !== "")
        .join(" · ");
    v.meta.textContent = meta;
    v.fuente.textContent = datos.fuente || "";
    v.fuente.hidden = !datos.fuente;
}

function pintarFragmento(f, total) {
    const esCitado = f.citado || f.chunk_id === estado.citado;
    const nodo = el("article", esCitado ? "visor-frag visor-frag-citado" : "visor-frag");
    nodo.dataset.chunk = f.chunk_id;

    const cabeza = el("div", "visor-frag-cabeza");
    cabeza.append(el("span", "visor-frag-pos", `Fragmento ${f.posicion + 1} de ${total.toLocaleString("es-CO")}`));
    if (esCitado) cabeza.append(el("span", "visor-frag-marca", "Citado"));
    nodo.append(cabeza);

    const texto = el("div", "visor-frag-texto", f.texto);
    nodo.append(texto);

    if (f.truncado) {
        const boton = el("button", "boton boton-texto visor-frag-completo", "Ver fragmento completo");
        boton.type = "button";
        boton.addEventListener("click", () => expandir(boton, texto, f.chunk_id));
        nodo.append(boton);
    }
    return nodo;
}

async function expandir(boton, texto, chunkId) {
    boton.disabled = true;
    boton.textContent = "Cargando…";
    try {
        const e = await obtenerEvidencia(chunkId);
        if (e.disponible) {
            texto.textContent = e.texto;
            boton.remove();
            return;
        }
        boton.textContent = "No disponible";
    } catch (err) {
        boton.disabled = false;
        boton.textContent = "Reintentar";
    }
}

function pintarDocumento(datos) {
    const v = obtenerVisor();
    estado.documento = datos;
    pintarCabecera(datos);
    v.cuerpo.replaceChildren(...datos.fragmentos.map((f) => pintarFragmento(f, datos.total_fragmentos)));
    v.pie.hidden = false;
    v.anterior.disabled = !datos.hay_anterior;
    v.siguiente.disabled = !datos.hay_siguiente;
    v.rango.textContent =
        `Fragmentos ${(datos.desde + 1).toLocaleString("es-CO")}–${(datos.hasta + 1).toLocaleString("es-CO")} ` +
        `de ${datos.total_fragmentos.toLocaleString("es-CO")}`;

    const citado = v.cuerpo.querySelector(".visor-frag-citado");
    if (citado) citado.scrollIntoView({ block: "center" });
    else v.cuerpo.scrollTop = 0;
}

async function cargar(params) {
    const mio = ++tokenCarga;
    mostrarAviso("Cargando documento…");
    let datos;
    try {
        datos = await obtenerDocumento(estado.docId, { ventana: VENTANA, ...params });
    } catch (err) {
        if (mio === tokenCarga) mostrarAviso(err.message || "No se pudo abrir el documento.", true);
        return;
    }
    if (mio !== tokenCarga) return;  // el usuario ya pidio otra cosa
    if (!datos.disponible) {
        mostrarAviso(mensajeNoDisponible(datos.motivo), true);
        return;
    }
    pintarDocumento(datos);
}

function pagina(direccion) {
    if (!estado.documento) return;
    cargar({ posicion: centroPagina(estado.documento, direccion) });
}

export function abrirVisor(cita, origen) {
    const v = obtenerVisor();
    ocultarTooltip(true);
    disparador = origen || null;
    estado.docId = cita.doc_id;
    // Una cifra agregada solo conoce el documento: sin fragmento citado, el visor
    // abre el documento desde el principio.
    estado.citado = cita.chunk_id || "";
    estado.cita = cita;
    estado.documento = null;

    const { origen: linea } = describirCita(cita);
    v.titulo.textContent = cita.doc_id;
    v.meta.textContent = linea;
    v.fuente.textContent = "";
    v.fuente.hidden = true;
    v.fondo.hidden = false;
    v.panel.hidden = false;
    document.addEventListener("keydown", alTeclear);
    v.cerrar.focus();
    cargar({ chunkId: cita.chunk_id });
}

export function cerrarVisor() {
    if (!visor || visor.panel.hidden) return;
    tokenCarga += 1;
    visor.panel.hidden = true;
    visor.fondo.hidden = true;
    document.removeEventListener("keydown", alTeclear);
    if (disparador && disparador.isConnected) disparador.focus();
    disparador = null;
}

// -- enlaces ------------------------------------------------------------------

function crearReferencia(cita) {
    const boton = el("button", "ref mono", cita.doc_id);
    boton.type = "button";
    boton.setAttribute("aria-haspopup", "dialog");
    boton.addEventListener("mouseenter", () => mostrarTooltip(boton, cita));
    boton.addEventListener("focus", () => mostrarTooltip(boton, cita));
    boton.addEventListener("mouseleave", () => ocultarTooltip());
    boton.addEventListener("blur", () => ocultarTooltip());
    boton.addEventListener("click", () => abrirVisor(cita, boton));
    return boton;
}

/** Convierte en referencias interactivas los doc_id de la respuesta que tienen cita.
 *
 * Recorre los nodos de texto de `raiz`, asi que respeta el formato que ya
 * tenga (negritas, listas). Devuelve cuantas referencias enlazo.
 */
export function enlazarReferencias(raiz, citas) {
    const porDocumento = new Map();
    for (const c of citas || []) {
        if (c && c.doc_id && !porDocumento.has(c.doc_id)) porDocumento.set(c.doc_id, c);
    }
    if (!porDocumento.size) return 0;

    const recorrido = document.createTreeWalker(raiz, NodeFilter.SHOW_TEXT, {
        acceptNode: (n) =>
            n.parentElement && n.parentElement.closest("button, a, .ref")
                ? NodeFilter.FILTER_REJECT
                : NodeFilter.FILTER_ACCEPT,
    });
    const nodos = [];
    while (recorrido.nextNode()) nodos.push(recorrido.currentNode);

    let enlazadas = 0;
    const ids = [...porDocumento.keys()];
    for (const nodo of nodos) {
        const partes = partirPorReferencias(nodo.nodeValue, ids);
        if (!partes.some((p) => p.id)) continue;
        const fragmento = document.createDocumentFragment();
        for (const p of partes) {
            if (p.id) {
                fragmento.append(crearReferencia(porDocumento.get(p.id)));
                enlazadas += 1;
            } else {
                fragmento.append(document.createTextNode(p.texto));
            }
        }
        nodo.replaceWith(fragmento);
    }
    return enlazadas;
}

/** Tarjeta de evidencia: linea de procedencia y boton para abrir el documento.
 *
 * La tarjeta ya muestra la fuente, asi que la linea nueva solo lleva lo que
 * falta (ano, formato, lugar en el documento) para no repetirla.
 */
export function hacerCitaInteractiva(item, cita) {
    const { origen, posicion } = describirCita({ ...cita, fuente: null });
    const detalle = [origen, posicion].filter(Boolean).join(" · ");
    if (detalle) item.append(el("p", "evidencia-meta", detalle));

    const boton = el("button", "boton boton-texto evidencia-abrir", "Abrir documento");
    boton.type = "button";
    boton.setAttribute("aria-haspopup", "dialog");
    boton.addEventListener("click", () => abrirVisor(cita, boton));
    item.append(boton);
}
