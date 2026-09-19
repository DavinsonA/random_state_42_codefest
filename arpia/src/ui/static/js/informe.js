// Descarga del informe: lo que el analista ve, en un archivo que puede archivar.
//
// **PDF, con las graficas.** El informe se entrega como PDF porque es lo que un
// analista archiva o adjunta, y porque puede llevar las graficas tal como se
// vieron. Usa jsPDF, servida desde `vendor/` (sin CDN: el despliegue no depende
// de nada externo). `informeMarkdown` se conserva como version en texto plano.
//
// **Por que se arma en el cliente.** Todo lo que lleva el informe ya viajo en
// la respuesta de `/chat`: no hay una peticion mas, no hay un endpoint mas que
// mantener, y lo que se descarga es exactamente lo que se vio. Un informe que
// el servidor regenera puede diferir de lo que el analista tenia en pantalla.
//
// **Trazabilidad.** `RETO.md` exige que todo dato se rastree hasta su `doc_id`
// y su `chunk_id`: el informe los lleva, y por eso sirve como anexo de un
// analisis y no solo como copia de una conversacion.

import { t } from "./i18n.js";

/** Fecha y hora local en ISO corto, para el nombre del archivo y la cabecera. */
function sello(fecha = new Date()) {
    const dos = (n) => String(n).padStart(2, "0");
    return {
        archivo: `${fecha.getFullYear()}${dos(fecha.getMonth() + 1)}${dos(fecha.getDate())}-${dos(fecha.getHours())}${dos(fecha.getMinutes())}`,
        legible: fecha.toLocaleString("es-CO", { dateStyle: "long", timeStyle: "short" }),
    };
}

/** Una cita en una linea, con lo que permite volver al documento. */
function lineaCita(c) {
    const partes = [c.organizacion || c.fuente, c.fenomeno_nombre, c.anio, c.formato].filter(Boolean);
    const cabeza = partes.length ? `${partes.join(" · ")} — ` : "";
    const sitio =
        c.posicion !== null && c.posicion !== undefined && c.total_fragmentos
            ? ` (fragmento ${c.posicion} de ${c.total_fragmentos})`
            : "";
    return `- ${cabeza}\`${c.doc_id}\`${sitio}\n  - \`${c.chunk_id}\``;
}

/** Arma el informe en Markdown a partir de la respuesta de /chat. */
export function informeMarkdown(pregunta, datos, { vistas = [] } = {}) {
    const { legible } = sello();
    const md = datos.metadata || {};
    const lineas = [
        `# ${t("informe.titulo")}`,
        "",
        `**${t("informe.pregunta")}:** ${pregunta}`,
        `**${t("informe.fecha")}:** ${legible}`,
        "",
        "## " + t("informe.respuesta"),
        "",
        String(datos.respuesta || "").trim(),
    ];

    // Los hallazgos con su soporte: sin el, una cifra en un informe es una
    // afirmacion sin fuente, que es justo lo que este sistema no hace.
    const detalle = Array.isArray(datos.hallazgos_detalle) ? datos.hallazgos_detalle : [];
    const textos = Array.isArray(datos.hallazgos) ? datos.hallazgos : [];
    if (textos.length) {
        lineas.push("", `## ${t("informe.hallazgos")}`, "");
        textos.forEach((h, i) => {
            lineas.push(`- ${h}`);
            const d = detalle[i];
            if (d?.doc_ids?.length) lineas.push(`  - ${d.doc_ids.join(", ")}`);
        });
    }

    if (vistas.length) {
        lineas.push("", `## ${t("informe.vistas")}`, "");
        for (const v of vistas) {
            const filtro = v.fenomenos?.length ? ` · ${v.fenomenos.join(", ")}` : "";
            lineas.push(`- **${v.titulo || v.chart}** — ${v.chart} / ${v.group_by || "-"}${filtro}`);
            if (v.nota) lineas.push(`  - ${v.nota}`);
        }
    }

    const citas = Array.isArray(datos.citations) ? datos.citations : [];
    if (citas.length) {
        lineas.push("", `## ${t("informe.fuentes")}`, "");
        for (const c of citas) lineas.push(lineaCita(c));
    }

    lineas.push(
        "",
        "---",
        "",
        `_${t("informe.pie", {
            tokens: md.tokens?.total ?? 0,
            agentes: (md.agentes_invocados || []).join(", "),
        })}_`,
        "",
    );
    return lineas.join("\n");
}

// -- PDF ------------------------------------------------------------------------

const A4 = { ancho: 595.28, alto: 841.89 };
const MARGEN = 42;
const ANCHO_UTIL = A4.ancho - 2 * MARGEN;
const PIE = 46;

/** Colores del PDF: salen de los tokens del tablero (tokens.css), no se escriben aqui. */
function coloresPdf() {
    const css = getComputedStyle(document.documentElement);
    const tok = (n) => css.getPropertyValue(`--arpia-${n}`).trim();
    const rgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
    return {
        banda: rgb(tok("bg")),
        acento: rgb(tok("primary")),
        agua: rgb(tok("space")),
        texto: [30, 41, 59],
        suave: [100, 116, 139],
        linea: [203, 213, 225],
        caja: [241, 245, 249],
    };
}

/** Las fuentes estandar de PDF cubren Latin-1 y unos pocos signos: lo demas se descarta. */
const limpio = (s) =>
    String(s ?? "")
        .replace(/\*\*/g, "")
        .replace(/[^\x09\x0A\x20-\x7E\xA0-\xFF–—‘’“”•…]/g, "");

/** Una cita en texto plano, con lo que permite volver al documento. */
function citaPlana(c) {
    const partes = [c.organizacion || c.fuente, c.fenomeno_nombre, c.anio, c.formato].filter(Boolean);
    const sitio =
        c.posicion !== null && c.posicion !== undefined && c.total_fragmentos
            ? ` (fragmento ${c.posicion} de ${c.total_fragmentos})`
            : "";
    return { cabeza: `${partes.length ? `${partes.join(" · ")} - ` : ""}${c.doc_id}${sitio}`, chunk: c.chunk_id };
}

/**
 * Arma el PDF del informe. Devuelve el documento jsPDF (sin guardarlo).
 *
 * `graficas`: [{ titulo, nota, imagen (JPEG dataURL), ancho, alto }], las que estaban en pantalla.
 */
export function informePdf(pregunta, datos, { graficas = [], jsPDF = globalThis.jspdf?.jsPDF } = {}) {
    if (!jsPDF) throw new Error("jsPDF no esta cargada");
    const c = coloresPdf();
    const doc = new jsPDF({ unit: "pt", format: "a4" });
    const md = datos.metadata || {};
    let y = 0;

    const nuevaPagina = () => {
        doc.addPage();
        y = MARGEN;
    };
    const espacio = (alto) => {
        if (y + alto > A4.alto - PIE) nuevaPagina();
    };
    const parrafo = (texto, { tamano = 10, color = c.texto, estilo = "normal", sangria = 0, interlineado = 1.35 } = {}) => {
        doc.setFont("helvetica", estilo).setFontSize(tamano).setTextColor(...color);
        for (const linea of doc.splitTextToSize(limpio(texto), ANCHO_UTIL - sangria)) {
            espacio(tamano * interlineado);
            doc.text(linea, MARGEN + sangria, y + tamano);
            y += tamano * interlineado;
        }
    };
    const seccion = (texto) => {
        espacio(48);
        y += 14;
        doc.setFont("helvetica", "bold").setFontSize(12).setTextColor(...c.acento);
        doc.text(limpio(texto).toUpperCase(), MARGEN, y + 12);
        y += 18;
        doc.setDrawColor(...c.linea).setLineWidth(0.6).line(MARGEN, y, MARGEN + ANCHO_UTIL, y);
        y += 8;
    };

    // Portada: banda de marca con el titulo y la fecha.
    doc.setFillColor(...c.banda).rect(0, 0, A4.ancho, 92, "F");
    doc.setFillColor(...c.agua).rect(0, 92, A4.ancho, 3, "F");
    doc.setFont("helvetica", "bold").setFontSize(21).setTextColor(255, 255, 255);
    doc.text(limpio(t("informe.titulo")), MARGEN, 46);
    doc.setFont("helvetica", "normal").setFontSize(9.5).setTextColor(...c.agua);
    doc.text(limpio(`${t("informe.fecha")}: ${sello().legible}`), MARGEN, 68);
    y = 116;

    // La consulta, en un recuadro: es a lo que responde todo lo demas.
    const consulta = doc.splitTextToSize(limpio(pregunta || "-"), ANCHO_UTIL - 24);
    const altoConsulta = 26 + consulta.length * 14;
    doc.setFillColor(...c.caja).roundedRect(MARGEN, y, ANCHO_UTIL, altoConsulta, 5, 5, "F");
    doc.setFillColor(...c.acento).rect(MARGEN, y, 3, altoConsulta, "F");
    doc.setFont("helvetica", "bold").setFontSize(8).setTextColor(...c.suave);
    doc.text(limpio(t("informe.pregunta")).toUpperCase(), MARGEN + 14, y + 16);
    doc.setFont("helvetica", "normal").setFontSize(11).setTextColor(...c.texto);
    doc.text(consulta, MARGEN + 14, y + 32);
    y += altoConsulta + 4;

    seccion(t("informe.respuesta"));
    parrafo(String(datos.respuesta || "").trim());

    // Los hallazgos con su soporte: una cifra sin fuente es justo lo que este sistema no hace.
    const textos = Array.isArray(datos.hallazgos) ? datos.hallazgos : [];
    const detalle = Array.isArray(datos.hallazgos_detalle) ? datos.hallazgos_detalle : [];
    if (textos.length) {
        seccion(t("informe.hallazgos"));
        textos.forEach((h, i) => {
            espacio(30);
            doc.setFillColor(...c.acento).circle(MARGEN + 4, y + 6, 2, "F");
            parrafo(h, { sangria: 14 });
            const ids = detalle[i]?.doc_ids;
            if (ids?.length) parrafo(ids.join(", "), { tamano: 8, color: c.suave, sangria: 14 });
            y += 4;
        });
    }

    if (graficas.length) {
        seccion(t("informe.vistas"));
        for (const g of graficas) {
            const alto = Math.min(ANCHO_UTIL * (g.alto / g.ancho), 270);
            const ancho = alto * (g.ancho / g.alto);
            espacio(alto + 40);
            parrafo(g.titulo, { tamano: 10.5, estilo: "bold" });
            if (g.nota) parrafo(g.nota, { tamano: 8, color: c.suave });
            y += 4;
            const x = MARGEN + (ANCHO_UTIL - ancho) / 2;
            doc.addImage(g.imagen, "JPEG", x, y, ancho, alto);
            y += alto + 14;
        }
    }

    const citas = Array.isArray(datos.citations) ? datos.citations : [];
    if (citas.length) {
        seccion(t("informe.fuentes"));
        for (const cita of citas) {
            const { cabeza, chunk } = citaPlana(cita);
            espacio(26);
            parrafo(cabeza, { tamano: 8.5 });
            parrafo(chunk, { tamano: 7.5, color: c.suave, sangria: 10 });
            y += 2;
        }
    }

    // Pie en cada pagina: procedencia y paginacion.
    const total = doc.getNumberOfPages();
    const pie = t("informe.pie", { tokens: md.tokens?.total ?? 0, agentes: (md.agentes_invocados || []).join(", ") });
    for (let n = 1; n <= total; n++) {
        doc.setPage(n);
        doc.setDrawColor(...c.linea).setLineWidth(0.6).line(MARGEN, A4.alto - 34, MARGEN + ANCHO_UTIL, A4.alto - 34);
        doc.setFont("helvetica", "normal").setFontSize(7.5).setTextColor(...c.suave);
        doc.text(doc.splitTextToSize(limpio(pie), ANCHO_UTIL - 90)[0], MARGEN, A4.alto - 22);
        doc.text(limpio(t("informe.pagina", { n, total })), MARGEN + ANCHO_UTIL, A4.alto - 22, { align: "right" });
    }
    return doc;
}

/** Descarga el informe en PDF. */
export function descargarInforme(pregunta, datos, opciones = {}) {
    informePdf(pregunta, datos, opciones).save(`arpia-informe-${sello().archivo}.pdf`);
}

/** Las graficas que el agente puso en el tablero, como imagenes con fondo (para el PDF). */
export function capturarGraficas(raiz = document, fondo = getComputedStyle(document.documentElement).getPropertyValue("--arpia-surface").trim()) {
    return [...raiz.querySelectorAll("article.grafico")]
        .filter((p) => p.querySelector(".insignia-panel")?.dataset.origen === "agente")
        .map((p) => {
            const canvas = p.querySelector("canvas");
            if (!canvas || !canvas.width || !canvas.height) return null;
            // El lienzo es transparente y su texto claro: sin fondo, sobre papel blanco no se lee.
            const plano = document.createElement("canvas");
            plano.width = canvas.width;
            plano.height = canvas.height;
            const g = plano.getContext("2d");
            g.fillStyle = fondo;
            g.fillRect(0, 0, plano.width, plano.height);
            g.drawImage(canvas, 0, 0);
            return {
                titulo: p.querySelector("h3")?.textContent || "",
                nota: p.querySelector(".grafico-nota")?.textContent || "",
                imagen: plano.toDataURL("image/jpeg", 0.92),
                ancho: plano.width,
                alto: plano.height,
            };
        })
        .filter(Boolean);
}
