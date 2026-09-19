// Descarga del informe: lo que el analista ve, en un archivo que puede archivar.
//
// **Por que Markdown y no PDF.** Un PDF exigiria una libreria nueva —una carga
// mas en la ventana de evaluacion— y produciria un documento que no se puede
// pegar en un correo ni versionar. El Markdown se abre en cualquier sitio, se
// lee tal cual en texto plano y conserva la estructura.
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

/** Dispara la descarga. El objeto URL se libera siempre, haya fallado o no. */
export function descargarInforme(pregunta, datos, opciones = {}) {
    const texto = informeMarkdown(pregunta, datos, opciones);
    const url = URL.createObjectURL(new Blob([texto], { type: "text/markdown;charset=utf-8" }));
    try {
        const a = document.createElement("a");
        a.href = url;
        a.download = `arpia-informe-${sello().archivo}.md`;
        document.body.append(a);
        a.click();
        a.remove();
    } finally {
        // Sin esto cada descarga deja el blob en memoria hasta recargar.
        URL.revokeObjectURL(url);
    }
}
